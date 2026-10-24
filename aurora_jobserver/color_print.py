"""Native per-color raster/mixed composition accepted on hardware October 23."""
from .artwork import ProcessSettings
from .color_rasters import plan_color_layers,_encode_raster_job
from .color_vector_job import plan_scene_vectors,_encode_color_vector_job
from .color_vectors import VectorPlan
from .direct_print import CONTROLLER_PATH
from .jbs import MAX_JOB_BYTES,prepare
from .wire import raster_plan


# Independent XP capture e2aeadb8... (2026-10-22): two color rasters followed
# by three color vectors match the complete raw model byte for byte.
MIXED_BOUNDARY_VERIFIED=True


def color_plans(scene,settings):
    prefs=settings['classic_preferences']
    if (settings['laser_dpi']!=167 or not prefs['UseColors']
            or settings['output_mode'] not in ('raster-only','raster-and-vector')
            or prefs['PauseColors'] or prefs['BottomUp'] or prefs['InvertRaster']):
        raise ValueError('Color raster/mixed output requires 167 DPI with Pause, Bottom-Up and Invert off')
    # A zero exposure row is already supported by the measured global raster
    # path. Retain such gaps within a color mask instead of discarding artwork
    # or inferring XP's separate picture segmentation for arbitrary text.
    rasters=plan_color_layers(scene.layers,prefs['Colors'],allow_blank_rows=True,allow_empty=True)
    if any(region.process.speed_native>31000 for region in rasters.regions):
        raise ValueError('Selected raster color speed exceeds the supported 31 ips range')
    vectors=(plan_scene_vectors(scene.vector_scene,prefs['Colors'],sort_colors=prefs['SortColors'])
             if settings['output_mode']=='raster-and-vector' else VectorPlan((),b''))
    return rasters,vectors


def encode_color_scene(scene,settings,title):
    rasters,vectors=color_plans(scene,settings)
    if not rasters.regions:
        if not vectors.paths:raise ValueError('No enabled color artwork')
        prefs=settings['classic_preferences']
        return _encode_color_vector_job(scene.vector_scene,ProcessSettings.parse(settings['process_settings']),
            prefs['Colors'],title,sort_colors=prefs['SortColors'],draft=False,autostart=settings['autostart'])
    raw,cg=_encode_raster_job(rasters,title,draft=False,autostart=settings['autostart'])
    if vectors.paths:
        if len(rasters.regions)>1 and not MIXED_BOUNDARY_VERIFIED:
            raise ValueError('Mixed multiple-raster-color transition awaits the independent XP capture')
        footer=b'PU\r0. 0. V\rEND_PLOT\r'
        if not raw.endswith(footer):raise ValueError('Unrecognized raster/vector boundary')
        raw=raw[:-len(footer)]+vectors.commands+b'0. 0. V\rEND_PLOT\r'
        if len(raw)>MAX_JOB_BYTES:raise ValueError('Mixed color job exceeds the byte limit')
        cg=prepare(raw).data
    result=prepare(cg)
    if result.auto_start!=settings['autostart']:
        raise ValueError('Color raster output changed Autostart')
    raster_plan(result.data,CONTROLLER_PATH)
    return raw,cg
