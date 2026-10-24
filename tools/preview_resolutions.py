"""Render the original DPI choices offline; never encode or deliver a laser job."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


ORIGINAL_DPI=(50,100,167,200,250,333,500,1000,1200)
ROOT=Path(__file__).resolve().parents[1]


def preview(source,destination,*,resolutions=ORIGINAL_DPI,intake=None):
    source,destination=Path(source),Path(destination)
    intake=Path(intake or ROOT/'build/frontend/Aurora.XpsIntake.exe').resolve()
    resolutions=tuple(resolutions)
    if not resolutions or len(set(resolutions))!=len(resolutions) or any(type(d) is not int or d not in ORIGINAL_DPI for d in resolutions):
        raise ValueError('Choose distinct original driver resolutions.')
    if not intake.is_file():
        raise ValueError('Build the native XPS intake first.')
    with source.open('rb') as stream:
        data=stream.read(64*1024*1024+1)
    if not 0<len(data)<=64*1024*1024:
        raise ValueError('Source must be nonempty and at most 64 MiB.')
    source_hash=hashlib.sha256(data).hexdigest()
    destination.mkdir(parents=True,exist_ok=False)
    snapshot=destination/'source.bin'
    snapshot.write_bytes(data)
    rows=[]
    for dpi in resolutions:
        output=destination/('dpi-'+str(dpi))
        result=subprocess.run([str(intake),str(snapshot.resolve()),str(output.resolve()),
            '--dpi',str(dpi),'--tiled-raster','on','--raster-grid','document-dpi',
            '--text-rendering','outline-aliased','--cut-color','#FF0000','--max-cut-width-mm','0.2'],
            capture_output=True,text=True,shell=False,timeout=120)
        if result.returncode:
            raise ValueError(f'{dpi} DPI preview failed: '+(result.stderr or result.stdout)[-2000:])
        document=json.loads((output/'document.json').read_text())
        if document['source_sha256']!=source_hash or document['raster_grid']!='document-dpi' or not document['tiled_raster']:
            raise ValueError('Preview source or mode changed.')
        rows.append({'dpi':dpi,'pages':[{'number':page['number'],
            'surface_pixels':[page['pixel_width'],page['pixel_height']],
            'preview_origin_pixels':[page['preview_x_pixels'],page['preview_y_pixels']],
            'exposure':page['exposure'],'vector_paths':len(page['cuts']),
            'review_reasons':page['review_reasons']} for page in document['pages']]})
    report={'schema_version':1,'validation':'offline_document_grid_not_XP_calibration',
            'source_sha256':source_hash,'resolutions':rows,'laser_job_encoded':False,
            'physical_device_io_performed':False}
    (destination/'resolution-review.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('destination',type=Path)
    parser.add_argument('--resolutions',type=int,nargs='+',choices=ORIGINAL_DPI,default=ORIGINAL_DPI)
    args=parser.parse_args()
    report=preview(args.source,args.destination,resolutions=args.resolutions)
    print(json.dumps({'source_sha256':report['source_sha256'],
                      'dpi':[r['dpi'] for r in report['resolutions']],
                      'report':str(args.destination/'resolution-review.json')},indent=2))


if __name__=='__main__':
    main()
