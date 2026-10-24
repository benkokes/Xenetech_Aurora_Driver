"""Stage the reviewed square-and-TEST measurement job offline; never send it.

This deliberately accepts only the exact known 167-DPI reference. It is not a
general draft-release switch and does not change production artwork status.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import struct
import zlib

from .artwork import ProcessSettings, _encode, load_scene
from .jbs import DRAFT_MARKER, prepare
from .wire import raster_plan


SOURCE_SHA = '3946206c02d2504eab9b436b2c217ab468072bf39f134b0e59d0bbb68af07870'
EXPOSURE_SHA = 'bf712adcea801b20ef978d188ceba676f71e05e931e88f89b90e9e8817ef17b5'
SETTINGS = {'schema_version': 1, 'units': 'inches-per-second', 'raster_speed_ips': 30,
            'raster_power_percent': 30, 'vector_speed_ips': 1, 'vector_power_percent': 15, 'vector_ppi': 1000}
PATHS = [[[876,1212],[1878,1212],[1878,2214],[876,2214],[876,1212]]]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def validate_reference(scene):
    geometry = scene.geometry()
    expected = {
        'source_sha256': SOURCE_SHA, 'raster_grid': 'coreldraw-xp-draft',
        'dpi': 167, 'raster_pixel_pitch_units': 6, 'text_rendering': 'outline-aliased',
        'page_mm': [762,457.2], 'paths_units': PATHS,
        'corel_xp_compatibility': {'model':'coreldraw-x7-to-xp11-flatbed-v1',
            'validation':'reference_fit_not_physical_calibration','source_printer_dpi':600,'target_dpi':167},
        'raster': {'width':140,'height':41,'origin_units':[972,720],'exposure_sha256':EXPOSURE_SHA},
    }
    for name, value in expected.items():
        if geometry.get(name) != value:
            raise ValueError('Calibration staging accepts only the reviewed square-and-TEST reference: ' + name)
    if sha(scene.exposure) != EXPOSURE_SHA:
        raise ValueError('Calibration exposure does not match the reviewed reference')
    return geometry


def png_gray(exposure, width, height):
    def chunk(kind, data):
        body = kind + data
        return struct.pack('>I',len(data)) + body + struct.pack('>I',zlib.crc32(body)&0xffffffff)
    rows = b''.join(b'\0' + bytes(255-x for x in exposure[y*width:(y+1)*width]) for y in range(height))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,0,0,0,0))
            + chunk(b'IDAT',zlib.compress(rows)) + chunk(b'IEND',b''))


def preview(scene):
    image = base64.b64encode(png_gray(scene.exposure,140,41)).decode('ascii')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="480" height="660" viewBox="800 650 1200 1650">\n'
            '<title>Reviewed square and TEST calibration job - native controller coordinates</title>\n'
            '<rect x="800" y="650" width="1200" height="1650" fill="white"/>\n'
            f'<image x="972" y="720" width="840" height="246" style="image-rendering:pixelated" href="data:image/png;base64,{image}"/>\n'
            '<path d="M876 1212 H1878 V2214 H876 Z" fill="none" stroke="red" stroke-width="3"/>\n'
            '</svg>\n')


def stage(intake, destination, *, raster_power_percent=30):
    if type(raster_power_percent) is not int or raster_power_percent not in (30,45):
        raise ValueError('Only the reviewed 30% reference and owner-requested 45% raster test are supported')
    scene = load_scene(intake)
    geometry = validate_reference(scene)
    settings = dict(SETTINGS, raster_power_percent=raster_power_percent)
    title = 'AuroraCalibration167' if raster_power_percent == 30 else 'AuroraCal167P45'
    raw, compressed = _encode(scene,ProcessSettings.parse(settings),title,draft=False)
    validated = prepare(compressed)
    if validated.auto_start or validated.rasters != 1 or DRAFT_MARKER in raw[:128]:
        raise AssertionError('Unexpected calibration framing')
    plan = raster_plan(validated.data,r'c:\xfiles\jbs\Convert\Default.jbs')
    result = {
        'schema_version':1, 'purpose':'single physical calibration test; not approved for production',
        'state':'staged_offline_awaiting_operator_readiness',
        'lettering_decision':'owner chose to preserve the X7 appearance shown in the comparison',
        'artwork':geometry, 'process_settings':settings, 'auto_start':False,
        'physical_feedback_basis': None if raster_power_percent == 30 else 'Owner reported 30% raster too light and requested a 50% relative power increase to 45%',
        'focus':'No Focus at Start; operator must prepare focus and material',
        'controller_bounds_units':[876,720,1878,2214],
        'design_square_inches':[1,1], 'emitted_square_units':[1002,1002],
        'physical_size_validated':False,
        'known_original_warning':"Token 'set_xyup_feed' not found",
        'files':{'calibration.raw.jbs':{'bytes':len(raw),'sha256':sha(raw)},
                 'calibration.cg.jbs':{'bytes':len(compressed),'sha256':sha(compressed)}},
        'wire_plan_steps':len(plan),
        'controller_target':'192.168.1.244; not contacted during staging',
    }
    destination = Path(destination)
    destination.mkdir(parents=True,exist_ok=False)
    for name,data in [('calibration.raw.jbs',raw),('calibration.cg.jbs',compressed)]:
        with (destination/name).open('xb') as file:
            file.write(data)
    (destination/'preview.svg').write_text(preview(scene),encoding='utf-8')
    (destination/'calibration-plan.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    measurements = {'job_sha256':sha(compressed),'completed':None,'square_width_mm':None,
                    'square_height_mm':None,'square_left_from_bed_origin_mm':None,
                    'square_top_from_bed_origin_mm':None,'text_complete':None,
                    'material_and_focus_notes':None,'operator_notes':None}
    (destination/'measurements-template.json').write_text(json.dumps(measurements,indent=2)+'\n',encoding='utf-8')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('intake',type=Path)
    parser.add_argument('destination',type=Path)
    parser.add_argument('--raster-power-percent',type=int,choices=(30,45),default=30)
    args=parser.parse_args()
    try:
        print(json.dumps(stage(args.intake,args.destination,raster_power_percent=args.raster_power_percent),indent=2))
    except (OSError,ValueError,KeyError,TypeError) as error:
        parser.exit(2,f'Calibration staging: {error}\n')


if __name__=='__main__':
    main()
