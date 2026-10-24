"""Decode the observed seven-bit CG raster encoding offline, with row checks."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from raster_codec import decompress7, unpack7


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", type=Path)
    parser.add_argument("--output", type=Path, default=Path("captures/decoded/converted-lzw"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    data = args.job.read_bytes()
    if not data.startswith(b"!ZX\r"):
        parser.error("Expected a captured JBS header")
    results = []
    previous_end = 0
    for number, match in enumerate(re.finditer(rb"PICT-(UL|LL)\r\x63\x47", data), 1):
        if match.start() < previous_end:
            continue
        start = match.end() - 2
        if start + 20 > len(data):
            raise ValueError("Truncated CG header")
        width = unpack7(data[start+2:start+6])
        height = unpack7(data[start+6:start+10])
        xres = unpack7(data[start+10:start+14])
        yres = unpack7(data[start+14:start+18])
        flags = unpack7(data[start+18:start+20])
        if flags != 0xc1 or not width or not height or width*height > 50_000_000:
            raise ValueError("Unsupported CG flags or dimensions")
        expected_size = (width+2)*height
        decoded, end, counters = decompress7(data, start+20, max_output=expected_size)
        if len(decoded) != expected_size:
            raise ValueError("Decoded CG size does not match picture dimensions")
        for row in range(height):
            trailer = (row+1)*(width+2)
            if decoded[trailer-2:trailer] != b"\x00\xff":
                raise ValueError(f"Bad decoded row trailer at row {row}")
        (args.output / f"raster-{number:02d}.bin").write_bytes(decoded)
        result = {"number": number, "header_offset": start, "width": width, "height": height,
                  "x_resolution_field": xres, "y_resolution_field": yres, "flags": hex(flags),
                  "resolution_scale": 1000, "rows_with_valid_trailers": height,
                  "stream_end_offset": end, "decoded_size": len(decoded), "counters": counters,
                  "decoded_sha256": hashlib.sha256(decoded).hexdigest(),
                  "prefix_hex": decoded[:64].hex(), "suffix_hex": decoded[-64:].hex(),
                  "following_text": data[end:end+75].decode("ascii", errors="backslashreplace")}
        results.append(result)
        print(json.dumps(result))
        previous_end = end
    if not results:
        parser.error("No supported CG rasters found")
    (args.output / "streams.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
