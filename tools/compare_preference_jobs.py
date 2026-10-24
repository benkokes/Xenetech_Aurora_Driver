"""Compare raw/CG XP preference captures offline, including pure output modes.

Pixel flip/inversion matches describe stored samples only. They do not establish
controller scan direction, physical placement, or permission to deliver a job.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import zlib

from aurora_jobserver.jbs import DRAFT_MARKER, MAX_JOB_BYTES
from tools.raster_codec import decompress7, unpack7


NUMBER = r'-?\d+(?:\.\d*)?'
POINT = re.compile('(' + NUMBER + ') (' + NUMBER + ') V')
PROCESS = re.compile('(' + NUMBER + ') (speed|power|set_vppi|set_gspot)')
MAX_PIXELS = 50_000_000


def number(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('Non-finite numeric job command')
    return result


def png_gray(width, height, pixels):
    """Small dependency-free PNG writer for decoded diagnostic samples."""
    if width <= 0 or height <= 0 or len(pixels) != width * height:
        raise ValueError('Invalid grayscale image dimensions')
    def chunk(kind, payload):
        return (struct.pack('>I', len(payload)) + kind + payload
                + struct.pack('>I', zlib.crc32(kind + payload)))
    rows = b''.join(b'\0' + pixels[y*width:(y+1)*width] for y in range(height))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 0, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


def decode(data):
    if not data or len(data) > MAX_JOB_BYTES or not data.startswith(b'!ZX\r'):
        raise ValueError('Expected a bounded Xenetech JBS job')
    cursor = total_pixels = 0
    commands, rasters, paths = [], [], []
    position, drawing = None, None
    process = {}
    title = ''
    draft = ended = autostart = False
    while cursor < len(data):
        end = data.find(b'\r', cursor)
        if end < 0:
            if data[cursor:].strip():
                raise ValueError('Unterminated job command')
            break
        line = data[cursor:end].strip()
        cursor = end + 1
        if not line:
            continue
        if ended:
            raise ValueError('Content follows END_PLOT')
        if len(commands) >= 100_000:
            raise ValueError('Too many commands for a preference comparison')
        try:
            token = line.decode('ascii')
        except UnicodeError as error:
            raise ValueError('Binary data outside a supported picture') from error
        if any(ord(c) < 32 for c in token):
            raise ValueError('Control data outside a supported picture')
        if line == DRAFT_MARKER:
            draft = True
            continue
        if token.startswith('JOB '):
            title = token[4:]
            continue
        commands.append(token)
        if token in ('PICT-UL', 'PICT-LL'):
            if drawing is not None or position is None:
                raise ValueError('Picture needs a pen-up origin')
            if cursor + 20 > len(data):
                raise ValueError('Truncated picture header')
            magic = data[cursor:cursor+2]
            if magic == b'\xc3\x58':
                _, w, h, xr, yr, flags = struct.unpack_from('<HIIIIH', data, cursor)
                encoding, expected_flags = 'raw', 0x41
            elif magic == b'cG':
                w, h, xr, yr = [unpack7(data[cursor+i:cursor+i+4]) for i in (2, 6, 10, 14)]
                flags = unpack7(data[cursor+18:cursor+20])
                encoding, expected_flags = 'compressed', 0xc1
            else:
                raise ValueError('Unsupported picture encoding')
            total_pixels += w * h
            if not w or not h or not xr or not yr or flags != expected_flags or total_pixels > MAX_PIXELS:
                raise ValueError('Unsupported picture dimensions, resolution or flags')
            cursor += 20
            size = (w + 2) * h
            if encoding == 'raw':
                payload = data[cursor:cursor+size]
                cursor += size
            else:
                payload, cursor, _ = decompress7(data, cursor, max_output=size)
            if len(payload) != size:
                raise ValueError('Truncated picture payload')
            pixels = bytearray()
            for y in range(h):
                row = payload[y*(w+2):(y+1)*(w+2)]
                if row[-2:] != b'\0\xff':
                    raise ValueError('Invalid picture row trailer')
                pixels.extend(row[:-2][::-1] if y % 2 else row[:-2])
            pixels = bytes(pixels)
            histogram = Counter(pixels)
            rasters.append({'width': w, 'height': h, 'resolution_fields': [xr, yr],
                'resolution_dpi': [xr / (1000 if encoding == 'compressed' else 1),
                                   yr / (1000 if encoding == 'compressed' else 1)],
                'origin_label': token[5:], 'origin_units': list(position), 'encoding': encoding,
                'settings': dict(process), 'pixels_sha256': hashlib.sha256(pixels).hexdigest(),
                'signal_histogram': dict(sorted(histogram.items())), 'pixels': pixels})
        elif token.startswith('PICT'):
            raise ValueError('Unsupported picture command')
        elif token == 'PD':
            if drawing is not None or position is None:
                raise ValueError('Invalid vector pen transition')
            drawing = {'points': [list(position)], 'settings': dict(process)}
        elif token == 'PU':
            if drawing is not None:
                if len(drawing['points']) < 2:
                    raise ValueError('Empty vector path')
                paths.append(drawing)
                drawing = None
        elif token == 'END_PLOT':
            if drawing is not None:
                raise ValueError('Unfinished vector path')
            ended = True
        elif token == 'autostart START':
            autostart = True
        elif POINT.fullmatch(token):
            position = [number(v) for v in POINT.fullmatch(token).groups()]
            if drawing is not None:
                drawing['points'].append(list(position))
        elif PROCESS.fullmatch(token):
            value, name = PROCESS.fullmatch(token).groups()
            process[name] = number(value)
    if not ended:
        raise ValueError('Missing END_PLOT')
    return {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'title': title,
            'draft': draft, 'autostart': autostart, 'commands': commands,
            'rasters': rasters, 'vector_paths': paths}


def summary(job):
    return {**job, 'rasters': [{k: v for k, v in raster.items() if k != 'pixels'} for raster in job['rasters']]}


def pixel_matches(reference, candidate):
    if (reference['width'], reference['height']) != (candidate['width'], candidate['height']):
        return {'same_dimensions': False, 'pixel_transform_matches': [], 'mismatched_pixels': None}
    w, h = reference['width'], reference['height']
    source, target = reference['pixels'], candidate['pixels']
    matches = []
    invert = bytes(255-i for i in range(256))
    for flip_y, flip_x, label in ((False, False, 'identity'), (False, True, 'horizontal_flip'),
                                  (True, False, 'vertical_flip'), (True, True, 'rotate_180')):
        rows = range(h-1, -1, -1) if flip_y else range(h)
        transformed = b''.join(source[y*w:(y+1)*w][::-1] if flip_x else source[y*w:(y+1)*w] for y in rows)
        if transformed == target:
            matches.append(label)
        if transformed.translate(invert) == target:
            matches.append(label + '_and_invert')
    return {'same_dimensions': True, 'pixel_transform_matches': matches,
            'mismatched_pixels': sum(a != b for a, b in zip(source, target)),
            'mean_absolute_signal_error': sum(abs(a-b) for a, b in zip(source, target)) / len(source)}


def compare(reference, candidate, destination):
    reference, candidate, destination = Path(reference), Path(candidate), Path(destination)
    # Decode both before creating output, so invalid input cannot leave a partial report.
    jobs = []
    for source in (reference, candidate):
        with source.open('rb') as stream:
            jobs.append(decode(stream.read(MAX_JOB_BYTES + 1)))
    destination.mkdir(parents=True, exist_ok=False)
    for label, job in zip(('reference', 'candidate'), jobs):
        for index, raster in enumerate(job['rasters'], 1):
            # Display zero signal as white; stored row order and UL/LL are kept separate.
            preview = raster['pixels'].translate(bytes(255-i for i in range(256)))
            (destination / f'{label}-raster-{index:02d}.png').write_bytes(png_gray(raster['width'], raster['height'], preview))
    r, c = jobs
    pairs = []
    for index, (a, b) in enumerate(zip(r['rasters'], c['rasters']), 1):
        pairs.append({'index': index, **pixel_matches(a, b),
            'origin_candidate_minus_reference': [y-x for x, y in zip(a['origin_units'], b['origin_units'])],
            'origin_labels_equal': a['origin_label'] == b['origin_label'],
            'resolution_fields_equal': a['resolution_fields'] == b['resolution_fields'],
            'resolution_dpi_equal': a['resolution_dpi'] == b['resolution_dpi'],
            'settings_equal': a['settings'] == b['settings']})
    result = {'schema_version': 1, 'reference_path': str(reference), 'candidate_path': str(candidate),
        'reference': summary(r), 'candidate': summary(c), 'raster_counts_equal': len(r['rasters']) == len(c['rasters']),
        'vector_path_counts_equal': len(r['vector_paths']) == len(c['vector_paths']),
        'vector_geometry_equal': [p['points'] for p in r['vector_paths']] == [p['points'] for p in c['vector_paths']],
        'vector_processes_equal': [p['settings'] for p in r['vector_paths']] == [p['settings'] for p in c['vector_paths']],
        'normalized_text_commands_equal': r['commands'] == c['commands'], 'autostart_equal': r['autostart'] == c['autostart'],
        'raster_pairs_by_capture_order': pairs,
        'interpretation': 'Comparison only. Raster pairs follow capture order. Pixel transforms do not infer physical scan direction or resolve UL/LL placement. No delivery authorization.'}
    (destination / 'comparison.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    result = compare(args.reference, args.candidate, args.destination)
    print(json.dumps({k: v for k, v in result.items() if k not in ('reference', 'candidate')}, indent=2))


if __name__ == '__main__':
    main()
