import json
from diag_tree import Ok
from sync_graph import LinuxClockDeviceId, Phc2SysUpdate, SystemClockId
from tcp_transport import DataclassJsonDecoder, DataclassJsonEncoder


def assert_serde_eq(obj):
    ser = json.dumps(obj, cls=DataclassJsonEncoder)
    decoded_obj = DataclassJsonDecoder({Phc2SysUpdate}).decode(ser)

    assert obj == decoded_obj


def test_simple_serde():
    obj = Phc2SysUpdate(SystemClockId("main"), LinuxClockDeviceId("main", 0), Ok())

    assert_serde_eq({})
    assert_serde_eq([])
    assert_serde_eq({"a": 3})
    assert_serde_eq({"a": "b"})
    assert_serde_eq({"a": True})
    assert_serde_eq({"a": None})
    assert_serde_eq(Ok())
    assert_serde_eq(obj)
