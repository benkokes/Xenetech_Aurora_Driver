"""Stage a normal-start bottom-up raster check; never connect or send."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import uuid
from xml.dom import minidom
import xml.etree.ElementTree as ET
import zipfile

from aurora_jobserver.classic_settings import PARAMETER, carriers, parse
from aurora_jobserver.print_pipeline import prepare_capture
from aurora_jobserver.printer_settings import PRIVATE, PSF, settings_from_xps
from aurora_jobserver.store import atomic_write
from tools.compare_preference_jobs import decode


def stage(source, baseline_job, destination, intake):
    source, baseline_job, destination=Path(source),Path(baseline_job),Path(destination)
    if destination.exists():raise ValueError('Preserve previous evidence; use a new staging directory')
    initial=settings_from_xps(source)
    if initial.get('schema_version')!=2 or initial['held_features']:
        raise ValueError('Expected a supported saved native source')
    output=io.BytesIO()
    with zipfile.ZipFile(source) as original,zipfile.ZipFile(output,'w') as target:
        for entry in original.infolist():
            data=original.read(entry.filename)
            if entry.filename=='Metadata/Job_PT.xml':
                ticket=minidom.parseString(data)
                ticket.documentElement.setAttribute('xmlns:aur',PRIVATE)
                nodes=[p for p in ticket.getElementsByTagNameNS(PSF,'ParameterInit')
                       if p.getAttribute('name').rsplit(':',1)[-1]==PARAMETER]
                if len(nodes)!=1:raise ValueError('Expected one complete preferences carrier')
                value=nodes[0].getElementsByTagNameNS(PSF,'Value')[0]
                prefs=ET.fromstring(base64.b64decode(value.firstChild.nodeValue))
                for key,text in {'Output':'RasterOnly','UseColors':'false','BottomUp':'true',
                    'InvertRaster':'false','Autostart':'false','Resolution':'167',
                    'RasterPower':'45','RasterSpeed':'30'}.items():
                    prefs.find(key).text=text
                payload=base64.b64encode(ET.tostring(prefs,encoding='utf-8')).decode('ascii')
                value.firstChild.nodeValue=payload
                selected=carriers(parse(payload))
                for feature in ticket.getElementsByTagNameNS(PSF,'Feature'):
                    local=feature.getAttribute('name').rsplit(':',1)[-1]
                    if local.startswith('Job') and local[3:] in selected:
                        feature.getElementsByTagNameNS(PSF,'Option')[0].setAttribute('name','aur:'+selected[local[3:]])
                data=ticket.toxml(encoding='utf-8')
            target.writestr(entry,data)
    data=output.getvalue()
    print_id=str(uuid.uuid4())
    capture=destination/'captures'/print_id
    capture.mkdir(parents=True,exist_ok=False)
    atomic_write(capture/'source.bin',data)
    receipt={'schema_version':1,'id':print_id,'state':'captured','queue':'aurora-direct',
        'received_ns':1,'files':{'document':{'file':'source.bin','bytes':len(data),
                                           'sha256':hashlib.sha256(data).hexdigest()}}}
    atomic_write(capture/'capture.json',json.dumps(receipt,indent=2).encode())
    prepared=destination/'prepared'
    result=prepare_capture(capture,prepared,intake)
    candidate=decode((prepared/'job.cg.jbs').read_bytes())
    baseline=decode(baseline_job.read_bytes())
    if len(baseline['rasters'])!=1 or len(candidate['rasters'])!=1 or candidate['vector_paths'] or candidate['autostart']:
        raise ValueError('Expected one normal-start raster and no cuts')
    before,after=baseline['rasters'][0],candidate['rasters'][0]
    w,h=before['width'],before['height']
    expected=b''.join(before['pixels'][y*w:(y+1)*w] for y in range(h-1,-1,-1))
    if (after['width']!=w or after['height']!=h or after['pixels']!=expected
            or after['origin_label']!='LL' or before['origin_label']!='UL'
            or after['origin_units']!=[before['origin_units'][0],before['origin_units'][1]+(h-1)*6]
            or after['settings']['speed']!=30000 or after['settings']['power']!=45
            or after['resolution_dpi']!=[167,167]):
        raise ValueError('Bottom-up does not preserve the accepted raster with the expected scan transform')
    report={'state':'staged_not_sent_waiting_for_operator_readiness','title':candidate['title'],
        'synthetic_ticket_not_new_corel_print':True,'physical_device_io':False,
        'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'accepted_baseline_sha256':hashlib.sha256(baseline_job.read_bytes()).hexdigest(),
        'cg_sha256':result['cg_sha256'],'settings':result['printer_settings'],
        'raster_size':[w,h],'baseline_upper_left_units':before['origin_units'],
        'bottom_up_lower_left_units':after['origin_units'],
        'pixels_exact_reverse_rows_of_accepted_print':True,'cut_paths':0,'autostart':False,
        'material_guide_inches':[.9,.9,7.1,5.7]}
    atomic_write(destination/'staging.json',json.dumps(report,indent=2).encode())
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('saved_source',type=Path)
    parser.add_argument('accepted_baseline_job',type=Path)
    parser.add_argument('destination',type=Path)
    parser.add_argument('--intake',type=Path,required=True)
    args=parser.parse_args()
    report=stage(args.saved_source,args.accepted_baseline_job,args.destination,args.intake)
    print(json.dumps({key:report[key] for key in ('state','title','raster_size',
        'baseline_upper_left_units','bottom_up_lower_left_units','cg_sha256','physical_device_io')}))


if __name__=='__main__':main()
