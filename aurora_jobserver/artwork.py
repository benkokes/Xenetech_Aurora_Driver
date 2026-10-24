"""Offline artwork-to-JBS drafts for the observed flatbed raster/vector dialect.

These drafts require XP comparison and physical calibration. The marker blocks
ordinary queue preparation and wire-plan construction. No device I/O occurs.
"""
import argparse
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import math
from pathlib import Path
import re
import struct

from .jbs import DRAFT_MARKER, prepare
from .corel_layout import COREL_GRID, from_manifest


GRID = 'aurora-167-6mil-draft'
XP_GRID = 'xp-167-6mil-draft'
UNITS_PER_INCH = Decimal(1000)  # Static inference; not yet physically calibrated.
MM_PER_INCH = Decimal('25.4')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def number(value, label, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'Invalid {label}')
    return value


def integer(value, label, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'Invalid {label}')
    return value


def read_json(path):
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('JSON input exceeds 32 MiB')
    def reject(value):
        raise ValueError(f'Nonfinite JSON number: {value}')
    return json.loads(path.read_text(encoding='utf-8'), parse_constant=reject)


def local_file(root, name):
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+', name) or name in ('.', '..'):
        raise ValueError('Expected a local artifact filename')
    path = (root / name).resolve()
    if path.parent != root:
        raise ValueError('Artifact path leaves its document directory')
    return path


