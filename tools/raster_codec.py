"""Offline seven-bit packing and LZW primitives recovered from BmpPict2.

No device I/O. The supported LZW dialect starts dictionary entries at 0x104
and packs codes least-significant-bit first into seven-bit transport bytes.
"""


def unpack7(data):
    if any(value & 0x80 for value in data):
        raise ValueError("High bit set in a seven-bit integer")
    return sum(value << (7 * index) for index, value in enumerate(data))


def pack7(value, length):
    if not 0 <= value < 1 << (length * 7):
        raise ValueError("Integer does not fit seven-bit field")
    return bytes((value >> (7 * index)) & 0x7f for index in range(length))


def decompress7(data, start=0, max_output=50_000_000):
    """Return (decoded bytes, first unused input offset, diagnostic counters)."""
    position = start
    reservoir = 0
    available = 0
    output = bytearray()
    table = {value: bytes([value]) for value in range(256)}
    next_code = 0x104
    width = 9
    threshold = 0x1ff
    previous = None
    resets = 0
    code_count = 0
    while True:
        while available < width:
            if position >= len(data):
                raise ValueError("Truncated LZW stream")
            value = data[position]
            if value & 0x80:
                raise ValueError(f"High bit set in LZW transport at {position:#x}")
            reservoir |= value << available
            available += 7
            position += 1
        code = reservoir & ((1 << width) - 1)
        reservoir >>= width
        available -= width
        code_count += 1
        if code == 0x100:
            table = {value: bytes([value]) for value in range(256)}
            next_code = 0x104
            width = 9
            threshold = 0x1ff
            previous = None
            resets += 1
            continue
        if code == 0x101:
            if reservoir:
                raise ValueError("Nonzero padding after LZW end code")
            return bytes(output), position, {"codes": code_count, "dictionary_resets": resets}
        if code in table:
            entry = table[code]
        elif previous is not None and code == next_code:
            entry = previous + previous[:1]
        else:
            raise ValueError(f"Invalid LZW code {code:#x} (next={next_code:#x}, offset={position:#x})")
        if len(output) + len(entry) > max_output:
            raise ValueError("Decoded LZW data exceeds output limit")
        output.extend(entry)
        if previous is not None:
            table[next_code] = previous + entry[:1]
            next_code += 1
            if next_code == threshold:
                width += 1
                threshold = threshold * 2 + 1
                if width > 12:
                    raise ValueError("LZW dictionary grew beyond supported size")
        previous = entry


def compress7(data):
    """Encode the observed byte stream, including CLEAR/END and dictionary resets."""
    output = bytearray()
    reservoir = 0
    available = 0
    width = 9

    def emit(code):
        nonlocal reservoir, available
        reservoir |= code << available
        available += width
        while available >= 7:
            output.append(reservoir & 0x7f)
            reservoir >>= 7
            available -= 7

    dictionary = {}
    next_code = 0x104
    threshold = 0x200
    prefix = None
    emit(0x100)
    for value in data:
        if prefix is None:
            prefix = value
            continue
        pair = (prefix, value)
        found = dictionary.get(pair)
        if found is not None:
            prefix = found
            continue
        dictionary[pair] = next_code
        next_code += 1
        emit(prefix)
        if next_code == threshold:
            width += 1
            threshold *= 2
        if next_code == 0xffe:
            emit(0x100)
            dictionary.clear()
            next_code = 0x104
            width = 9
            threshold = 0x200
        prefix = value
    if prefix is not None:
        emit(prefix)
    emit(0x101)
    if available:
        output.append(reservoir & 0x7f)
    return bytes(output)
