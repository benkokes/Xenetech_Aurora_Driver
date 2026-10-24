"""Stage, without sending, one explicit per-color validation of saved artwork.

This creates a NEW synthetic PrintTicket and capture. It does not claim a fresh
CorelDRAW print or a user-selected palette. This tool never sends its output.
"""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
from xml.dom import minidom
import xml.etree.ElementTree as ET
import zipfile

from aurora_jobserver.artwork import load_scene
from aurora_jobserver.classic_settings import PARAMETER, carriers, parse
from aurora_jobserver.print_pipeline import prepare_capture
from aurora_jobserver.printer_settings import PRIVATE, PSF, settings_from_xps
from aurora_jobserver.store import atomic_write
from tools.compare_preference_jobs import decode


PALETTE = {
    'Black':('1','15',1000),
    'Red':('1.5','10',750),
    'Blue':('2','5',500),
}


def validation_document(source, *, palette=None, changes=None):
    palette=PALETTE if palette is None else palette
    original_settings=settings_from_xps(source)
    if original_settings.get('schema_version')!=2 or original_settings.get('held_features'):
        raise ValueError('Expected a saved, complete, supported Corel print settings snapshot')
    output=io.BytesIO()
    changed=False
    with zipfile.ZipFile(source) as original,zipfile.ZipFile(output,'w') as target:
        for entry in original.infolist():
            data=original.read(entry.filename)
            if entry.filename=='Metadata/Job_PT.xml':
                ticket=minidom.parseString(data)
                ticket.documentElement.setAttribute('xmlns:aur',PRIVATE)
                nodes=[node for node in ticket.getElementsByTagNameNS(PSF,'ParameterInit')
                       if node.getAttribute('name').rsplit(':',1)[-1]==PARAMETER]
                if len(nodes)!=1:
                    raise ValueError('Expected one complete Aurora settings carrier')
                value=nodes[0].getElementsByTagNameNS(PSF,'Value')[0]
                prefs=ET.fromstring(base64.b64decode(value.firstChild.nodeValue))
                for key,text in {'Output':'VectorOnly','UseColors':'true','Autostart':'false',
                    'SortColors':'true','PauseColors':'false','Resolution':'167',
                    'BottomUp':'false','InvertRaster':'false',**(changes or {})}.items():
                    prefs.find(key).text=text
                for color in prefs.find('Colors'):
                    name=color.find('Name').text
                    color.find('Enabled').text='true' if name in palette else 'false'
                    if name in palette:
                        speed,power,ppi=palette[name]
                        color.find('SpeedIps').text=speed
                        color.find('PowerPercent').text=power
                        color.find('Ppi').text=str(ppi)
                payload=base64.b64encode(ET.tostring(prefs,encoding='utf-8')).decode('ascii')
                value.firstChild.nodeValue=payload
                selected=carriers(parse(payload))
                for feature in ticket.getElementsByTagNameNS(PSF,'Feature'):
                    local=feature.getAttribute('name').rsplit(':',1)[-1]
                    if local.startswith('Job') and local[3:] in selected:
                        feature.getElementsByTagNameNS(PSF,'Option')[0].setAttribute('name','aur:'+selected[local[3:]])
                data=ticket.toxml(encoding='utf-8')
                changed=True
            target.writestr(entry,data)
    if not changed:
        raise ValueError('Saved source has no job-level settings ticket')
    return output.getvalue(),original_settings


def stage(source, destination, intake):
    import uuid
    source=Path(source).resolve()
    destination=Path(destination).resolve()
    if destination.exists():
        raise ValueError('Use a new staging directory; existing evidence is immutable')
    if not 0<source.stat().st_size<=64*1024*1024:
        raise ValueError('Source exceeds the capture size limit')
    data,original_settings=validation_document(source)
    print_id=str(uuid.uuid4())
    capture=destination/'captures'/print_id
    capture.mkdir(parents=True,exist_ok=False)
    atomic_write(capture/'source.bin',data)
    receipt={'schema_version':1,'id':print_id,'state':'captured','queue':'aurora-direct',
        'received_ns':1,'files':{'document':{'file':'source.bin','bytes':len(data),
                                           'sha256':hashlib.sha256(data).hexdigest()}}}
    atomic_write(capture/'capture.json',json.dumps(receipt,indent=2).encode())
    prepared=destination/'prepared'
    result=prepare_capture(capture,prepared,intake,allow_color_vectors=True)
    if result['state']!='encoded_for_direct_print':
        raise ValueError('Validation artwork has no enabled hairline cuts')
    scene=load_scene(prepared/'intake')
    colors=[cut['color'] for cut in scene.page['cuts']]
    allowed={'#FF000000':'Black','#FFFF0000':'Red','#FF0000FF':'Blue'}
    if set(colors)!=set(allowed):
        raise ValueError('Expected Black, Red and Blue only; do not stage different artwork')
    job=decode((prepared/'job.cg.jbs').read_bytes())
    if job['autostart'] or len(job['rasters'])!=1 or job['rasters'][0]['pixels']!=b'\0' or job['rasters'][0]['settings']['power']!=0:
        raise ValueError('Validation lost its normal-start zero-exposure carrier')
    points=[point for path in job['vector_paths'] for point in path['points']]
    bounds=[min(p[0] for p in points)/1000,min(p[1] for p in points)/1000,
            max(p[0] for p in points)/1000,max(p[1] for p in points)/1000]
    report={'state':'staged_not_sent_waiting_for_operator_readiness',
        'title':job['title'],'source_file':str(source),'original_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'original_settings':original_settings,'new_settings':result['printer_settings'],
        'synthetic_print_ticket_not_new_corel_print':True,'physical_device_io':False,
        'palette':{name:{'speed_ips':speed,'power_percent':power,'ppi':ppi}
                   for name,(speed,power,ppi) in PALETTE.items()},
        'color_path_counts':{name:colors.count(rgb) for rgb,name in allowed.items()},
        'cut_path_count':len(job['vector_paths']),'cut_bounds_inches_left_top_right_bottom':bounds,
        'zero_power_carrier_moves_to_origin':True,'autostart':job['autostart'],
        'cg_sha256':result['cg_sha256'],'raw_sha256':result['raw_sha256'],
        'normal_service_per_color_vector_support':True}
    atomic_write(destination/'staging.json',json.dumps(report,indent=2).encode())
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('saved_source',type=Path)
    parser.add_argument('destination',type=Path)
    parser.add_argument('--intake',type=Path,required=True)
    args=parser.parse_args()
    report=stage(args.saved_source,args.destination,args.intake)
    print(json.dumps({key:report[key] for key in ('state','title','color_path_counts',
        'cut_bounds_inches_left_top_right_bottom','physical_device_io')}))


if __name__=='__main__':
    main()
