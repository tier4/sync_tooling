"""PTP Management Protocol (PMC) client for monitoring PTP instances."""

import asyncio
import logging
import os
import shutil
import subprocess
from logging import Logger
from signal import SIGINT
from typing import IO, List

from pmc_monitor import pmc_parser
from pmc_monitor.pmc_protocol import (
    CurrentDataSet,
    DefaultDataSet,
    ManagementErrorStatusTlv,
    ManagementTlv,
    Message,
    ParentDataSet,
    PortDataSet,
    PortIdentity,
    Request,
    Response,
    UnknownTlv,
)
from pmc_monitor.ptp_instance import PtpInstance, PtpPort


def _safe_read(pipe: IO[bytes] | None) -> str | None:
    """
    Read from a pipe, returning None if the pipe is closed.
    """
    if pipe is None:
        raise RuntimeError("Broken pipe")
    encoded: bytes | None = pipe.read()
    if encoded is None:
        return None
    return encoded.decode()


class PmcMonitor:
    """
    Monitor PTP instances for their current state through the PTP Management Protocol (PMC).
    """

    # The set of PMC datasets that will be polled
    monitored_datasets = (
        "DEFAULT_DATA_SET",
        "CURRENT_DATA_SET",
        "PARENT_DATA_SET",
        "PORT_DATA_SET",
    )

    def __init__(
        self, pmc_args: List[str], logger: Logger | None = None, max_wait_s: float = 0.1
    ):
        """
        Construct a new PmcMonitor.

        Args:
            pmc_args: The arguments to pass to the `pmc` command. See `man pmc` for more information.
            logger: The logger to use. If not provided, a logger will be created.
            max_wait_s: The maximum amount of time to wait for PMC responses.

        Raises:
            RuntimeError: If `pmc` is not found in `PATH`.
        """
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

        self._wait_step_s = 0.1
        self._max_wait_s = max_wait_s

        if logger is not None:
            self._logger = logger
        else:
            self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.setLevel(logging.INFO)

    def stop(self):
        """
        Stop the PMC process.
        """
        self._pmc.send_signal(SIGINT)
        self._pmc.wait()

    async def query_dataset(self, dataset: str):
        """
        Send a PMC GET command for the given dataset. Receiving has to be handled by the caller.

        Args:
            dataset: The dataset to query, e.g. "DEFAULT_DATA_SET".
        """
        if (return_code := self._pmc.poll()) is not None:
            raise RuntimeError(
                f"PMC process has exited with code {return_code}:\n{self._pmc.stderr.read().decode()}"  # type: ignore
            )

        cmd = f"GET {dataset.strip()}\n"
        self._logger.debug(f"Sending command '{cmd.strip()}'")
        self._pmc.stdin.write(cmd.encode())  # type: ignore
        self._pmc.stdin.flush()  # type: ignore
        await asyncio.sleep(self._wait_step_s)  # type: ignore

    def _handle_management_tlv(
        self,
        mgmt_tlv: ManagementTlv,
        source_port: PortIdentity,
        ptp_instances: dict[str, PtpInstance],
    ):
        """
        Update `ptp_instances` with the given management TLV.

        Args:
            mgmt_tlv: The received management TLV. Only basic data sets are supported.
            source_port: The port that sent the TLV.
            ptp_instances: The collection of PTP instances to update.
        """
        ptp_instance = ptp_instances.get(source_port.clock_id)

        if ptp_instance is None:
            # Port 0 is UDS, not network, so the instance has to be local
            is_local_instance = source_port.port_number == 0
            ptp_instance = PtpInstance(is_local_instance, source_port.clock_id)
            ptp_instances[source_port.clock_id] = ptp_instance

        match mgmt_tlv.payload:
            case DefaultDataSet() as default_ds:
                ptp_instance.default_ds = default_ds
            case CurrentDataSet() as current_ds:
                ptp_instance.current_ds = current_ds
            case ParentDataSet() as parent_ds:
                ptp_instance.parent_ds = parent_ds
            case PortDataSet() as port_ds:
                ptp_instance.ports[port_ds.portIdentity.port_number] = PtpPort(port_ds)
            case other_payload:
                self._logger.warning(
                    f"Ignoring unexpected {other_payload.__class__.__name__}"
                )

    def _handle_response(self, resp: Response, ptp_instances: dict[str, PtpInstance]):
        """
        Handle a PMC response. Does not raise on error but instead logs a warning. The given
        `ptp_instances` will be updated with the received TLVs.

        Args:
            resp: The received response.
            ptp_instances: The collection of PTP instances to update.
        """
        if resp.action != "RESPONSE":
            self._logger.warning(
                f"Expected response of type 'RESPONSE', got '{resp.action}'"
            )
            return

        match resp.tlv:
            case ManagementTlv(payload) as mgmt_tlv:
                self._logger.debug(
                    f"Got response for {resp.action} query for {payload.tlv_type} from {resp.source_port}"
                )
                self._handle_management_tlv(mgmt_tlv, resp.source_port, ptp_instances)
            case ManagementErrorStatusTlv():
                self._logger.warning(
                    f"Got an error status for a {resp.action} query from {resp.source_port}"
                )
            case UnknownTlv():
                self._logger.warning(
                    f"Got an unknown TLV for a {resp.action} query from {resp.source_port}"
                )

    def _handle_message(self, message: Message, ptp_instances: dict[str, PtpInstance]):
        """
        Handle a PMC message. If a response is received, its contents will be added to `ptp_instances`.

        Args:
            message: The received message.
            ptp_instances: The collection of PTP instances to update.
        """
        match message:
            case Request() as req:
                self._logger.debug(f"PMC sent {req.action} query for {req.tlv_type}")
            case Response() as resp:
                self._handle_response(resp, ptp_instances)
            case _:
                raise AssertionError(
                    f"Unexpected message type: {message.__class__.__name__}"
                )

    async def poll(self):
        """
        Poll PTP instances for their current state through the PTP Management Protocol (PMC).

        Raises:
            RuntimeError: When the PMC process exits unexpectedly.

        Yields(PtpInstance):
            The current state of a PTP instance.
        """
        ptp_instances: dict[str, PtpInstance] = {}

        if (return_code := self._pmc.poll()) is not None:
            error_text = _safe_read(self._pmc.stderr)
            raise RuntimeError(f"PMC exited with code {return_code}:\n{error_text}")  # type: ignore

        for dataset in self.monitored_datasets:
            await self.query_dataset(dataset)

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
                self._handle_message(m, ptp_instances)

        for ptp_instance in ptp_instances.values():
            yield ptp_instance
