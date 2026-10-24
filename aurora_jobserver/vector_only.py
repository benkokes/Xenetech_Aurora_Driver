"""Cut-only encoding using the physically validated CG transfer envelope.

A one-pixel zero-exposure, zero-power raster precedes the requested cut paths.
The owner accepted its square/circle physical test on October 22, 2026.
"""
from dataclasses import replace
from decimal import Decimal

from .artwork import _encode
from .wire import raster_plan
from .direct_print import CONTROLLER_PATH
from .corel_layout import COREL_HAIRLINE_MAX_MM, COREL_GRID


HAIRLINE_MAX_MM = COREL_HAIRLINE_MAX_MM


def encode_candidate(scene, process, title='VectorOnlyReview', *, draft=True, autostart=False):
    if type(draft) is not bool or scene.manifest.get('dpi')!=167:
        raise ValueError('Vector-only candidate requires 167 DPI and an explicit draft flag')
    if not scene.paths:
        raise ValueError('Nothing to cut: no eligible hairline paths')
    if (scene.manifest.get('raster_grid')!=COREL_GRID or scene.manifest.get('cut_color')!='any'
            or scene.manifest.get('text_rendering')!='outline-aliased'):
        raise ValueError('Expected an explicit all-color Corel hairline intake')
    if scene.manifest.get('max_cut_width_mm',1) > HAIRLINE_MAX_MM:
        raise ValueError('Cut-path intake used a wider-than-hairline rule')
    # Ignore all original raster settings and pixels. No visible artwork is
    # encoded in this carrier, and its process power is explicitly zero too.
    carrier=replace(scene,page=dict(scene.page,exposure={
        'width':1,'height':1,'x_pixels':0,'y_pixels':0}),exposure=b'\0')
    settings=replace(process,raster_power_percent=Decimal(0))
    raw,cg=_encode(carrier,settings,title,draft=draft,autostart=autostart)
    if not draft:
        raster_plan(cg,CONTROLLER_PATH)
    return raw,cg
