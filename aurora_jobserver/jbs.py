"""Validate the observed JBS dialect and prepare it without device I/O."""
from dataclasses import dataclass
import re
import struct

from tools.convert_job import convert
from tools.raster_codec import decompress7, unpack7


MAX_JOB_BYTES = 64 * 1024 * 1024
PICTURE = re.compile(rb"\s*PICT-(UL|LL)")
DRAFT_MARKER = b"( AURORA_DRAFT_UNCALIBRATED_V1 )"
UNIMPLEMENTED_HOST_DIRECTIVES = (b'set_stamp_mode', b'set_stamp_action')


@dataclass(frozen=True)
class PreparedJob:
    data: bytes
    input_format: str
    rasters: int
    auto_start: bool
    title: str


def prepare(data: bytes, *, allow_draft: bool = False) -> PreparedJob:
    if not data or len(data) > MAX_JOB_BYTES:
        raise ValueError("Job is empty or exceeds the 64 MiB limit")
    if not data.startswith(b"!ZX\r"):
        raise ValueError("Expected a Xenetech JBS header (!ZX)")
    if data.startswith(b"!ZX\r" + DRAFT_MARKER + b"\r") and not allow_draft:
        raise ValueError("Generated artwork is an uncalibrated draft; queue preparation and delivery are blocked")
    if not data.rstrip(b"\r\n \t").endswith(b"END_PLOT"):
        raise ValueError("Job is incomplete: END_PLOT is missing")
    cursor = 0
    formats = set()
    rasters = 0
    auto_start = False
    title = "Untitled"
    while cursor < len(data):
        end = data.find(b"\r", cursor)
        if end < 0:
            if data[cursor:].strip():
                raise ValueError("Unterminated command after job footer")
            break
        line = data[cursor:end].strip()
        cursor = end + 1
        if line.startswith(b"JOB "):
            title = line[4:].decode("cp1252", errors="replace").strip()
        elif line == b"autostart START":
            auto_start = True
        # Legacy preprocessing recognizes these fixed words even when a number
        # touches them ("60set_stamp_mode"). Picture data is skipped as a whole
        # below, so this search examines command text, never binary pixels.
        elif any(directive in line for directive in UNIMPLEMENTED_HOST_DIRECTIVES):
            raise ValueError('Rubber-stamp job preprocessing is not implemented; job was not prepared')
        if not PICTURE.fullmatch(line):
            if line.startswith(b"PICT"):
                raise ValueError("This picture command is not supported yet")
            if any(value < 32 and value not in (9, 10) for value in line):
                raise ValueError("Unexpected binary data outside a supported picture")
            continue
        if cursor + 20 > len(data):
            raise ValueError("Truncated picture header")
        magic = data[cursor:cursor+2]
        if magic == b"\xc3\x58":
            _, width, height, xres, yres, flags = struct.unpack_from("<HIIIIH", data, cursor)
            encoding = "raw"
            expected_flags = 0x41
        elif magic == b"cG":
            width, height, xres, yres = [unpack7(data[cursor+i:cursor+i+4]) for i in (2, 6, 10, 14)]
            flags = unpack7(data[cursor+18:cursor+20])
            encoding = "compressed"
            expected_flags = 0xc1
        else:
            raise ValueError("Unsupported picture encoding")
        if flags != expected_flags:
            raise ValueError(f"Unsupported {encoding} picture flags: {flags:#x}")
        if not width or not height or width * height > 50_000_000 or not xres or not yres:
            raise ValueError("Invalid picture dimensions or resolution")
        size = (width + 2) * height
        cursor += 20
        if encoding == "raw":
            payload = data[cursor:cursor+size]
            cursor += size
        else:
            payload, cursor, _ = decompress7(data, cursor, max_output=size)
        if len(payload) != size:
            raise ValueError("Picture payload length is incorrect")
        for row in range(height):
            trailer = (row + 1) * (width + 2)
            if payload[trailer-2:trailer] != b"\0\xff":
                raise ValueError(f"Invalid picture row trailer at row {row}")
        formats.add(encoding)
        rasters += 1
    if len(formats) > 1:
        raise ValueError("Mixed raw/compressed picture encodings are not supported yet")
    if "raw" in formats:
        result, count = convert(data)
        if count != rasters:
            raise ValueError("Picture count changed during conversion")
        return PreparedJob(result, "raw", rasters, auto_start, title)
    return PreparedJob(data, "compressed" if rasters else "vector-only", rasters, auto_start, title)
