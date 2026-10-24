"""Bounded, seeded raster/codec/draft-guard checks with all socket use denied.

This is robustness testing, not independent XP or physical calibration evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import time
import traceback
from unittest.mock import patch

from aurora_jobserver.artwork import Scene, ProcessSettings, encode
from aurora_jobserver.corel_layout import COREL_GRID
from aurora_jobserver.jbs import prepare
from aurora_jobserver.wire import raster_plan
from tools.compare_preference_jobs import decode


SHAPES = ((1, 1), (1, 257), (257, 1), (2, 3), (3, 2), (7, 9), (16, 17), (255, 33), (256, 65), (511, 129))
PATTERNS = ('constant', 'ramp', 'checker', 'sparse', 'random', 'command_bytes')


def must_reject(action):
    try:
        action()
    except ValueError:
        return
    raise AssertionError('Malformed input or draft guard unexpectedly accepted a job')


def run(destination, *, cases=1200, seed=20261018, max_seconds=7200):
    if not 1 <= cases <= 100_000 or not 1 <= max_seconds <= 8*3600:
        raise ValueError('Campaign bounds are invalid')
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    rng = random.Random(seed)
    started = time.monotonic()
    coverage = {'shapes': set(), 'patterns': set(), 'modes': set(), 'dpi': set()}
    combinations = set()
    digest = hashlib.sha256()
    report = {'state': 'running', 'seed': seed, 'requested_cases': cases, 'completed_cases': 0,
              'malformed_inputs_rejected': 0, 'draft_guards_checked': 0, 'raw_cg_decodes': 0,
              'physical_device_io_performed': False, 'socket_calls_permitted': False}
    def checkpoint():
        report['elapsed_seconds'] = round(time.monotonic()-started, 3)
        report['coverage'] = {key: sorted(value) for key, value in coverage.items()}
        report['shape_pattern_mode_dpi_combinations'] = len(combinations)
        report['job_stream_sha256'] = digest.hexdigest()
        temporary = destination/'progress.tmp'
        temporary.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        temporary.replace(destination/'progress.json')
    checkpoint()
    raw = cg = b''
    with patch('socket.socket', side_effect=AssertionError('Offline campaign forbids sockets')), patch(
            'socket.create_connection', side_effect=AssertionError('Offline campaign forbids connections')):
        try:
            for case in range(cases):
                if time.monotonic()-started >= max_seconds:
                    report['state'] = 'time_bound_reached'
                    break
                w, h = SHAPES[case % len(SHAPES)]
                pattern = PATTERNS[(case // len(SHAPES)) % len(PATTERNS)]
                size = w*h
                if pattern == 'constant': pixels = bytes([rng.randrange(256)]) * size
                elif pattern == 'ramp': pixels = bytes(range(256)) * (size//256) + bytes(range(size%256))
                elif pattern == 'checker': pixels = bytes(255 if ((i//w) + i%w) % 2 else 0 for i in range(size))
                elif pattern == 'sparse':
                    data = bytearray(size)
                    for _ in range(max(1, size//100)): data[rng.randrange(size)] = rng.randrange(1, 256)
                    pixels = bytes(data)
                elif pattern == 'random': pixels = rng.randbytes(size)
                else:
                    token = b'PD\rPU\rPICT-UL\rEND_PLOT\r\xc3\x58\0\xff'
                    pixels = (token*((size+len(token)-1)//len(token)))[:size]
                # First 360 cases exhaust shape x pattern x mode x DPI; later
                # passes vary independently seeded pixels/process settings.
                mode = ('raster-and-vector', 'raster-only', 'vector-only')[(case // 60) % 3]
                dpi = (100, 167)[(case // 180) % 2]
                x, y = rng.randrange(5, 100), rng.randrange(5, 100)
                paths = (((123, 456), (789, 456), (789, 900), (123, 456)),)
                scene = Scene({'dpi': dpi, 'raster_grid': COREL_GRID, 'text_rendering': 'outline-aliased'},
                              {'exposure': {'width': w, 'height': h, 'x_pixels': x, 'y_pixels': y}}, pixels, paths)
                settings = ProcessSettings.parse({'schema_version': 1, 'units': 'driver-native',
                    'raster_speed_native': rng.randrange(1, 31001), 'raster_power_percent': rng.randrange(10001)/100,
                    'vector_speed_native': rng.randrange(1, 15001), 'vector_power_percent': rng.randrange(10001)/100,
                    'vector_ppi': rng.randrange(5, 1001)})
                raw, cg = encode(scene, settings, f'Offline_{seed}_{case}', output_mode=mode)
                digest.update(raw); digest.update(cg)
                a, b = decode(raw), decode(cg)
                report['raw_cg_decodes'] += 2
                if a['commands'] != b['commands'] or a['vector_paths'] != b['vector_paths']:
                    raise AssertionError('Raw/compressed commands or vector paths differ')
                if len(a['rasters']) != (0 if mode == 'vector-only' else 1):
                    raise AssertionError('Raster output-mode filtering failed')
                if len(a['vector_paths']) != (0 if mode == 'raster-only' else 1):
                    raise AssertionError('Vector output-mode filtering failed')
                if a['vector_paths'] and a['vector_paths'][0]['points'] != [list(p) for p in paths[0]]:
                    raise AssertionError('Vector geometry changed')
                for raster in a['rasters'] + b['rasters']:
                    if raster['pixels'] != pixels or raster['resolution_dpi'] != [dpi, dpi]:
                        raise AssertionError('Decoded samples or resolution differ from independent source')
                    pitch = 10 if dpi == 100 else 6
                    if raster['origin_units'] != [x*pitch, y*pitch]:
                        raise AssertionError('Raster origin changed')
                must_reject(lambda: prepare(raw))
                must_reject(lambda: raster_plan(cg, r'c:\xfiles\jbs\Convert\Default.jbs'))
                report['draft_guards_checked'] += 2
                must_reject(lambda: decode(raw[:-10]))
                must_reject(lambda: decode(raw+b'PD\r'))
                report['malformed_inputs_rejected'] += 2
                if a['rasters']:
                    offset = cg.index(b'PICT-UL\r') + 8
                    corrupt = bytearray(cg); corrupt[offset+2] |= 0x80
                    must_reject(lambda: decode(bytes(corrupt)))
                    corrupt = bytearray(cg); corrupt[offset+20] |= 0x80
                    must_reject(lambda: decode(bytes(corrupt)))
                    report['malformed_inputs_rejected'] += 2
                coverage['shapes'].add(f'{w}x{h}'); coverage['patterns'].add(pattern)
                coverage['modes'].add(mode); coverage['dpi'].add(dpi)
                combinations.add((w, h, pattern, mode, dpi))
                report['completed_cases'] = case+1
                if (case+1) % 25 == 0: checkpoint()
            else:
                report['state'] = 'complete'
        except Exception:
            report['state'] = 'failed'
            report['error'] = traceback.format_exc()
            (destination/'failing.raw.jbs.draft').write_bytes(raw)
            (destination/'failing.cg.jbs.draft').write_bytes(cg)
        finally:
            checkpoint()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--cases', type=int, default=1200)
    parser.add_argument('--seed', type=int, default=20261018)
    parser.add_argument('--max-seconds', type=float, default=7200)
    args = parser.parse_args()
    result = run(args.destination, cases=args.cases, seed=args.seed, max_seconds=args.max_seconds)
    print(json.dumps(result, indent=2))
    return 1 if result['state'] == 'failed' else 0


if __name__ == '__main__':
    raise SystemExit(main())
