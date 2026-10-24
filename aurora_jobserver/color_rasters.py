"""167-DPI color raster planning and separate marked offline draft output.

Normal printing uses verified native brush coverage, preserving X7 edge samples.
Flat fixture input requires explicit RGB and binary coverage; no nearest-color
classification is inferred. Global mode consumes converted exposure, not RGB.
"""
from dataclasses import dataclass
import re
import struct

from .classic_settings import RGB
from .color_settings import ColorProcess, parse_palette
from .jbs import DRAFT_MARKER, MAX_JOB_BYTES, prepare


MAX_PIXELS = 50_000_000


@dataclass(frozen=True)
class ExposureSurface:
    x_pixels: int
    y_pixels: int
    width: int
    height: int
    pixels: bytes


@dataclass(frozen=True)
class FlatColorSurface:
    x_pixels: int
    y_pixels: int
    width: int
    height: int
    rgb: bytes  # Conventional R,G,B byte order, not native BGRA.
    coverage: bytes  # Explicit 0/255 coverage separates blank paper from paint.


@dataclass(frozen=True)
class RasterRegion:
    color_index: int | None
    image: ExposureSurface
    process: ColorProcess


@dataclass(frozen=True)
class RasterPlan:
    regions: tuple
    color_mode: bool
    pause_colors: bool = False
    unmatched_pixels: int = 0
    mask_encoding: str = 'binary-u8'


@dataclass(frozen=True)
class CoverageLayer:
    rgb: int
    image: ExposureSurface


def _dimensions(surface):
    values = (surface.x_pixels, surface.y_pixels, surface.width, surface.height)
    if (any(type(v) is not int for v in values)
            or not 0 <= surface.x_pixels < 5010 or not 0 <= surface.y_pixels < 3006
            or not 1 <= surface.width <= 5010 - surface.x_pixels
            or not 1 <= surface.height <= 3006 - surface.y_pixels):
        raise ValueError('Invalid 167-DPI surface dimensions or bounds')
    return surface.width * surface.height


def _exposure(surface):
    if not isinstance(surface, ExposureSurface):
        raise ValueError('Expected an exposure surface')
    size = _dimensions(surface)
    if type(surface.pixels) is not bytes or len(surface.pixels) != size:
        raise ValueError('Exposure must be immutable bytes matching its dimensions')


def _process(process):
    if (not isinstance(process, ColorProcess)
            or any(type(v) is not int for v in (process.speed_native, process.power_percent, process.ppi))
            or not 1 <= process.speed_native <= 150000
            or not 1 <= process.power_percent <= 100 or not 5 <= process.ppi <= 1000):
        raise ValueError('Invalid offline raster process')


def plan_global_rasters(surface, process):
    """Split observed global exposure into consecutive nonempty row bands.

    RGB-to-exposure conversion is deliberately outside this function: the
    legacy global color values do not establish a general luminance formula.
    """
    _exposure(surface)
    _process(process)
    regions = []
    start = left = right = None
    w = surface.width
    for y in range(surface.height + 1):
        row = surface.pixels[y*w:(y+1)*w] if y < surface.height else b''
        active = row.strip(b'\0')
        if active:
            x0, x1 = len(row) - len(row.lstrip(b'\0')), len(row.rstrip(b'\0'))
            if start is None:
                start, left, right = y, x0, x1
            else:
                left, right = min(left, x0), max(right, x1)
        elif start is not None:
            pixels = b''.join(surface.pixels[yy*w+left:yy*w+right] for yy in range(start, y))
            regions.append(RasterRegion(None, ExposureSurface(surface.x_pixels+left,
                surface.y_pixels+start, right-left, y-start, pixels), process))
            start = None
    if not regions:
        raise ValueError('No raster exposure in the selected surface')
    return RasterPlan(tuple(regions), False)


