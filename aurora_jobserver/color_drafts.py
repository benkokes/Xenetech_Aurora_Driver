"""Compose only MARKED offline color raster/vector review jobs.

The October 22 XP capture verifies multiple raster colors followed by vectors
with Pause off. Paused mixed-color transitions remain held.
"""
from .color_rasters import RasterPlan,encode_raster_draft
from .color_settings import parse_palette
from .color_vectors import plan_vectors
from .jbs import prepare


def encode_color_draft(rasters,paths,rgb_colors,palette,*,sort_colors=False,
                       pause_colors=False,title='ColorMixedReview'):
    if not isinstance(rasters,RasterPlan) or not rasters.color_mode or rasters.pause_colors!=pause_colors:
        raise ValueError('Raster/vector color preferences disagree')
    processes=parse_palette(palette)
    for region in rasters.regions:
        if (type(region.color_index) is not int or not 0<=region.color_index<16
                or region.process!=processes[region.color_index]):
            raise ValueError('Raster/vector palette processes disagree')
    vectors=plan_vectors(paths,rgb_colors,palette,sort_colors=sort_colors,pause_colors=pause_colors)
    raw,cg=encode_raster_draft(rasters,title)
    if not vectors.paths:return raw,cg
    if len(rasters.regions)!=1 and pause_colors:
        raise ValueError('Paused mixed multiple-raster-color boundaries require independent XP evidence')
    footer=b'PU\r0. 0. V\rEND_PLOT\r'
    if not raw.endswith(footer):raise ValueError('Unverified raster/vector pen-state boundary')
    raw=raw[:-len(footer)]+vectors.commands+b'0. 0. V\rEND_PLOT\r'
    prepared=prepare(raw,allow_draft=True)
    if prepared.auto_start:raise AssertionError('Offline color draft enabled Autostart')
    return raw,prepared.data
