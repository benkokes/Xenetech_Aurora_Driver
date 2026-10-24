"""Create an asymmetric grayscale BMP for offline XP driver comparisons."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from tools.compare_preference_jobs import png_gray


def sample():
    width = height = 167
    pixels = bytearray([255]) * (width * height)
    def box(x, y, w, h, value):
        for row in range(y, y+h):
            pixels[row*width+x:row*width+x+w] = bytes([value]) * w
    # L, stepped wedge and separate markers distinguish flips, row order,
    # inversion, and whether the driver includes blank bitmap margins.
    box(12, 12, 12, 60, 0)
    box(12, 60, 52, 12, 0)
    for row in range(30):
        box(108, 18+row, row+1, 1, 0)
    for index, value in enumerate((255, 224, 192, 160, 128, 96, 64, 0)):
        box(12+index*18, 93, 18, 30, value)
    box(120, 142, 23, 9, 64)
    return width, height, bytes(pixels)


def bmp24(width, height, pixels, dpi=167):
    if len(pixels) != width * height:
        raise ValueError('Invalid bitmap dimensions')
    stride = (width*3 + 3) & ~3
    rows = []
    for y in range(height-1, -1, -1):
        row = b''.join(bytes([v, v, v]) for v in pixels[y*width:(y+1)*width])
        rows.append(row + bytes(stride-len(row)))
    body = b''.join(rows)
    ppm = round(dpi / .0254)
    return (b'BM' + struct.pack('<IHHI', 54+len(body), 0, 0, 54)
            + struct.pack('<IiiHHIIiiII', 40, width, height, 1, 24, 0, len(body), ppm, ppm, 0, 0) + body)


INSTRUCTIONS = """OFFLINE XP BITMAP PREFERENCES COMPARISON — PREPARED, NOT YET CAPTURED

Keep the laser OFF, XP's network cable disconnected and XP JobServer closed.
Keep the host JobServer in Capture only. This test collects files from the
original driver; it does not run the laser. No network change is needed.

1. In XP CorelDRAW 11, make a NEW 30 x 18 inch document. Import
   preferences-asymmetric-167.bmp. Set its width AND height to 1.000 inch,
   with rotation zero. Place it about 1 inch from the bed's left/top edges;
   exact placement is less important than keeping it identical in all cases.
   Do not use the older square-and-TEST document for these three captures.
   Save the new drawing before printing.
2. Use original Xenetech Properties: 167 DPI; Raster Only; raster 30 ips/45%;
   No Focus; Autostart off; Use Color Settings off; normal plate and engraving
   orientation; zero offsets; 30 x 18 inch plate. Advanced: Custom bitmap,
   Dither Bitmaps OFF, Manual Contrast OFF. Corel Layout: As in document/100%.
3. Both Invert Raster Output and Bottom-Up Engraving OFF: print ONCE, then
   immediately run xp-reference-collect-bitmap-baseline.cmd.
4. Change ONLY Invert Raster Output to ON: print ONCE, then immediately run
   xp-reference-collect-bitmap-invert.cmd. Turn Invert OFF again.
5. Change ONLY Bottom-Up Engraving to ON: print ONCE, then immediately run
   xp-reference-collect-bitmap-bottom-up.cmd.
6. Restore Bottom-Up OFF and Both Raster and Vector. Keep 167 DPI and the
   same power/speeds. Leave XP disconnected, JobServer closed, laser OFF.

Run each collector after its print, before Default.jbs can be overwritten.
Collectors only copy the watched inbox to separately labeled folders. Labels
record intended settings; actual job contents are checked independently.
If printing/copying fails, stop rather than printing a second copy.

The PNG is a visual reference. The BMP has eight grayscale levels, an L at
top-left, a triangle at top-right and a separate lower-right gray marker.
White margins and gaps are intentional. Import the BMP without tracing it.
This package has NOT been tested against XP output yet. Matching pixel flips
alone will not establish scan direction; origin commands and UL/LL matter too.
"""


def create(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    width, height, pixels = sample()
    bitmap = bmp24(width, height, pixels)
    (destination / 'preferences-asymmetric-167.bmp').write_bytes(bitmap)
    (destination / 'preferences-asymmetric-167.png').write_bytes(png_gray(width, height, pixels))
    (destination / 'BITMAP-PREFERENCES-READ-ME.txt').write_text(INSTRUCTIONS.replace('\n', '\r\n'), encoding='utf-8', newline='')
    template = (Path(__file__).parent / 'xp-output-mode-reference/xp-reference-collect-raster-only.cmd').read_text(encoding='ascii')
    for label in ('baseline', 'invert', 'bottom-up'):
        text = template.replace('output-raster-only-', f'bitmap-{label}-')
        text = text.replace('requested_output_mode=raster-only', f'requested_bitmap_case={label}')
        text = text.replace('the raster-only reference', f'the bitmap {label} reference')
        (destination / f'xp-reference-collect-bitmap-{label}.cmd').write_text(text.replace('\n', '\r\n'), encoding='ascii', newline='')
    result = {'state': 'prepared_for_offline_xp_comparison', 'width_pixels': width, 'height_pixels': height,
        'intended_size_inches': [1, 1], 'nominal_dpi': 167, 'gray_levels': sorted(set(pixels)),
        'bmp_sha256': hashlib.sha256(bitmap).hexdigest(), 'pixels_sha256': hashlib.sha256(pixels).hexdigest(),
        'xp_reference_captured': False, 'physical_device_io_performed': False}
    (destination / 'sample.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    print(json.dumps(create(args.destination), indent=2))


if __name__ == '__main__':
    main()