def plan_color_rasters(surface, palette, *, pause_colors=False):
    """Select exact palette colors, omit unmatched paint and form cropped masks.

    Multiple separated vertical bands per color and pauses with omitted
    disabled/zero-power colors remain held. These combinations need XP evidence.
    """
    if not isinstance(surface, FlatColorSurface):
        raise ValueError('Expected an explicit flat-color surface')
    size = _dimensions(surface)
    if (type(surface.rgb) is not bytes or len(surface.rgb) != size * 3
            or type(surface.coverage) is not bytes or len(surface.coverage) != size
            or any(v not in (0, 255) for v in surface.coverage)):
        raise ValueError('RGB and binary coverage must match the surface; antialiasing is unverified')
    if type(pause_colors) is not bool:
        raise ValueError('Pause must be an explicit boolean')
    processes = parse_palette(palette)
    lookup = {rgb: index for index, rgb in enumerate(RGB)}
    bounds, rows = {}, {}
    unmatched = 0
    omitted_disabled = False
    w = surface.width
    for pos, covered in enumerate(surface.coverage):
        if not covered:
            continue
        p = pos * 3
        rgb = (surface.rgb[p] << 16) | (surface.rgb[p+1] << 8) | surface.rgb[p+2]
        color = lookup.get(rgb)
        if color is None:
            unmatched += 1
            continue
        if processes[color].power_percent == 0:
            omitted_disabled = True
            continue
        y, x = divmod(pos, w)
        if color not in bounds:
            bounds[color] = [x, y, x+1, y+1]
            rows[color] = {y}
        else:
            box = bounds[color]
            box[0], box[1], box[2], box[3] = min(box[0], x), min(box[1], y), max(box[2], x+1), max(box[3], y+1)
            rows[color].add(y)
    if pause_colors and omitted_disabled:
        raise ValueError('Pauses with disabled or zero-power colors require independent XP evidence')
    if not bounds:
        raise ValueError('No enabled matched raster colors in the selected surface')
    if any(len(rows[c]) != box[3] - box[1] for c, box in bounds.items()):
        raise ValueError('Multiple vertical regions per color require independent XP evidence')
    if sum((box[2]-box[0])*(box[3]-box[1]) for box in bounds.values()) > MAX_PIXELS:
        raise ValueError('Color masks exceed the decoded pixel budget')
    buffers = {c: bytearray((b[2]-b[0])*(b[3]-b[1])) for c,b in bounds.items()}
    for pos, covered in enumerate(surface.coverage):
        if covered:
            p = pos * 3
            color = lookup.get((surface.rgb[p] << 16) | (surface.rgb[p+1] << 8) | surface.rgb[p+2])
            if color in buffers:
                y, x = divmod(pos, w)
                left, top, right, bottom = bounds[color]
                buffers[color][(y-top)*(right-left)+(x-left)] = 255
    regions = tuple(RasterRegion(c, ExposureSurface(surface.x_pixels+b[0], surface.y_pixels+b[1],
        b[2]-b[0], b[3]-b[1], bytes(buffers[c])), processes[c]) for c,b in sorted(bounds.items()))
    return RasterPlan(regions, True, pause_colors, unmatched)


def plan_color_layers(layers, palette, *, pause_colors=False, allow_blank_rows=False, allow_empty=False):
    """Plan semantic brush coverage from the experimental native reader.

    These grayscale edge masks preserve X7 rendering; they are not inferred
    by nearest RGB matching. Public draft serialization always retains its marker.
    """
    if (type(allow_blank_rows) is not bool or type(allow_empty) is not bool
            or not isinstance(layers, (tuple, list)) or not (0 if allow_empty else 1) <= len(layers) <= 32):
        raise ValueError('Expected bounded semantic color layers')
    if type(pause_colors) is not bool:
        raise ValueError('Pause must be an explicit boolean')
    processes = parse_palette(palette)
    lookup = {rgb: index for index, rgb in enumerate(RGB)}
    seen, regions = set(), []
    omitted_disabled = False
    unmatched = total = 0
    for layer in layers:
        if (not isinstance(layer, CoverageLayer) or type(layer.rgb) is not int
                or not 0 <= layer.rgb <= 0xffffff or layer.rgb in seen):
            raise ValueError('Invalid or duplicate semantic layer color')
        if layer.rgb == 0xffffff:
            raise ValueError('White paint classification requires independent XP evidence')
        seen.add(layer.rgb)
        _exposure(layer.image)
        total += len(layer.image.pixels)
        if total > MAX_PIXELS:
            raise ValueError('Semantic layers exceed the pixel budget')
        rows = [any(layer.image.pixels[y*layer.image.width:(y+1)*layer.image.width]) for y in range(layer.image.height)]
        if not any(rows):
            raise ValueError('Empty semantic layer')
        if not allow_blank_rows and not all(rows):
            raise ValueError('Multiple vertical regions per color require independent XP evidence')
        color = lookup.get(layer.rgb)
        if color is None:
            unmatched += sum(value != 0 for value in layer.image.pixels)
            continue
        if processes[color].power_percent == 0:
            omitted_disabled = True
            continue
        regions.append(RasterRegion(color, layer.image, processes[color]))
    if pause_colors and omitted_disabled:
        raise ValueError('Pauses with disabled or zero-power colors require independent XP evidence')
    if not regions and not allow_empty:
        raise ValueError('No enabled matched semantic color layers')
    return RasterPlan(tuple(sorted(regions,key=lambda region:region.color_index)), True,
        pause_colors, unmatched, 'semantic-coverage-u8-review')


