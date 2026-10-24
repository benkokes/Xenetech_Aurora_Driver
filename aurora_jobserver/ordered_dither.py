"""Offline 167-DPI ordered exposure conversion recovered from XP captures.

Phase is explicit: (0, 0) indexes the threshold at the first sample of the
651x315 reference raster at native origin (1014,1026). A bed-relative phase
rule fits two references but has not been independently validated at arbitrary
origins. The production print pipeline deliberately keeps DitherBitmaps held.

Input is laser exposure (0 blank, 255 full), not conventional image luminance.
This module neither quantizes grayscale nor resizes, crops or repositions it.
"""
from copy import deepcopy
from dataclasses import replace
import hashlib
from types import MappingProxyType

from .artwork import ProcessSettings, Scene, encode
from .corel_layout import COREL_GRID


# Exact white-max thresholds: full exposure is emitted iff input > threshold.
# All 256 levels were observed at every matrix phase in the XP reference.
THRESHOLDS = MappingProxyType({
    'Ordered4': (
        (151, 103, 167, 87),
        (55, 199, 7, 247),
        (183, 71, 135, 119),
        (23, 231, 39, 215),
    ),
    'Ordered8': (
        (157, 109, 173, 81, 145, 97, 161, 93),
        (53, 197, 5, 249, 57, 201, 9, 245),
        (181, 69, 133, 121, 185, 73, 137, 117),
        (21, 229, 37, 217, 25, 233, 41, 213),
        (149, 101, 165, 89, 153, 105, 169, 85),
        (61, 205, 13, 241, 49, 193, 1, 253),
        (189, 77, 141, 113, 177, 65, 129, 125),
        (29, 237, 45, 209, 17, 225, 33, 221),
    ),
})


def ordered_exposure(pixels, width, height, method, *, phase_x, phase_y):
    """Return immutable binary exposure with unchanged dimensions and row order.

    phase_x/phase_y index the table at the input rectangle's top-left sample;
    callers must supply normalized integers. They are not inferred from a
    physical machine origin. Cropped/tiled input must advance its phase by its
    corresponding pixel offset, modulo the matrix size.
    """
    if not isinstance(method, str) or method not in THRESHOLDS:
        raise ValueError('Expected Ordered4 or Ordered8')
    table = THRESHOLDS[method]
    size = len(table)
    if (type(width) is not int or type(height) is not int
            or not 1 <= width <= 5000 or not 1 <= height <= 3000):
        raise ValueError('Invalid 167-DPI raster dimensions')
    if type(pixels) is not bytes or len(pixels) != width * height:
        raise ValueError('Expected immutable exposure bytes matching dimensions')
    if any(type(v) is not int or not 0 <= v < size for v in (phase_x, phase_y)):
        raise ValueError('Ordered phase must be normalized integer table coordinates')
    output = bytearray(width * height)
    # Translate each interleaved matrix column. This bounds intermediate memory
    # to a row and avoids a Python callback for every pixel of a full bed.
    maps = {threshold: bytes(255 if v > threshold else 0 for v in range(256))
            for row in table for threshold in row}
    for y in range(height):
        row = pixels[y*width:(y+1)*width]
        thresholds = table[(y + phase_y) % size]
        for x in range(min(size, width)):
            converted = row[x::size].translate(maps[thresholds[(x + phase_x) % size]])
            output[y*width+x:(y+1)*width:size] = converted
    return bytes(output)


def encode_ordered_draft(scene, process, method, *, phase_x, phase_y,
                         title='OrderedDraft', output_mode='raster-and-vector'):
    """Encode marked review drafts only, with unchanged geometry and vectors.

    The caller provides a validated Scene and explicit phase. There is no
    unmarked-output or Autostart option, and no print-ticket override.
    """
    if (not isinstance(scene, Scene) or scene.manifest.get('dpi') != 167
            or scene.manifest.get('raster_grid') != COREL_GRID):
        raise ValueError('Ordered draft requires the explicit 167-DPI Corel grid')
    if not isinstance(process, ProcessSettings):
        raise ValueError('Expected validated process settings')
    if output_mode not in ('raster-and-vector', 'raster-only'):
        raise ValueError('Ordered draft requires raster content')
    raster = scene.page.get('exposure')
    if not isinstance(raster, dict):
        raise ValueError('Ordered draft requires an exposure rectangle')
    width, height = raster.get('width'), raster.get('height')
    x, y = raster.get('x_pixels'), raster.get('y_pixels')
    if (type(x) is not int or type(y) is not int or x < 0 or y < 0
            or type(width) is not int or type(height) is not int
            or x + width > 5000 or y + height > 3000):
        raise ValueError('Exposure rectangle leaves the 167-DPI Corel surface')
    exposure = ordered_exposure(scene.exposure, width, height, method,
                                phase_x=phase_x, phase_y=phase_y)
    page = deepcopy(scene.page)
    page['exposure']['sha256'] = hashlib.sha256(exposure).hexdigest()
    converted = replace(scene, page=page, exposure=exposure)
    return encode(converted, process, title, output_mode=output_mode)
