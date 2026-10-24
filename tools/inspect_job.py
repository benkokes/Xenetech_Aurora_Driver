"""Inspect captured Xenetech jobs offline; decode validated raw C358 rasters.

Only the observed raw raster layout is supported. Converted/compressed rasters
are reported without treating arbitrary binary bytes as commands. No networking.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct


RAW_PICTURE = re.compile(rb"PICT-(UL|LL)\r\xc3\x58")


def inspect(path, output):
    data = path.read_bytes()
    result = {"path": str(path), "size": len(data),
              "sha256": hashlib.sha256(data).hexdigest(),
              "has_jbs_header": data.startswith(b"!ZX\r"), "rasters": [], "text_segments": []}
    if not data:
        result["status"] = "empty"
        return result
    end_of_last = 0
    for number, match in enumerate(RAW_PICTURE.finditer(data), 1):
        if match.start() < end_of_last:
            continue
        header_offset = match.end() - 2
        if header_offset + 20 > len(data):
            raise ValueError(f"Truncated picture header at {header_offset:#x}")
        magic, width, height, xres, yres, flags = struct.unpack_from("<HIIIIH", data, header_offset)
        if flags != 0x41:
            raise ValueError(f"Unvalidated raw raster flags at {header_offset:#x}: {flags:#x}")
        if not width or not height or width * height > 50_000_000:
            raise ValueError(f"Unreasonable dimensions at {header_offset:#x}: {width}x{height}")
        pixel_offset = header_offset + 20
        end = pixel_offset + height * (width + 2)
        if end > len(data):
            raise ValueError(f"Truncated raster at {header_offset:#x}")
        pixels = bytearray()
        for row in range(height):
            start = pixel_offset + row * (width + 2)
            if data[start + width:start + width + 2] != b"\0\xff":
                raise ValueError(f"Invalid row trailer at picture {number}, row {row}")
            row_data = data[start:start + width]
            pixels.extend(row_data[::-1] if row % 2 else row_data)
        before = data[end_of_last:match.start()]
        result["text_segments"].append({"offset": end_of_last, "length": len(before),
                                        "text": before.decode("ascii", errors="backslashreplace")})
        name = f"{path.stem}-raster-{number:02d}"
        raster = {"header_offset": header_offset, "width": width, "height": height,
                  "x_resolution_field": xres, "y_resolution_field": yres,
                  "flags": hex(flags), "origin_label": match.group(1).decode(),
                  "pixel_offset": pixel_offset, "end_offset": end,
                  "rows_with_valid_trailers": height,
                  "signal_min": min(pixels), "signal_max": max(pixels),
                  "pixels_sha256": hashlib.sha256(pixels).hexdigest()}
        # A standalone grayscale PGM keeps the decoder independent of image libraries.
        # Stored zero means white/no exposure; preview uses conventional white paper.
        display = pixels.translate(bytes(255 - i for i in range(256)))
        pgm = output / (name + ".pgm")
        pgm.write_bytes(f"P5\n{width} {height}\n255\n".encode() + display)
        raster["preview_pgm"] = str(pgm)
        result["rasters"].append(raster)
        end_of_last = end
    if result["rasters"]:
        tail = data[end_of_last:]
        result["text_segments"].append({"offset": end_of_last, "length": len(tail),
                                        "text": tail.decode("ascii", errors="backslashreplace")})
        result["status"] = "raw_rasters_decoded"
    else:
        result["status"] = "unsupported_encoding" if result["has_jbs_header"] else "unknown_format"
        result["prefix_hex"] = data[:256].hex()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=Path("captures/decoded"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for path in args.paths:
        destination = args.output / (path.stem + ".json")
        if destination.exists():
            raise FileExistsError(f"Choose a different output folder; report exists: {destination}")
        report = inspect(path, args.output)
        destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({k: v for k, v in report.items() if k != "text_segments"}))


if __name__ == "__main__":
    main()
