"""Compare the single embedded bitmap in a real capture with its source pixels.

This reads existing files only. It does not render, print, modify tickets or
contact equipment. Reports are exclusive-created so earlier evidence survives.
"""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import zipfile

from PIL import Image


def audit(source, original):
    source, original = Path(source), Path(original)
    with Image.open(original) as image:
        expected = image.convert('RGB')
    with zipfile.ZipFile(source) as package:
        names = [name for name in package.namelist() if '/Resources/Images/' in name]
        if len(names) != 1:
            raise ValueError('Expected the single-bitmap calibration drawing')
        with Image.open(BytesIO(package.read(names[0]))) as image:
            image_format = image.format
            captured = image.convert('RGB')
    same_size = captured.size == expected.size
    differences = (sum(a != b for a, b in zip(expected.get_flattened_data(), captured.get_flattened_data()))
                   if same_size else None)
    passed = image_format == 'PNG' and same_size and differences == 0
    return {
        'state': 'passed' if passed else 'failed',
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'original_sha256': hashlib.sha256(original.read_bytes()).hexdigest(),
        'image_part': names[0], 'image_format': image_format,
        'original_size': list(expected.size), 'captured_size': list(captured.size),
        'original_colors': len(set(expected.get_flattened_data())),
        'captured_colors': len(set(captured.get_flattened_data())),
        'different_pixels': differences, 'physical_device_io': False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('original', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Choose a fresh report path')
    result = audit(args.source, args.original)
    with args.report.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result, indent=2))
    return 0 if result['state'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
