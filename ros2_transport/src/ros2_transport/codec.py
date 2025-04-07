def lossless_decode(b: bytes) -> str:
    """
    Converts any byte sequence into a string without changing any bits.

    Args:
        b: The byte sequence to decode.

    Returns:
        The decoded string.
    """

    # latin1 is an encoding that maps each byte from the range 0-255 to itself.
    return b.decode("latin1")


def lossless_encode(s: str) -> bytes:
    """
    Converts any string into a byte sequence without changing any bits.

    Args:
        s: The string to encode.

    Returns:
        The encoded byte sequence.
    """

    # latin1 is an encoding that maps each byte from the range 0-255 to itself.
    return s.encode("latin1")
