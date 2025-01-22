import asyncio
from collections import defaultdict
from copy import deepcopy
from logging import Logger
import logging
import os
import shutil
from signal import SIGINT
import subprocess
from typing import IO, List
from dataclasses import dataclass

import pandas as pd

from pmc_monitor import pmc_parser
from pmc_monitor.pmc_parser import ParseError
from pmc_monitor.pmc_protocol import (
    CurrentDataSet,
    DefaultDataSet,
    ManagementErrorStatusTlv,
    ManagementTlv,
    ParentDataSet,
    PortDataSet,
    PortIdentity,
    PortStatsNp,
    Request,
    Response,
    TimePropertiesDataSet,
    TimeStatusNp,
    UnknownTlv,
)
from pmc_monitor.ptp_instance import PtpInstance, PtpPort


@dataclass
class PmcStateChange:
    old_state: PtpInstance | None
    new_state: PtpInstance | None


def _safe_read(pipe: IO[bytes] | None) -> str | None:
    if pipe is None:
        raise RuntimeError("Broken pipe")
    encoded: bytes | None = pipe.read()
    if encoded is None:
        return None
    return encoded.decode()


class PmcMonitor:
    monitored_datasets = [
        "DEFAULT_DATA_SET",
        "CURRENT_DATA_SET",
        "PARENT_DATA_SET",
        "TIME_PROPERTIES_DATA_SET",
        "TIME_STATUS_NP",
        "PORT_DATA_SET",
        "PORT_STATS_NP",
    ]

    def __init__(
        self, pmc_args: List[str], logger: Logger | None = None, max_wait_s: float = 0.5
    ):
        pmc = shutil.which("pmc")
        if pmc is None:
            raise RuntimeError(
                "`pmc`was not found in `PATH`. Ensure that the `linuxptp` package is installed."
            )

        self._pmc = subprocess.Popen(
            [pmc, *pmc_args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        os.set_blocking(self._pmc.stdout.fileno(), False)  # type: ignore
        os.set_blocking(self._pmc.stderr.fileno(), False)  # type: ignore

        self._ptp_instances: dict[str, PtpInstance] = {}

        self._wait_step_s = 0.1
        self._max_wait_s = max_wait_s

        if logger is not None:
            self._logger = logger
        else:
            self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.setLevel(logging.INFO)

    def stop(self):
        self._pmc.send_signal(SIGINT)
        self._pmc.wait()

    async def query_dataset(self, dataset: str):
        if (return_code := self._pmc.poll()) is not None:
            raise RuntimeError(
                f"PMC process has exited with code {return_code}:\n{self._pmc.stderr.read().decode()}"  # type: ignore
            )

        cmd = f"GET {dataset.strip()}\n"
        self._logger.debug(f"Sending command '{cmd.strip()}'")
        self._pmc.stdin.write(cmd.encode())  # type: ignore
        self._pmc.stdin.flush()  # type: ignore
        await asyncio.sleep(self._wait_step_s)  # type: ignore

    @classmethod
    def _get_stats_table(
        cls, tx_attempts: dict[str, int], tx: dict[str, int], rx: dict[str, int]
    ):
        keys = tx_attempts.keys() | tx.keys() | rx.keys()
        data = [(k, tx_attempts[k], tx[k], rx[k]) for k in keys]
        table = pd.DataFrame(
            data, columns=["TLV type", "TX attempted", "TX confirmed", "RX"]
        )
        table = table.set_index("TLV type")
        return table

    def _handle_management_tlv(
        self, mgmt_tlv: ManagementTlv, source_port: PortIdentity
    ):
        ptp_instance = self._ptp_instances.get(source_port.clock_id)
        instance_old = deepcopy(ptp_instance)
        match ptp_instance:
            case None:
                match mgmt_tlv.payload:
                    case DefaultDataSet() as default_ds:
                        # Port 0 is UDS, not network, so the instance has to be local
                        is_local_instance = source_port.port_number == 0
                        ptp_instance = PtpInstance(is_local_instance, default_ds)
                        self._ptp_instances[source_port.clock_id] = ptp_instance
                    case payload:
                        self._logger.warning(
                            f"Received {payload.__class__.__name__} from port {source_port} before receiving DefaultDS, ignoring"
                        )
                        return None
            case PtpInstance():
                match mgmt_tlv.payload:
                    case DefaultDataSet() as default_ds:
                        ptp_instance.default_ds = default_ds
                    case CurrentDataSet() as current_ds:
                        ptp_instance.current_ds = current_ds
                    case ParentDataSet() as parent_ds:
                        ptp_instance.parent_ds = parent_ds
                    case TimeStatusNp() as time_status_ds:
                        ptp_instance.time_status_ds = time_status_ds
                    case TimePropertiesDataSet() as time_properties_ds:
                        ptp_instance.time_properties_ds = time_properties_ds
                    case PortDataSet() | PortStatsNp() as port_tlv:
                        port = ptp_instance.ports.get(port_tlv.portIdentity.port_number)
                        match port:
                            case None:
                                match port_tlv:
                                    case PortDataSet() as port_ds:
                                        ptp_instance.ports[
                                            port_tlv.portIdentity.port_number
                                        ] = PtpPort(port_ds)
                                    case other:
                                        self._logger.warning(
                                            f"Received {other.__class__.__name__} from port {source_port} before receiving PortDS, ignoring"
                                        )
                                        return None
                            case PtpPort():
                                match port_tlv:
                                    case PortDataSet() as port_ds:
                                        port.port_ds = port_ds
                                    case PortStatsNp() as port_stats:
                                        port.port_stats = port_stats
                            case _:
                                assert False
                    case other_payload:
                        self._logger.warning(
                            f"Ignoring received {other_payload.__class__.__name__}"
                        )
                        return None
            case _:
                assert False
        return PmcStateChange(instance_old, ptp_instance)

    async def poll(self):
        if (return_code := self._pmc.poll()) is not None and return_code != 0:
            error_text = _safe_read(self._pmc.stderr)
            raise RuntimeError(f"PMC exited with code {return_code}:\n{error_text}")  # type: ignore

        tx_attempt_stats: defaultdict[str, int] = defaultdict(lambda: 0)
        tx_stats: defaultdict[str, int] = defaultdict(lambda: 0)
        rx_stats: defaultdict[str, int] = defaultdict(lambda: 0)

        for dataset in self.monitored_datasets:
            await self.query_dataset(dataset)
            tx_attempt_stats[dataset] += 1

        await asyncio.sleep(self._max_wait_s)  # type: ignore

        self._logger.debug("Reading back responses")

        error_text = _safe_read(self._pmc.stderr)
        if error_text is not None:
            self._logger.error(f"PMC error: {error_text.strip()}")

        response_text = _safe_read(self._pmc.stdout)
        if response_text is not None:
            self._logger.debug(f"stdout=\n{response_text}")
            parsed_messages = pmc_parser.parse(response_text)

            for m in parsed_messages:
                match m:
                    case ParseError() as p:
                        self._logger.error(
                            f"Failed to parse at:\n{p.trace}\ngiven the following:\n'{p.rest}'"
                        )
                    case Request() as req:
                        self._logger.debug(
                            f"PMC sent {req.action} query for {req.tlv_type}"
                        )
                        tx_stats[req.tlv_type] += 1
                    case Response() as resp:
                        if resp.action != "RESPONSE":
                            self._logger.warning(
                                f"Expected response of type 'RESPONSE', got '{resp.action}'"
                            )
                            continue

                        match resp.tlv:
                            case ManagementTlv(payload) as mgmt_tlv:
                                self._logger.debug(
                                    f"Got response for {resp.action} query for {payload.tlv_type} from {resp.source_port}"
                                )
                                rx_stats[payload.tlv_type] += 1
                                state_change = self._handle_management_tlv(
                                    mgmt_tlv, resp.source_port
                                )
                                if state_change is not None:
                                    yield state_change
                            case ManagementErrorStatusTlv():
                                self._logger.warning(
                                    f"Got an error status for a {resp.action} query from {resp.source_port}"
                                )
                            case UnknownTlv():
                                self._logger.warning(
                                    f"Got an unknown TLV for a {resp.action} query from {resp.source_port}"
                                )

        stats = self._get_stats_table(tx_attempt_stats, tx_stats, rx_stats)
        self._logger.debug("\n" + stats.to_markdown())
