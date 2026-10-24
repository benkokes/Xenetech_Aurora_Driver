"""Recovered XP rotary setup, for marked offline drafts only.

No production settings exception or device I/O is provided here. Paper size
means the original DEVMODE fields in tenths of a millimeter, not an assumed
diameter supplied by a modern UI. UI size conversion still needs XP evidence.
"""
from dataclasses import dataclass
import math

from .artwork import encode
from .corel_layout import COREL_GRID
from .jbs import DRAFT_MARKER, prepare


# Doubles read from the matched XP graphics DLL at 0x403200 / 0x403208.
XP_PI = float.fromhex('0x1.921fb54442d18p+1')
XP_TENTH_MM_TO_INCHES = float.fromhex('0x1.0204081020408p-8')
ORIENTATIONS = ('Normal', 'Left90', 'Right90', 'UpsideDown')


@dataclass(frozen=True)
class RotarySetup:
    paper_width_tenth_mm: int
    paper_height_tenth_mm: int
    orientation: str
    selected_dimension: str
    axis_scale: float
    commands: bytes


def setup_from_devmode(paper_width_tenth_mm, paper_height_tenth_mm, *, orientation='Normal'):
    """Model the positive-dimension branch at graphics VA 0x407663.

    Normal/180 use dmPaperLength (+0x90); either 90-degree orientation uses
    dmPaperWidth (+0x92). The driver emits PI/(selected_size/254), to five
    decimal places. Negative/zero DEVMODE sizes are not supported here.
    """
    for value in (paper_width_tenth_mm, paper_height_tenth_mm):
        if type(value) is not int or not 1 <= value <= 32767:
            raise ValueError('Rotary DEVMODE dimensions must be positive signed 16-bit integers in tenths of a millimeter')
    if orientation not in ORIENTATIONS:
        raise ValueError('Unknown rotary plate orientation')
    dimension = 'height' if orientation in ('Normal', 'UpsideDown') else 'width'
    selected = paper_width_tenth_mm if dimension == 'width' else paper_height_tenth_mm
    scale = XP_PI / (selected * XP_TENTH_MM_TO_INCHES)
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError('Invalid rotary axis scale')
    commands = f'1 set_rotary\r{scale:.5f} zset_axis\r'.encode('ascii')
    return RotarySetup(paper_width_tenth_mm, paper_height_tenth_mm, orientation,
                       dimension, scale, commands)


def encode_rotary_draft(scene, process, *, paper_width_tenth_mm,
                        paper_height_tenth_mm, title='RotaryOfflineReview'):
    """Add recovered rotary setup to a normal-orientation 167-DPI draft.

    Artwork coordinates are preserved; this does not establish rotary surface
    size, Corel placement, physical gearing, or focus. There is deliberately no
    Autostart, production, or unmarked-output option. Both formats are blocked
    by normal preparation and delivery through the existing draft marker.
    """
    if (scene.manifest.get('dpi') != 167 or scene.manifest.get('raster_grid') != COREL_GRID
            or scene.manifest.get('text_rendering') != 'outline-aliased'):
        raise ValueError('Rotary draft requires the normal 167-DPI Corel review profile')
    setup = setup_from_devmode(paper_width_tenth_mm, paper_height_tenth_mm)
    raw, _ = encode(scene, process, title)
    # Only inspect the known generated command prefix; binary picture samples
    # may contain arbitrary bytes resembling commands and must not be edited.
    prefix, separator, body = raw.partition(b'0 PMC\r')
    old = b'0 set_rotary\r100. set_xyup_feed\r'
    if (not separator or not raw.startswith(b'!ZX\r' + DRAFT_MARKER + b'\r')
            or prefix.count(old) != 1 or b'autostart START\r' in prefix):
        raise ValueError('Unrecognized flatbed draft header')
    raw = prefix.replace(old, setup.commands + b'100. set_xyup_feed\r', 1) + separator + body
    cg = prepare(raw, allow_draft=True)
    if cg.auto_start or not cg.data.startswith(b'!ZX\r' + DRAFT_MARKER + b'\r'):
        raise AssertionError('Rotary draft lost its offline restrictions')
    return raw, cg.data
