from ros2_transport.codec import lossless_decode, lossless_encode


def test_codec():
    for i in range(256):
        b = bytes([i])
        s = lossless_decode(b)
        assert lossless_encode(s) == b
