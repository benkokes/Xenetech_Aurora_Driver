"""Recovered original-driver per-color vector command body.

Used by the 167-DPI Vector Only print path and marked offline review tools.
This model alone does not extract artwork, encode colored raster regions,
build complete jobs, or authorize legacy speeds.
The five independent XP references establish the sampled vector behavior.
"""
from dataclasses import dataclass
from decimal import Decimal

from .classic_settings import RGB
from .color_settings import ColorProcess, decimal_number, parse_palette


@dataclass(frozen=True)
class ColorPath:
    source_index: int
    color_index: int  # 16 is the unmatched-color sentinel, before clamping.
    palette_index: int
    points: tuple
    process: ColorProcess


@dataclass(frozen=True)
class VectorPlan:
    paths: tuple
    commands: bytes  # Body only; no header, final origin return or END_PLOT.


def plan_vectors(paths, rgb_colors, palette, *, sort_colors=False, pause_colors=False):
    """Plan exact-RGB paths in drawing order, using the fixed original palette.

    Coordinates must already be in native job units. Unmatched colors retain
    index 16 for sorting/transitions but use palette entry 15 for processing.
    Fractional powers and pauses combined with omitted paths are held until
    independent captures establish those behaviors. Legacy speeds above the
    production limit are accepted here solely to model offline reference files.
    """
    if type(sort_colors) is not bool or type(pause_colors) is not bool:
        raise ValueError('Sort and pause must be explicit booleans')
    if (not isinstance(paths, (list, tuple)) or not isinstance(rgb_colors, (list, tuple))
            or len(paths) != len(rgb_colors) or len(paths) > 100000):
        raise ValueError('Expected one RGB color per bounded vector path')
    processes = parse_palette(palette)
    lookup = {rgb: index for index, rgb in enumerate(RGB)}
    items = []
    total_points = 0
    for source_index, (path, rgb) in enumerate(zip(paths, rgb_colors)):
        if type(rgb) is not int or not 0 <= rgb <= 0xffffff:
            raise ValueError('Expected an opaque 24-bit RGB integer')
        if not isinstance(path, (list, tuple)) or len(path) < 2:
            raise ValueError('Invalid vector path')
        total_points += len(path)
        if total_points > 2000000:
            raise ValueError('Too many vector points')
        points = []
        for point in path:
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                raise ValueError('Invalid vector point')
            for coordinate in point:
                if isinstance(coordinate, bool) or not isinstance(coordinate, (int, float, Decimal)):
                    raise ValueError('Invalid native vector coordinate')
                decimal_number(coordinate, 'native vector coordinate', -1000000, 1000000, 10)
            points.append(tuple(point))
        if len(set(points)) < 2:
            raise ValueError('Collapsed vector path')
        color_index = lookup.get(rgb, 16)
        palette_index = min(color_index, 15)
        items.append(ColorPath(source_index, color_index, palette_index, tuple(points), processes[palette_index]))
    if pause_colors and any(item.process.power_percent == 0 for item in items):
        raise ValueError('Pauses with disabled or zero-power colors require independent XP evidence')
    if sort_colors:
        # XP's linked-list insertion uses <=, reversing each equal-color group.
        items.sort(key=lambda item: (item.color_index, -item.source_index))
    items = tuple(item for item in items if item.process.power_percent != 0)
    out = bytearray()
    previous = None
    for index, item in enumerate(items):
        process = item.process
        if previous is None or process.speed_native != previous.speed_native:
            out.extend(f'{process.speed_native}. speed\r'.encode())
        if previous is None or process.power_percent != previous.power_percent:
            out.extend(f'{process.power_percent:.2f} power\r'.encode())
        if previous is None or process.ppi != previous.ppi:
            out.extend(f'{process.ppi}. set_vppi\r'.encode())
        x, y = item.points[0]
        out.extend(f'PU\r2 RA\r{x:.1f} {y:.1f} V\r1 RA\rPD\r'.encode())
        for x, y in item.points[1:]:
            out.extend(f'{x:.1f} {y:.1f} V\r'.encode())
        out.extend(b'PU\r2 RA\r')
        if pause_colors and index + 1 < len(items) and items[index + 1].color_index != item.color_index:
            out.extend(b'0. 0. V\rPAUSE\r')
        previous = process
    return VectorPlan(items, bytes(out))
