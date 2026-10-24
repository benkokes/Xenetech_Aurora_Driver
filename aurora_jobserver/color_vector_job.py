"""Per-color cut-only composition and separate marked offline drafts.

Uses the already measured zero-power carrier and the independently recovered
XP color-vector body. The owner accepted the five-path physical test on
October 22, 2026; the print pipeline supports this at 167 DPI in Vector Only.
"""
from dataclasses import replace
from decimal import Decimal
import re

from .artwork import _encode
from .color_vectors import plan_vectors
from .corel_layout import COREL_GRID, COREL_HAIRLINE_MAX_MM
from .jbs import DRAFT_MARKER, MAX_JOB_BYTES, prepare


def plan_scene_vectors(scene, palette, *, sort_colors=False, pause_colors=False):
    """Retain source RGB identity after validated all-color hairline extraction."""
    manifest = scene.manifest
    if (manifest.get('dpi') != 167 or manifest.get('raster_grid') != COREL_GRID
            or manifest.get('text_rendering') != 'outline-aliased'
            or manifest.get('cut_color') != 'any'
            or isinstance(manifest.get('max_cut_width_mm'), bool)
            or not isinstance(manifest.get('max_cut_width_mm'), (int,float))
            or not 0 < manifest['max_cut_width_mm'] <= COREL_HAIRLINE_MAX_MM):
        raise ValueError('Color vectors require the 167-DPI all-color Corel hairline profile')
    cuts = scene.page.get('cuts')
    if not isinstance(cuts, list) or len(cuts) != len(scene.paths):
        raise ValueError('Expected one source color identity per extracted hairline path')
    colors = []
    for cut in cuts:
        if (not isinstance(cut, dict) or not isinstance(cut.get('color'), str)
                or not re.fullmatch(r'#FF[0-9A-F]{6}', cut['color'])):
            raise ValueError('Expected opaque RGB identity for each hairline path')
        width = cut.get('width_mm')
        if (isinstance(width,bool) or not isinstance(width,(int,float))
                or not 0 < width <= COREL_HAIRLINE_MAX_MM):
            raise ValueError('Cut path is wider than the established hairline threshold')
        colors.append(int(cut['color'][3:],16))
    plan = plan_vectors(scene.paths, colors, palette,
                        sort_colors=sort_colors, pause_colors=pause_colors)
    if any(path.process.speed_native > 15000 for path in plan.paths):
        raise ValueError('Selected color vector speed exceeds the Aurora 15 ips UI range')
    return plan


def encode_color_vector_draft(scene, process, palette, *, sort_colors=False,
                              pause_colors=False, title='ColorVectorOffline'):
    """Encode a marked, normal-start cut-only job with a zero-exposure carrier.

    Global process values never replace the selected palette values. All paths
    disabled/zero-power means no job, rather than an empty upload. There is no
    option here to remove the marker or enable Autostart.
    """
    return _encode_color_vector_job(scene, process, palette, title,
        sort_colors=sort_colors, pause_colors=pause_colors, draft=True)


def _encode_color_vector_job(scene, process, palette, title, *, sort_colors=False,
                             pause_colors=False, draft, autostart=False):
    """Shared implementation for drafts and the supported vector print path."""
    if type(draft) is not bool or type(autostart) is not bool:
        raise ValueError('Color vector output requires explicit draft/Autostart booleans')
    if draft and autostart:
        raise ValueError('Offline color drafts cannot enable Autostart')
    plan = plan_scene_vectors(scene, palette, sort_colors=sort_colors,
                              pause_colors=pause_colors)
    if not plan.paths:
        raise ValueError('Nothing to cut: no enabled nonzero-power color paths')
    carrier = replace(scene, page=dict(scene.page, exposure={
        'width':1,'height':1,'x_pixels':0,'y_pixels':0}), exposure=b'\0')
    zero_process = replace(process, raster_power_percent=Decimal(0))
    raw, _ = _encode(carrier, zero_process, title, output_mode='raster-only',
                     draft=draft, autostart=autostart)
    footer = b'PU\r0. 0. V\rEND_PLOT\r'
    if not raw.endswith(footer):
        raise ValueError('Unrecognized carrier/vector pen-state boundary')
    raw = raw[:-len(footer)] + plan.commands + b'0. 0. V\rEND_PLOT\r'
    if len(raw) > MAX_JOB_BYTES:
        raise ValueError('Color vector job exceeds the job byte limit')
    cg = prepare(raw, allow_draft=draft)
    if cg.auto_start != autostart:
        raise AssertionError('Color vector output changed Autostart')
    if draft and not cg.data.startswith(b'!ZX\r'+DRAFT_MARKER+b'\r'):
        raise AssertionError('Color vector draft lost its marker')
    return raw, cg.data
