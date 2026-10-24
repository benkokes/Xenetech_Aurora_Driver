"""Stage an offline cut-only candidate from saved X7 artwork, never send it."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from aurora_jobserver.artwork import ProcessSettings,load_scene
from aurora_jobserver.printer_settings import settings_from_xps
from aurora_jobserver.vector_only import HAIRLINE_MAX_MM,encode_candidate
from tools.compare_preference_jobs import decode,summary


def stage(source,destination,intake,*,measurement=False):
    source=Path(source).resolve();destination=Path(destination).resolve()
    data=source.read_bytes()
    if not 0<len(data)<=64*1024*1024:raise ValueError('Expected a bounded saved print')
    settings=settings_from_xps(source)
    other_holds=[h for h in settings.get('held_features',[]) if h!='Output']
    if other_holds:raise ValueError('Additional preferences remain held: '+', '.join(other_holds))
    destination.mkdir(parents=True,exist_ok=False)
    snapshot=destination/'source.oxps';snapshot.write_bytes(data)
    command=[str(Path(intake).resolve()),str(snapshot),str(destination/'intake'),
             '--dpi',str(settings['laser_dpi']),'--raster-grid','coreldraw-xp-draft',
             '--text-rendering','outline-aliased','--cut-color','any','--cut-paths-only','on',
             '--max-cut-width-mm',str(HAIRLINE_MAX_MM)]
    result=subprocess.run(command,shell=False,capture_output=True,text=True,timeout=120)
    if result.returncode:raise ValueError('Cut-path review failed: '+result.stderr)
    doc=json.loads((destination/'intake/document.json').read_text())
    if doc['source_sha256']!=hashlib.sha256(data).hexdigest():raise ValueError('Source changed')
    if len(doc['pages'])!=1:raise ValueError('Review requires one page')
    page=doc['pages'][0]
    if page['review_reasons']:raise ValueError('Unresolved cutting review: '+repr(page['review_reasons']))
    report={'state':'nothing_to_cut' if not page['cuts'] else 'vector_only_candidate',
            'source_sha256':doc['source_sha256'],'original_printer_settings':settings,
            'classification':'opaque solid hairline strokes, any color',
            'hairline_max_width_mm':HAIRLINE_MAX_MM,'cut_paths':len(page['cuts']),
            'production_vector_only_enabled':False,'physical_delivery_performed':False,
            'original_autostart':settings['autostart'],'candidate_autostart':False,
            'candidate_is_measurement':measurement}
    if page['cuts']:
        scene=load_scene(destination/'intake')
        raw,cg=encode_candidate(scene,ProcessSettings.parse(settings['process_settings']),
                                'VectorOnly167Test',draft=not measurement)
        ending='' if measurement else '.draft'
        (destination/('job.raw.jbs'+ending)).write_bytes(raw)
        (destination/('job.cg.jbs'+ending)).write_bytes(cg)
        decoded=decode(cg);raster=decoded['rasters'][0]
        assert raster['pixels']==b'\0' and raster['settings']['power']==0
        assert not decoded['autostart'] and len(decoded['vector_paths'])==len(scene.paths)
        report['decoded']=summary(decoded)
        report['paths_units']=[list(map(list,p)) for p in scene.paths]
        report['cg_sha256']=hashlib.sha256(cg).hexdigest()
    (destination/'review.json').write_text(json.dumps(report,indent=2,default=float))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path);parser.add_argument('destination',type=Path)
    parser.add_argument('--intake',type=Path,required=True)
    parser.add_argument('--measurement',action='store_true',help='Stage one unmarked measurement candidate; does not send')
    args=parser.parse_args()
    result=stage(args.source,args.destination,args.intake,measurement=args.measurement)
    print(json.dumps({k:v for k,v in result.items() if k not in ('decoded','original_printer_settings','paths_units')}))


if __name__=='__main__':main()
