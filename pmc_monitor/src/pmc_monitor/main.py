import json
import os
import subprocess
import time

from pmc_monitor.pmc_protocol import Request, Response
from pmc_monitor.pmc_parser import ParseError, parse

import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

POLLED_COMMANDS = [
    "GET USER_DESCRIPTION",
    "GET DEFAULT_DATA_SET",
    "GET CURRENT_DATA_SET",
    "GET PARENT_DATA_SET",
    "GET TIME_PROPERTIES_DATA_SET",
    "GET PRIORITY1",
    "GET PRIORITY2",
    "GET DOMAIN",
    "GET SLAVE_ONLY",
    "GET CLOCK_ACCURACY",
    "GET TRACEABILITY_PROPERTIES",
    "GET TIMESCALE_PROPERTIES",
    "GET TIME_STATUS_NP",
    "GET GRANDMASTER_SETTINGS_NP",
    "GET SUBSCRIBE_EVENTS_NP",
    "GET SYNCHRONIZATION_UNCERTAIN_NP",
    "GET NULL_MANAGEMENT",
    "GET CLOCK_DESCRIPTION",
    "GET PORT_DATA_SET",
    "GET LOG_ANNOUNCE_INTERVAL",
    "GET ANNOUNCE_RECEIPT_TIMEOUT",
    "GET LOG_SYNC_INTERVAL",
    "GET VERSION_NUMBER",
    "GET DELAY_MECHANISM",
    "GET LOG_MIN_PDELAY_REQ_INTERVAL",
    "GET PORT_DATA_SET_NP",
    "GET PORT_STATS_NP",
    "GET PORT_PROPERTIES_NP",
]

POLLED_COMMANDS = [f"{cmd}\n".encode() for cmd in POLLED_COMMANDS]


def main():
    pmc = subprocess.Popen(
        ["pmc", "-u"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    os.set_blocking(pmc.stdout.fileno(), False)
    os.set_blocking(pmc.stderr.fileno(), False)

    cmd_iter = iter(POLLED_COMMANDS)

    while pmc.poll() is None:
        cmd = next(cmd_iter, None)
        if cmd is None:
            break

        logger.debug(f"Sending {cmd}")
        pmc.stdin.write(cmd)
        pmc.stdin.flush()
        logger.debug("Sent, waiting for responses")
        time.sleep(0.5)

        error_lines = pmc.stderr.readlines()
        if error_lines:
            logger.debug(f"Got {len(error_lines)} errors")
            for e in error_lines:
                logger.error(e.decode().removesuffix("\n"))
                pmc.terminate()

        response_lines = pmc.stdout.readlines()
        logger.debug(f"Got {len(response_lines)} responses")
        if response_lines:
            text = "".join([r.decode() for r in response_lines])
            parsed_messages = parse(text)

            for m in parsed_messages:
                match m:
                    case ParseError() as p:
                        logger.error(f"Failed to parse the following:\n'{p.rest}'")
                    case Request() as req:
                        logger.info(f"Sent {req.action} query for {req.tlv_type}")
                    case Response() as resp:
                        logger.info(
                            f"Got response for {resp.action} query for {resp.tlv.payload.__class__.__name__} from {resp.source_port}:\n{json.dumps(resp.tlv.payload.__dict__, indent=2)}"
                        )
