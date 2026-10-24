"""Build marked offline bottom-up, per-color cut, and rotary review artifacts.

Reuses a validated saved intake. Example process/paper settings below are
explicit review fixtures, never inferred operator choices or printer defaults.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from aurora_jobserver.artwork import ProcessSettings, encode, load_scene
from aurora_jobserver.classic_settings import NAMES, RGB
from aurora_jobserver.color_vector_job import encode_color_vector_draft, plan_scene_vectors
from aurora_jobserver.direct_print import CONTROLLER_PATH
from aurora_jobserver.jbs import prepare
from aurora_jobserver.rotary import encode_rotary_draft, setup_from_devmode
from aurora_jobserver.wire import raster_plan
from tools.compare_preference_jobs import decode


def build(intake, destination):
    scene = load_scene(Path(intake))
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Review destination already exists; preserve prior evidence')
    process_json = {'schema_version':1,'units':'driver-native',
        'raster_speed_native':30000,'raster_power_percent':45,
        'vector_speed_native':1000,'vector_power_percent':15,'vector_ppi':1000}
    process = ProcessSettings.parse(process_json)
    palette = [{'Name':name, 'R':(rgb>>16)&255, 'G':(rgb>>8)&255, 'B':rgb&255,
        'Enabled':True,'PowerPercent':'15','SpeedIps':'1','Ppi':1000}
        for name,rgb in zip(NAMES,RGB)]
    palette[1].update(PowerPercent='20',SpeedIps='2',Ppi=750)
    palette[9].update(PowerPercent='25',SpeedIps='3',Ppi=500)
    cases = {
        'bottom-up':encode(scene,process,'BottomUpOffline',output_mode='raster-only',bottom_up=True),
        'color-vector':encode_color_vector_draft(scene,process,palette),
        # Flatbed DEVMODE dimensions solely exercise the recovered formula.
        # These are NOT an actual cylinder configuration.
        'rotary-formula-example':encode_rotary_draft(scene,process,
            paper_width_tenth_mm=7620,paper_height_tenth_mm=4572),
    }
    report = {'state':'offline_drafts_not_authorized_for_physical_use',
        'source_sha256':scene.manifest['source_sha256'],
        'settings_origin':'explicit_synthetic_review_fixtures_not_source_PrintTicket',
        'physical_device_io':False,'new_host_or_xp_print_submitted':False,
        'process_fixture':process_json,'palette_fixture':palette,'cases':{}}
    plan = plan_scene_vectors(scene,palette)
    expected_color_paths = [list(map(list,path.points)) for path in plan.paths]
    destination.mkdir(parents=True,exist_ok=False)
    for case, pair in cases.items():
        folder=destination/case
        folder.mkdir()
        details=[]
        for kind,data in zip(('raw','cg'),pair):
            job=decode(data)
            if not job['draft'] or job['autostart']:
                raise AssertionError('Review artifact lost its restrictions')
            for check in (lambda:prepare(data),lambda:raster_plan(data,CONTROLLER_PATH)):
                try:check()
                except ValueError as error:
                    if 'uncalibrated draft' not in str(error):raise
                else:raise AssertionError('Review artifact permits ordinary delivery')
            if case=='color-vector':
                if [path['points'] for path in job['vector_paths']]!=expected_color_paths:
                    raise AssertionError('Per-color composition changed cut geometry')
                if job['rasters'][0]['pixels']!=b'\0' or job['rasters'][0]['settings']['power']!=0:
                    raise AssertionError('Cut-only carrier exposes artwork')
            elif case=='bottom-up':
                image=scene.page['exposure'];w,h=image['width'],image['height']
                expected=b''.join(scene.exposure[y*w:(y+1)*w] for y in range(h-1,-1,-1))
                if (job['rasters'][0]['pixels']!=expected or job['rasters'][0]['origin_label']!='LL'
                        or job['vector_paths']):
                    raise AssertionError('Bottom-up review differs from its reversed raster')
            else:
                if job['rasters'][0]['pixels']!=scene.exposure:
                    raise AssertionError('Rotary setup altered stored raster pixels')
            filename=f'job.{kind}.jbs.draft'
            (folder/filename).write_bytes(data)
            details.append({'file':filename,'sha256':hashlib.sha256(data).hexdigest(),
                'bytes':len(data),'raster_blocks':len(job['rasters']),
                'cut_paths':len(job['vector_paths']),'ordinary_delivery_blocked':True})
        report['cases'][case]=details
    setup=asdict(setup_from_devmode(7620,4572))
    setup['commands']=setup['commands'].decode('ascii')
    report['rotary_formula_example_not_actual_cylinder']=setup
    (destination/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('saved_intake',type=Path)
    parser.add_argument('destination',type=Path)
    args=parser.parse_args()
    result=build(args.saved_intake,args.destination)
    print(json.dumps({'state':result['state'],'cases':list(result['cases']),'physical_device_io':False}))


if __name__=='__main__':
    main()
