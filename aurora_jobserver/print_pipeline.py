"""Connect a completed direct-print capture to the validated flatbed encoder.

No device I/O occurs here. Ordinary offline artwork drafts retain their marker.
This route requires the dedicated print queue and complete job-attached options.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import uuid

from .artwork import ProcessSettings, _encode, load_scene
from .corel_layout import COREL_GRID
from .jbs import prepare
from .printer_settings import settings_from_xps
from .classic_settings import ensure_supported
from .store import atomic_write
from .wire import raster_plan
from .direct_print import CONTROLLER_PATH
from .vector_only import encode_candidate
from .color_vector_job import _encode_color_vector_job, plan_scene_vectors
from .color_scene import load_color_scene,ColorScene
from .color_print import color_plans,encode_color_scene


def digest(data):
    return hashlib.sha256(data).hexdigest()


def color_raster_mode(settings):
    return (settings.get('classic_preferences',{}).get('UseColors') is True
            and settings['output_mode'] in ('raster-only','raster-and-vector'))


def encode_print(scene, settings, title, *, allow_color_vectors=True, allow_color_rasters=True):
    ensure_supported(settings, allow_color_vectors=allow_color_vectors,allow_color_rasters=allow_color_rasters)
    if (scene.manifest['raster_grid'] != COREL_GRID
            or scene.manifest.get('text_rendering') != 'outline-aliased'
            or scene.manifest['dpi'] != settings['laser_dpi']):
        raise ValueError('Printer scene does not match the Corel flatbed profile')
    preferences = settings.get('classic_preferences',{})
    if color_raster_mode(settings):
        if not isinstance(scene,ColorScene):raise ValueError('Expected a verified native color scene')
        return encode_color_scene(scene,settings,title)
    if preferences.get('UseColors'):
        # Hardware acceptance covers 167-DPI Vector Only. Keep this defense
        # even if other preference holds are expanded in the future.
        if not allow_color_vectors or settings['output_mode'] != 'vector-only' or settings['laser_dpi'] != 167:
            raise ValueError('Per-color output is not enabled for this print mode')
        raw, cg = _encode_color_vector_job(scene, ProcessSettings.parse(settings['process_settings']),
            preferences['Colors'], title, sort_colors=preferences['SortColors'],
            pause_colors=preferences['PauseColors'], draft=False, autostart=settings['autostart'])
        prepared = prepare(cg)
        raster_plan(prepared.data, CONTROLLER_PATH)
        if prepared.auto_start != settings['autostart']:
            raise ValueError('Color-vector Autostart did not survive encoding')
        return raw, cg
    if settings['output_mode']=='vector-only' or (settings['output_mode']=='raster-and-vector' and scene.page['exposure'] is None):
        return encode_candidate(scene,ProcessSettings.parse(settings['process_settings']),title,
                                draft=False,autostart=settings['autostart'])
    if scene.page['exposure'] is None:
        if settings['output_mode']=='raster-only':
            raise ValueError('Raster Only contains no raster artwork; print was held')
        raise ValueError('No printable artwork')
    # load_scene has already checked source/exposure hashes, page, bounds,
    # source DPI, transforms, grayscale and all unresolved review reasons.
    raw, cg = _encode(scene, ProcessSettings.parse(settings['process_settings']), title,
                      draft=False, autostart=settings['autostart'], output_mode=settings['output_mode'],
                      invert_raster=preferences.get('InvertRaster',False),
                      bottom_up=preferences.get('BottomUp',False))
    prepared = prepare(cg)
    raster_plan(prepared.data, CONTROLLER_PATH)
    if prepared.auto_start != settings['autostart']:
        raise ValueError('Printer Autostart did not survive encoding')
    return raw, cg


def nothing_to_cut_message(scene, settings):
    if settings['output_mode'] != 'vector-only':
        return None
    if not scene.paths:
        return 'No eligible hairline paths. Nothing was sent; change the outlines to hairline and print again.'
    preferences = settings.get('classic_preferences',{})
    if preferences.get('UseColors'):
        plan = plan_scene_vectors(scene, preferences['Colors'],
            sort_colors=preferences['SortColors'], pause_colors=preferences['PauseColors'])
        if not plan.paths:
            return 'All eligible hairline colors are disabled or have zero power. Nothing was sent; enable the intended colors and print again.'
    return None


def empty_outcome(scene,settings):
    if color_raster_mode(settings):
        rasters,vectors=color_plans(scene,settings)
        if not rasters.regions and not vectors.paths:
            return ('nothing_to_print','No enabled color engraving or cutting artwork. Nothing was sent; check the palette and print again.')
        return None
    message=nothing_to_cut_message(scene,settings)
    return ('nothing_to_cut',message) if message else None


def read_print_scene(directory,settings):
    return (load_color_scene(directory) if color_raster_mode(settings)
            else load_scene(directory,allow_empty_cut_paths=settings['output_mode']=='vector-only'))


def prepare_capture(capture, destination, intake_executable, *, allow_color_vectors=True,allow_color_rasters=True):
    capture, destination = Path(capture).resolve(), Path(destination).resolve()
    receipt = json.loads((capture / 'capture.json').read_text(encoding='utf-8'))
    print_id = receipt.get('id')
    if (not isinstance(print_id,str) or str(uuid.UUID(print_id)) != print_id
            or capture.name != print_id or receipt.get('schema_version') != 1
            or receipt.get('state') != 'captured' or receipt.get('queue') != 'aurora-direct'):
        raise ValueError('Expected a completed capture from the dedicated Aurora direct-print queue')
    record = receipt['files']['document']
    if record.get('file') != 'source.bin':
        raise ValueError('Unexpected captured source path')
    with (capture / 'source.bin').open('rb') as stream:
        source = stream.read(64*1024*1024+1)
    if not 0 < len(source) <= 64*1024*1024 or record.get('bytes') != len(source) or record.get('sha256') != digest(source):
        raise ValueError('Captured print failed its integrity check')
    if destination.exists():
        # A completed conversion may be resumed after a crash, without rendering
        # again. A partial conversion stops for diagnosis and is never sent.
        result = json.loads((destination / 'print-job.json').read_text(encoding='utf-8'))
        if result.get('print_id') != print_id or result.get('source_sha256') != digest(source):
            raise ValueError('Prepared print belongs to another capture')
        ensure_supported(result['printer_settings'], allow_color_vectors=allow_color_vectors,allow_color_rasters=allow_color_rasters)
        if result.get('state')=='encoded_for_direct_print':
            if digest((destination / 'job.cg.jbs').read_bytes()) != result['cg_sha256']:
                raise ValueError('Prepared print failed its integrity check')
        elif result.get('state') in ('nothing_to_cut','nothing_to_print'):
            scene=read_print_scene(destination/'intake',result['printer_settings'])
            empty=empty_outcome(scene,result['printer_settings'])
            if (not empty or empty!=(result['state'],result.get('message'))
                    or (not isinstance(scene,ColorScene) and scene.exposure)
                    or scene.manifest['source_sha256']!=digest(source)):
                raise ValueError('Nothing-to-cut evidence changed')
        else:
            raise ValueError('Unknown prepared print outcome')
        if digest((destination / 'source.oxps').read_bytes()) != result['source_sha256']:
            raise ValueError('Prepared source snapshot changed')
        if result['printer_settings'] != settings_from_xps(destination / 'source.oxps'):
            raise ValueError('Prepared per-job settings changed')
        return result
    destination.mkdir(parents=True)
    atomic_write(destination / 'source.oxps', source)
    settings = settings_from_xps(destination / 'source.oxps')
    ensure_supported(settings, allow_color_vectors=allow_color_vectors,allow_color_rasters=allow_color_rasters)
    command = [str(Path(intake_executable).resolve()),str(destination / 'source.oxps'),str(destination / 'intake'),
               '--dpi',str(settings['laser_dpi']), '--raster-grid','coreldraw-xp-draft',
               '--text-rendering','outline-aliased',
               '--max-cut-width-mm',str(settings['max_cut_width_mm'])]
    if color_raster_mode(settings):
        command.extend(['--color-review','on'])
    else:
        command.extend(['--cut-color',settings['cut_color']])
    if settings['output_mode']=='vector-only':
        command.extend(['--cut-paths-only','on'])
    conversion = subprocess.run(command, shell=False, capture_output=True, text=True, timeout=120)
    if conversion.returncode:
        raise ValueError('Print document conversion failed: '+(conversion.stderr or conversion.stdout)[-2000:])
    scene = read_print_scene(destination / 'intake',settings)
    if scene.manifest['source_sha256'] != digest(source):
        raise ValueError('Rendered source differs from the captured print')
    title = 'Print_' + print_id[:8]
    empty=empty_outcome(scene,settings)
    if empty:
        state,message=empty
        result={'schema_version':1,'state':state,'print_id':print_id,
                'source_sha256':digest(source),'printer_settings':settings,'title':title,
                'message':message,
                'physical_delivery_performed_by_pipeline':False}
        atomic_write(destination/'print-job.json',json.dumps(result,indent=2).encode())
        return result
    raw, cg = encode_print(scene,settings,title, allow_color_vectors=allow_color_vectors,allow_color_rasters=allow_color_rasters)
    atomic_write(destination / 'job.raw.jbs',raw)
    atomic_write(destination / 'job.cg.jbs',cg)
    result = {'schema_version':1, 'state':'encoded_for_direct_print',
              'validation':'experimental_corel_flatbed_profile', 'print_id':print_id,
              'source_sha256':digest(source), 'raw_sha256':digest(raw), 'cg_sha256':digest(cg),
              'printer_settings':settings, 'title':title,
              'physical_delivery_performed_by_pipeline':False}
    atomic_write(destination / 'print-job.json',json.dumps(result,indent=2).encode())
    return result