def units(mm, grid=GRID):
    if grid == XP_GRID:
        # XP receives 28.4 device coordinates at nominal 167 DPI, multiplies by
        # six, then rounds to integer job units (Drv coordinate helper 406490).
        fixed = (Decimal(str(mm)) * 167 * 16 / MM_PER_INCH).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        return Decimal((int(fixed) * 6 + 8) // 16)
    return (Decimal(str(mm)) * UNITS_PER_INCH / MM_PER_INCH).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ProcessSettings:
    raster_speed_native: int
    raster_power_percent: Decimal
    vector_speed_native: int
    vector_power_percent: Decimal
    vector_ppi: int

    @classmethod
    def parse(cls, value):
        if not isinstance(value, dict) or value.get('schema_version') != 1:
            raise ValueError('Expected explicit version-1 process settings')
        base = {'schema_version', 'units', 'raster_power_percent', 'vector_power_percent', 'vector_ppi'}
        if value.get('units') == 'driver-native' and set(value) == base | {'raster_speed_native', 'vector_speed_native'}:
            raster_speed = integer(value['raster_speed_native'], 'raster speed', 1, 31000)
            vector_speed = integer(value['vector_speed_native'], 'vector speed', 1, 31000)
        elif value.get('units') == 'inches-per-second' and set(value) == base | {'raster_speed_ips', 'vector_speed_ips'}:
            speeds = []
            for key in ('raster_speed_ips', 'vector_speed_ips'):
                speed = Decimal(str(number(value[key], key, 0.001, 31))) * 1000
                if speed != speed.to_integral_value():
                    raise ValueError('Speed supports increments of 0.001 inches/second')
                speeds.append(int(speed))
            raster_speed, vector_speed = speeds
        else:
            raise ValueError('Expected explicit driver-native or inches-per-second process settings')
        ppi = integer(value['vector_ppi'], 'vector PPI', 1, 10000)
        powers = []
        for key in ('raster_power_percent', 'vector_power_percent'):
            power = Decimal(str(number(value[key], key, 0, 100)))
            if power != power.quantize(Decimal('0.01')):
                raise ValueError('Power must have at most two decimal places')
            powers.append(power)
        return cls(raster_speed, powers[0], vector_speed, powers[1], ppi)


@dataclass(frozen=True)
class Scene:
    manifest: dict
    page: dict
    exposure: bytes
    paths: tuple

    @property
    def pitch(self):
        return 10 if self.manifest['dpi'] == 100 else 6

    def geometry(self):
        raster = self.page['exposure']
        return {
            'schema_version': 1, 'validation': 'uncalibrated_draft',
            'source_sha256': self.manifest['source_sha256'],
            'coordinate_inference': ('Corel X7 to XP 11 reference placement fit; pixel rounding and XP surface mapping; physical scale uncalibrated'
                                     if self.manifest['raster_grid'] == COREL_GRID else
                                     'XP nominal 167 DPI times six, 28.4 device-coordinate rounding; application placement and physical scale uncalibrated'
                                     if self.manifest['raster_grid'] == XP_GRID else
                                     '1000 job units per inch, x right, y down; requires XP and physical comparison'),
            'raster_grid': self.manifest['raster_grid'], 'raster_pixel_pitch_units': self.pitch,
            'dpi': self.manifest['dpi'],
            'corel_xp_compatibility': self.manifest.get('corel_xp_compatibility'),
            'text_rendering': self.manifest.get('text_rendering', 'auto'),
            'page_mm': [self.page['width_mm'], self.page['height_mm']],
            'raster': None if raster is None else {
                'width': raster['width'], 'height': raster['height'],
                'origin_units': [raster['x_pixels'] * self.pitch, raster['y_pixels'] * self.pitch],
                'exposure_sha256': sha(self.exposure),
            },
            'paths_units': [[[float(x), float(y)] for x, y in path] for path in self.paths],
        }


def load_scene(directory, *, allow_empty_cut_paths=False):
    root = Path(directory).resolve()
    doc = read_json(root / 'document.json')
    grid = doc.get('raster_grid')
    if doc.get('schema_version') != 2 or grid not in (GRID, XP_GRID, COREL_GRID) or (grid != COREL_GRID and doc.get('dpi') != 167):
        raise ValueError('Rebuild intake with schema 2 and an explicit Aurora/XP draft raster grid')
    if doc.get('text_rendering', 'auto') not in ('auto', 'outline-aliased'):
        raise ValueError('Unsupported text rendering provenance')
    if grid == COREL_GRID and (type(doc.get('dpi')) is not int or doc['dpi'] not in (100, 167)):
        raise ValueError('Corel reference raster supports only 100 and 167 DPI')
    render_dpi = doc['dpi'] if grid in (XP_GRID, COREL_GRID) else 1000 / 6
    if not math.isclose(number(doc.get('render_dpi'), 'render DPI', 1, 1200), render_dpi, rel_tol=0, abs_tol=1e-8):
        raise ValueError('The raster sampling rate does not match its grid profile')
    source = local_file(root, doc.get('source_file'))
    if source.stat().st_size > 64 * 1024 * 1024 or sha(source.read_bytes()) != doc.get('source_sha256'):
        raise ValueError('Source snapshot integrity check failed')
    pages = doc.get('pages')
    if not isinstance(pages, list) or len(pages) != 1:
        raise ValueError('Draft encoding currently requires exactly one page')
    page = pages[0]
    empty_cut_page=(allow_empty_cut_paths and doc.get('cut_paths_only') is True
                    and page.get('has_visible_artwork') is False
                    and page.get('exposure') is None and page.get('cuts')==[])
    if page.get('review_reasons') != [] or (page.get('has_visible_artwork') is not True and not empty_cut_page):
        raise ValueError('Blank pages or unresolved review reasons cannot be encoded')
    width = number(page.get('width_mm'), 'page width', 0.001, 762)
    height = number(page.get('height_mm'), 'page height', 0.001, 457.2)
    layout = from_manifest(doc, page) if grid == COREL_GRID else None
    expected = layout.surface if layout else (math.ceil(width / 25.4 * render_dpi - 1e-9), math.ceil(height / 25.4 * render_dpi - 1e-9))
    pixels_x = integer(page.get('pixel_width'), 'pixel width', 1, 5010 if grid == XP_GRID else 5000)
    pixels_y = integer(page.get('pixel_height'), 'pixel height', 1, 3006 if grid == XP_GRID else 3000)
    if (pixels_x, pixels_y) != expected:
        raise ValueError('Raster size does not match page size and grid')
    raster = page.get('exposure')
    exposure = b''
    if raster is not None:
        if raster.get('encoding') != 'exposure-u8-row-major' or raster.get('colored_pixels') != 0:
            raise ValueError('First draft supports neutral grayscale engraving only')
        rw = integer(raster.get('width'), 'exposure width', 1, pixels_x)
        rh = integer(raster.get('height'), 'exposure height', 1, pixels_y)
        x = integer(raster.get('x_pixels'), 'exposure X offset', 0, pixels_x - rw)
        y = integer(raster.get('y_pixels'), 'exposure Y offset', 0, pixels_y - rh)
        if (x + rw) > width / 25.4 * render_dpi + 1e-6 or (y + rh) > height / 25.4 * render_dpi + 1e-6:
            raise ValueError('Exposure pixels extend past the page boundary')
        path = local_file(root, raster.get('file'))
        if path.stat().st_size != rw * rh:
            raise ValueError('Exposure length does not match dimensions')
        exposure = path.read_bytes()
        if sha(exposure) != raster.get('sha256') or not any(exposure):
            raise ValueError('Exposure integrity check failed or exposure is empty')
    paths = []
    point_count = 0
    cuts = page.get('cuts')
    if not isinstance(cuts, list):
        raise ValueError('Invalid cutting paths')
    for cut in cuts:
        points = cut.get('points_mm')
        if not isinstance(points, list) or len(points) < 2 or type(cut.get('closed')) is not bool:
            raise ValueError('Invalid cutting path')
        point_count += len(points)
        if point_count > 2000000:
            raise ValueError('Too many vector points')
        path = []
        for point in points:
            if not isinstance(point, list) or len(point) != 2:
                raise ValueError('Invalid cutting point')
            x, y = number(point[0], 'cut X', 0, width), number(point[1], 'cut Y', 0, height)
            path.append((layout.point(x, 0), layout.point(y, 1)) if layout else (units(x, grid), units(y, grid)))
        if cut['closed'] and path[-1] != path[0]:
            path.append(path[0])
        if len(set(path)) < 2:
            raise ValueError('Cutting path collapses after coordinate rounding')
        paths.append(tuple(path))
    if not paths and not exposure and not empty_cut_page:
        raise ValueError('No engraving or cutting content')
    return Scene(doc, page, exposure, tuple(paths))


OUTPUT_MODES = ('raster-and-vector', 'raster-only', 'vector-only')
RASTER_INVERT_TABLE = bytes(range(255,-1,-1))


def encode(scene, settings, title='ArtworkDraft', *, output_mode='raster-and-vector',
           invert_raster=False, bottom_up=False):
    return _encode(scene, settings, title, draft=True, output_mode=output_mode,
                   invert_raster=invert_raster, bottom_up=bottom_up)


def _encode(scene, settings, title, *, draft, autostart=False, output_mode='raster-and-vector',
            invert_raster=False, bottom_up=False):
    # Production artwork remains blocked. The separate, constrained calibration
    # staging tool may build the one reviewed reference as a measurement job.
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', title):
        raise ValueError('Draft title must be 1-64 ASCII letters, digits, dots, underscores or hyphens')
    if type(autostart) is not bool:
        raise ValueError('Autostart must be an explicit boolean')
    if output_mode not in OUTPUT_MODES:
        raise ValueError('Unknown laser output mode')
    if type(invert_raster) is not bool or type(bottom_up) is not bool:
        raise ValueError('Raster inversion and Bottom-Up must be explicit booleans')
    if (invert_raster or bottom_up) and scene.manifest['dpi'] != 167:
        raise ValueError('Raster inversion and Bottom-Up are verified only at 167 DPI')
    raster = scene.page['exposure'] if output_mode != 'vector-only' else None
    paths = scene.paths if output_mode != 'raster-only' else ()
    if raster is None and not paths:
        raise ValueError('Selected output mode contains no engraving or cutting content')
    pitch, dpi = scene.pitch, scene.manifest['dpi']
    header = (b'!ZX\r' + (DRAFT_MARKER + b'\r' if draft else b'') + f'JOB {title}\n\r'.encode()
              + f'1 set_binary\r1 == ?REPLAY\r{pitch:.3f} set_gspot\r'.encode()
              + (b'autostart START\r' if autostart else b'normalstart START\r')
              + b'0 set_rotary\r100. set_xyup_feed\r0 PMC\r40 PWF\r')
    out = bytearray(header)
    if raster is not None:
        w, h = raster['width'], raster['height']
        start_y = raster['y_pixels'] + (h-1 if bottom_up else 0)
        origin = 'LL' if bottom_up else 'UL'
        out.extend(f'{settings.raster_speed_native}. speed\r{settings.raster_power_percent:.2f} power\r'.encode())
        out.extend(f'PU\r2 RA\r{raster["x_pixels"] * pitch}.0 {start_y * pitch}.0 V\r{pitch:.3f} set_gspot\rPICT-{origin}\r'.encode())
        out.extend(struct.pack('<HIIIIH', 0x58c3, w, h, dpi, dpi, 0x41))
        for y in range(h):
            source_y = h-1-y if bottom_up else y
            row = scene.exposure[source_y*w:(source_y+1)*w]
            if invert_raster:
                row = row.translate(RASTER_INVERT_TABLE)
            # Alternation follows emitted row order, including when height is
            # even and the original bottom row had opposite scan parity.
            out.extend(row[::-1] if y % 2 else row)
            out.extend(b'\0\xff')
    if paths:
        out.extend(f'{settings.vector_speed_native}. speed\r{settings.vector_power_percent:.2f} power\r{settings.vector_ppi}. set_vppi\r'.encode())
        for index, path in enumerate(paths):
            x, y = path[0]
            # In global mode each preceding path already ended in PU / 2 RA.
            # XP emits that setup once between paths, not twice (color mode
            # has different framing, modeled separately in color_vectors).
            if index == 0:
                out.extend(b'PU\r2 RA\r')
            out.extend(f'{x:.1f} {y:.1f} V\r1 RA\rPD\r'.encode())
            for x, y in path[1:]:
                out.extend(f'{x:.1f} {y:.1f} V\r'.encode())
            out.extend(b'PU\r2 RA\r')
    out.extend(b'PU\r0. 0. V\rEND_PLOT\r')
    raw = bytes(out)
    prepared = prepare(raw, allow_draft=draft)
    if prepared.auto_start != autostart:
        raise AssertionError('Encoded Autostart differs from requested setting')
    return raw, prepared.data


def build(directory, destination, settings_json=None, title='ArtworkDraft'):
    scene = load_scene(directory)
    settings = ProcessSettings.parse(settings_json) if settings_json is not None else None
    result = scene.geometry()
    result['state'] = 'draft_encoded' if settings else 'awaiting_process_settings'
    result['process_settings'] = settings_json
    if settings:
        result['native_commands'] = {
            'raster_speed': settings.raster_speed_native, 'raster_power': float(settings.raster_power_percent),
            'vector_speed': settings.vector_speed_native, 'vector_power': float(settings.vector_power_percent),
            'vector_ppi': settings.vector_ppi,
        }
    outputs = {}
    if settings:
        raw, compressed = encode(scene, settings, title)
        outputs = {'job.raw.jbs.draft': raw, 'job.cg.jbs.draft': compressed}
        result['jobs'] = {name: {'bytes': len(data), 'sha256': sha(data)} for name, data in outputs.items()}
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    for name, data in outputs.items():
        with (destination / name).open('xb') as output:
            output.write(data)
    (destination / 'draft.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('intake', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--settings', type=Path, help='Explicit driver-native settings; omit to audit geometry only')
    parser.add_argument('--title', default='ArtworkDraft')
    args = parser.parse_args()
    try:
        result = build(args.intake, args.destination, read_json(args.settings) if args.settings else None, args.title)
        print(json.dumps(result, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f'Artwork draft: {error}\n')


if __name__ == '__main__':
    main()
