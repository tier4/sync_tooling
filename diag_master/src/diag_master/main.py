import socket


from sync_graph import SyncGraph


from tcp_transport import JsonSubscription
from sync_graph import GraphUpdate
import asyncio

from  argparse import ArgumentParser


class DiagMaster:
    def __init__(self, bind_ip: str, bind_port: int) -> None:
        hostname = socket.gethostname()
        if not hostname:
            raise RuntimeError("Could not determine hostname")

        self.subscription_ = JsonSubscription(
            bind_ip,
            bind_port,
            self.json_callback,
            {GraphUpdate},  # type: ignore
        )

        self.sync_graph_ = SyncGraph()

    def run(self):
        asyncio.run(self.subscription_.listen())

    def json_callback(self, j):
        print(f"got JSON: {j}")
        try:
            self.sync_graph_.update(j)
        except InterruptedError as e:
            raise e
        except Exception as e:
            print(f"error: {e}")
        print(self.sync_graph_)


def main():
    parser = ArgumentParser()
    parser.add_argument("bind_ip")
    parser.add_argument("--bind_port", "-p", type=int, default=16161)
    args = parser.parse_args()
    diag_master = DiagMaster(args.bind_ip, args.bind_port)
    diag_master.run()