def encode_raster_draft(plan, title='ColorRasterDraft'):
    """Serialize a validated offline plan; every output retains the draft marker.

    Only raw/CG drafts are returned. There is no unmarked or Autostart option.
    """
    return _encode_raster_job(plan,title,draft=True,autostart=False)


def _encode_raster_job(plan, title, *, draft, autostart=False):
    """Shared serializer; only the validated print route requests unmarked jobs."""
    if type(draft) is not bool or type(autostart) is not bool or (draft and autostart):
        raise ValueError('Raster output requires explicit draft/Autostart flags; drafts cannot autostart')
    if (not isinstance(plan, RasterPlan) or type(plan.color_mode) is not bool
            or type(plan.pause_colors) is not bool or not isinstance(plan.regions, tuple)
            or not 1 <= len(plan.regions) <= 3006 or (plan.pause_colors and not plan.color_mode)
            or plan.mask_encoding not in ('binary-u8','semantic-coverage-u8-review')
            or (not plan.color_mode and plan.mask_encoding != 'binary-u8')):
        raise ValueError('Invalid offline raster plan')
    if not isinstance(title, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', title):
        raise ValueError('Draft title must be 1-64 ASCII letters, digits, dots, underscores or hyphens')
    total = 0
    colors = []
    for region in plan.regions:
        if not isinstance(region, RasterRegion):
            raise ValueError('Invalid raster region')
        _exposure(region.image)
        _process(region.process)
        total += len(region.image.pixels)
        if not any(region.image.pixels):
            raise ValueError('Empty raster region')
        if plan.color_mode:
            if type(region.color_index) is not int or not 0 <= region.color_index < 16:
                raise ValueError('Invalid raster color index')
            if plan.mask_encoding == 'binary-u8' and any(v not in (0,255) for v in region.image.pixels):
                raise ValueError('Color region masks must be binary')
            colors.append(region.color_index)
        elif region.color_index is not None:
            raise ValueError('Global raster region has a color index')
    if total > MAX_PIXELS or (plan.color_mode and colors != sorted(set(colors))):
        raise ValueError('Raster pixel budget or palette region order is invalid')
    out = bytearray(b'!ZX\r' + (DRAFT_MARKER + b'\r' if draft else b'') + f'JOB {title}\n\r'.encode()
        + b'1 set_binary\r1 == ?REPLAY\r6.000 set_gspot\r'
        + (b'autostart START\r' if autostart else b'normalstart START\r')
        + b'0 set_rotary\r100. set_xyup_feed\r0 PMC\r40 PWF\r')
    previous = None
    pause_pen_up = False
    for index, region in enumerate(plan.regions):
        process, image = region.process, region.image
        if previous is None or process.speed_native != previous.speed_native:
            out.extend(f'{process.speed_native}. speed\r'.encode())
        if previous is None or process.power_percent != previous.power_percent:
            out.extend(f'{process.power_percent:.2f} power\r'.encode())
        out.extend(f'PU\r2 RA\r{image.x_pixels*6}.0 {image.y_pixels*6}.0 V\r6.000 set_gspot\rPICT-UL\r'.encode())
        out.extend(struct.pack('<HIIIIH', 0x58c3, image.width, image.height, 167, 167, 0x41))
        for y in range(image.height):
            row = image.pixels[y*image.width:(y+1)*image.width]
            out.extend(row[::-1] if y % 2 else row)
            out.extend(b'\0\xff')
        if plan.pause_colors and index+1 < len(plan.regions):
            if not pause_pen_up:
                out.extend(b'PU\r')
                pause_pen_up = True
            out.extend(b'0. 0. V\rPAUSE\r')
        previous = process
    out.extend((b'' if pause_pen_up else b'PU\r') + b'0. 0. V\rEND_PLOT\r')
    raw = bytes(out)
    if len(raw) > MAX_JOB_BYTES:
        raise ValueError('Raster draft exceeds the job byte limit')
    converted = prepare(raw, allow_draft=draft)
    if converted.auto_start != autostart:
        raise AssertionError('Raster output changed Autostart')
    return raw, converted.data
