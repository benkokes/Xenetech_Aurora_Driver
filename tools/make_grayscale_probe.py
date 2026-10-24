"""Create lossless, full-range offline contrast/dither reference artwork."""
import argparse
import hashlib
import json
from pathlib import Path

from tools.make_preferences_sample import bmp24
from tools.compare_preference_jobs import png_gray


def create(destination):
    destination = Path(destination)
    destination.mkdir(exist_ok=False, parents=True)
    width, height = 668, 334
    pixels = bytearray([255]) * (width * height)

    def box(x, y, w, h, value):
        for row in range(y, y + h):
            pixels[row * width + x:row * width + x + w] = bytes([value]) * w

    for level in range(256):
        box(8 + (level % 16) * 16, 8 + (level // 16) * 16, 16, 16, level)
        box(340 + (level % 16) * 16, 9 + (level // 16) * 16, 16, 16, 255 - level)
        box(8 + level * 2, 290, 2, 32, level)
    box(630, 8, 8, 52, 0)
    box(630, 52, 28, 8, 0)
    for level in range(16):
        box(542 + (level % 4) * 24, 282 + (level // 4) * 10, 24, 10, level * 17)
    data = bytes(pixels)
    bitmap = bmp24(width, height, data)
    (destination / 'grayscale-probe.bmp').write_bytes(bitmap)
    (destination / 'grayscale-probe.png').write_bytes(png_gray(width, height, data))
    result = {'state': 'prepared_not_printed', 'nominal_dpi': 167,
              'size_pixels': [width, height], 'size_inches': [4, 2],
              'gray_levels': sorted(set(data)), 'physical_device_io': False,
              'bmp_sha256': hashlib.sha256(bitmap).hexdigest(),
              'pixels_sha256': hashlib.sha256(data).hexdigest(),
              'patches': 'Two 16x16 grids of 16-pixel patches, reversed order; second grid shifted one row; 256-level horizontal ramp and asymmetric black anchor.'}
    (destination / 'sample.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    print(json.dumps(create(args.destination), indent=2))
