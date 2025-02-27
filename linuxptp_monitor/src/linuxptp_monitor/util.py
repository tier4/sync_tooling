import socket


def get_hostname() -> str:
    hostname = socket.gethostname()
    if not hostname:
        raise RuntimeError("Could not determine hostname")
    return hostname