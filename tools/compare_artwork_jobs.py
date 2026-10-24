"""Compare one-raster flatbed raw JBS captures offline, without device I/O."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

from tools.inspect_job import inspect
from aurora_jobserver.jbs import DRAFT_MARKER


COORD = re.compile(r'(-?\d+(?:\.\d*)?) (-?\d+(?:\.\d*)?) V')


def last_number(text, command):
    values = re.findall(r'(?m)(?:^|\r)(-?\d+(?:\.\d*)?) ' + re.escape(command) + r'(?:\r|$)', text)
    if not values:
        raise ValueError('Missing command: ' + command)
    return float(values[-1])


def facts(source, directory):
    directory.mkdir()
    result = inspect(source, directory)
    if result['status'] != 'raw_rasters_decoded' or len(result['rasters']) != 1:
        raise ValueError('Comparison requires exactly one validated raw C358 raster per job')
    raster = result['rasters'][0]
    prefix, tail = [s['text'] for s in result['text_segments']]
    origins = [COORD.fullmatch(s) for s in prefix.split('\r')]
    origins = [m for m in origins if m]
    if not origins:
        raise ValueError('Missing raster origin')
    paths = []
    pen = False
    position = None
    for token in tail.split('\r'):
        match = COORD.fullmatch(token)
        if token == 'PD':
            if position is None or pen:
                raise ValueError('Invalid vector pen transition')
            paths.append([position])
            pen = True
        elif token == 'PU':
            pen = False
        elif match:
            position = [float(v) for v in match.groups()]
            if pen:
                paths[-1].append(position)
    if not paths or any(len(p) < 2 for p in paths):
        raise ValueError('No valid vector paths to compare')
    data = source.read_bytes()
    pixels = bytearray()
    w, h = raster['width'], raster['height']
    for y in range(h):
        start = raster['pixel_offset'] + y * (w + 2)
        row = data[start:start+w]
        pixels.extend(row[::-1] if y % 2 else row)
    histogram = Counter(pixels)
    summary = {
        'source': str(source), 'sha256': result['sha256'], 'bytes': result['size'],
        'auto_start': 'autostart START' in prefix,
        'commands': {'initialization': re.sub(r'JOB [^\r]*\r', '', prefix.replace(DRAFT_MARKER.decode()+'\r','')),
                     'vectors': tail},
        'settings': {'raster_speed': last_number(prefix, 'speed'), 'raster_power': last_number(prefix, 'power'),
                     'vector_speed': last_number(tail, 'speed'), 'vector_power': last_number(tail, 'power'),
                     'vector_ppi': last_number(tail, 'set_vppi')},
        'raster': {'width': w, 'height': h, 'origin_units': [float(v) for v in origins[-1].groups()],
                   'resolution_fields': [raster['x_resolution_field'], raster['y_resolution_field']],
                   'pixels_sha256': raster['pixels_sha256'], 'signal_levels': len(histogram),
                   'nonzero_pixels': sum(count for level, count in histogram.items() if level),
                   'total_exposure': sum(level * count for level, count in histogram.items())},
        'vector_paths': paths,
        'vector_bounds': [[min(p[0] for p in path), min(p[1] for p in path),
                           max(p[0] for p in path), max(p[1] for p in path)] for path in paths],
    }
    return summary, pixels


def compare(reference, candidate, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    ref, rp = facts(Path(reference), destination / 'reference')
    test, tp = facts(Path(candidate), destination / 'candidate')
    r, t = ref['raster'], test['raster']
    mismatches = difference = 0
    width, height = max(r['width'], t['width']), max(r['height'], t['height'])
    # Align cropped top-left pixels, padding missing samples with zero exposure.
    # This metric deliberately does not hide absolute placement differences.
    for y in range(height):
        for x in range(width):
            a = rp[y*r['width']+x] if x < r['width'] and y < r['height'] else 0
            b = tp[y*t['width']+x] if x < t['width'] and y < t['height'] else 0
            mismatches += a != b
            difference += abs(a-b)
    vectors = []
    for a, b in zip(ref['vector_bounds'], test['vector_bounds']):
        vectors.append({'reference_size': [a[2]-a[0], a[3]-a[1]],
                        'candidate_size': [b[2]-b[0], b[3]-b[1]],
                        'candidate_minus_reference_origin': [b[0]-a[0], b[1]-a[1]]})
    result = {
        'schema_version': 1, 'reference': ref, 'candidate': test,
        'settings_equal': ref['settings'] == test['settings'],
        'initialization_commands_equal': ref['commands']['initialization'] == test['commands']['initialization'],
        'vector_commands_equal': ref['commands']['vectors'] == test['commands']['vectors'],
        'vector_paths_equal': ref['vector_paths'] == test['vector_paths'],
        'vector_path_counts_equal': len(ref['vector_paths']) == len(test['vector_paths']),
        'vectors': vectors,
        'raster_candidate_minus_reference_origin': [b-a for a, b in zip(r['origin_units'], t['origin_units'])],
        'raster_pixels_exact': r['width'] == t['width'] and r['height'] == t['height'] and rp == tp,
        'crop_top_left_comparison': {'mismatched_pixels': mismatches, 'sample_count': width*height,
                                     'mean_absolute_signal_error': difference/(width*height)},
        'validation': 'comparison_only; no calibration or send authorization',
    }
    (destination / 'comparison.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    result = compare(args.reference, args.candidate, args.destination)
    print(json.dumps({k: v for k, v in result.items() if k not in ('reference','candidate')}, indent=2))


if __name__ == '__main__':
    main()
