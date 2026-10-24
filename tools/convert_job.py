"""Convert observed raw CG-compatible raster jobs entirely offline.

Currently supports PICT-UL/LL, raw magic C358, and raw flags 0041 only. Textual
commands, including vectors and any auto-start command, are preserved verbatim.
The output is a file for comparison, never a transmission to the engraver.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

if __package__:
    from .raster_codec import compress7, pack7
else:
    from raster_codec import compress7, pack7


PICTURE = re.compile(rb"PICT-(UL|LL)\r\xc3\x58")


def convert(data):
    if not data.startswith(b"!ZX\r"):
        raise ValueError("Expected captured raw JBS header")
    output = bytearray()
    cursor = 0
    count = 0
    for match in PICTURE.finditer(data):
        if match.start() < cursor:
            continue
        start = match.end() - 2
        if start + 20 > len(data):
            raise ValueError("Truncated raw picture header")
        _, width, height, xres, yres, flags = struct.unpack_from("<HIIIIH", data, start)
        if flags != 0x41 or not width or not height or width * height > 50_000_000:
            raise ValueError("Unsupported flags or dimensions")
        if not xres or not yres:
            raise ValueError("Invalid resolution")
        end = start + 20 + (width + 2) * height
        if end > len(data):
            raise ValueError("Truncated raw picture payload")
        pixels = data[start+20:end]
        for row in range(height):
            trailer = (row+1) * (width+2)
            if pixels[trailer-2:trailer] != b"\x00\xff":
                raise ValueError(f"Invalid row trailer at row {row}")
        output.extend(data[cursor:match.start()])
        output.extend(b"  PICT-" + match.group(1) + b"\r\x63\x47")
        output.extend(pack7(width, 4))
        output.extend(pack7(height, 4))
        output.extend(pack7(xres * 1000, 4))
        output.extend(pack7(yres * 1000, 4))
        output.extend(pack7(flags | 0x80, 2))
        output.extend(compress7(pixels))
        cursor = end
        count += 1
    output.extend(data[cursor:])
    if not count:
        raise ValueError("No supported raw rasters found")
    return bytes(output), count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--compare", type=Path, help="Original JobServer output to compare")
    args = parser.parse_args()
    if args.destination.exists():
        parser.error("Destination already exists; choose a new filename")
    source = args.source.read_bytes()
    converted, count = convert(source)
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_bytes(converted)
    result = {"rasters_converted": count, "input_bytes": len(source), "output_bytes": len(converted),
              "output_sha256": hashlib.sha256(converted).hexdigest()}
    if args.compare:
        reference = args.compare.read_bytes()
        result["identical_to_reference"] = converted == reference
        if converted != reference:
            result["first_mismatch"] = next((i for i, (a, b) in enumerate(zip(converted, reference)) if a != b),
                                            min(len(converted), len(reference)))
        print(json.dumps(result))
        if converted != reference:
            raise SystemExit(1)
    else:
        print(json.dumps(result))


if __name__ == "__main__":
    main()
