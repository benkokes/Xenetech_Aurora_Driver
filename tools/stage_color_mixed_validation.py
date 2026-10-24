"""Stage one owned Corel capture as a mixed-color physical candidate. Never send."""
import argparse
import hashlib
import json
from pathlib import Path
import uuid
import io
import zipfile
import tempfile
from xml.dom import minidom

from aurora_jobserver.print_pipeline import prepare_capture
from aurora_jobserver.color_scene import load_color_scene
from aurora_jobserver.printer_settings import PSF,PRIVATE
from tools.stage_color_vector_validation import validation_document
from tools.compare_preference_jobs import decode

PALETTE={'Black':('30','45',1000),'Navy':('30','35',1000),'Lime':('30','40',1000),
         'Red':('1.5','10',750),'Blue':('2','5',500)}


def stage(source,destination,intake,ticket_template):
    source,destination=Path(source),Path(destination)
    if destination.exists():raise ValueError('Choose a fresh staging directory')
    # Corel Reset emits the legacy scalar ticket. Import ONLY the full settings
    # carrier from a saved supported job, then explicitly replace its values.
    # This is synthetic test preparation, never a claim about UI selections.
    output=io.BytesIO()
    with zipfile.ZipFile(ticket_template) as template:
        saved=minidom.parseString(template.read('Metadata/Job_PT.xml'))
    with zipfile.ZipFile(source) as original,zipfile.ZipFile(output,'w') as target:
        for entry in original.infolist():
            content=original.read(entry.filename)
            if entry.filename=='Metadata/Job_PT.xml':
                ticket=minidom.parseString(content);ticket.documentElement.setAttribute('xmlns:aur',PRIVATE)
                for i in range(saved.documentElement.attributes.length):
                    attr=saved.documentElement.attributes.item(i)
                    if attr.name.startswith('xmlns:'):
                        if ticket.documentElement.hasAttribute(attr.name) and ticket.documentElement.getAttribute(attr.name)!=attr.value:
                            raise ValueError('Settings template namespace conflicts with captured artwork')
                        ticket.documentElement.setAttribute(attr.name,attr.value)
                for node in list(ticket.documentElement.childNodes):
                    if (node.nodeType==node.ELEMENT_NODE and node.namespaceURI==PSF
                            and node.getAttribute('name').rsplit(':',1)[-1].startswith(('JobAurora','PageDevmodeSnapshot'))):
                        ticket.documentElement.removeChild(node)
                for node in saved.documentElement.childNodes:
                    if (node.nodeType==node.ELEMENT_NODE and node.namespaceURI==PSF
                            and node.getAttribute('name').rsplit(':',1)[-1].startswith('JobAurora')):
                        ticket.documentElement.appendChild(ticket.importNode(node,True))
                content=ticket.toxml(encoding='utf-8')
            target.writestr(entry,content)
    with tempfile.TemporaryDirectory() as temp:
        snapshot=Path(temp)/'synthetic-settings-seed.oxps';snapshot.write_bytes(output.getvalue())
        data,initial=validation_document(snapshot,palette=PALETTE,changes={'Output':'RasterAndVector'})
    print_id=str(uuid.uuid4());capture=destination/'captures'/print_id
    capture.mkdir(parents=True)
    (capture/'source.bin').write_bytes(data)
    (capture/'capture.json').write_text(json.dumps({'schema_version':1,'id':print_id,'state':'captured',
        'queue':'aurora-direct','received_ns':1,'files':{'document':{'file':'source.bin','bytes':len(data),
        'sha256':hashlib.sha256(data).hexdigest()}}},indent=2))
    result=prepare_capture(capture,destination/'prepared',intake,allow_color_rasters=True)
    scene=load_color_scene(destination/'prepared/intake');job=decode((destination/'prepared/job.cg.jbs').read_bytes())
    assert scene.appearance_error<=2 and len(job['rasters'])==3 and len(job['vector_paths'])==2 and not job['autostart']
    assert [r['settings']['power'] for r in job['rasters']]==[45,35,40]
    assert [r['settings']['speed'] for r in job['rasters']]==[30000]*3
    assert {cut['color'] for cut in scene.page['cuts']}=={'#FFFF0000','#FF0000FF'}
    assert all(any(not any(r['pixels'][y*r['width']:(y+1)*r['width']]) for y in range(r['height'])) for r in job['rasters'])
    report={'state':'staged_not_sent_waiting_for_operator_readiness','title':job['title'],
        'source_file':str(source.resolve()),'original_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'synthetic_print_ticket_not_new_properties_selection':True,'original_settings':initial,
        'new_settings':result['printer_settings'],'palette':PALETTE,'raster_regions':3,'cut_paths':2,
        'appearance_max_channel_error':scene.appearance_error,'blank_row_gaps_preserved':True,
        'material_guide_inches_left_top_right_bottom':[.9,.9,3.8,2.9],
        'autostart':False,'physical_device_io':False,'cg_sha256':result['cg_sha256'],'raw_sha256':result['raw_sha256']}
    (destination/'staging.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('destination',type=Path)
    p.add_argument('--intake',type=Path,required=True);args=p.parse_args()
    r=stage(args.source,args.destination,args.intake,
        Path('runtime/desktop-jobserver/capture-only/a7263df0-84a6-4092-b295-4dfeb4c348b3/source.bin'))
    print(json.dumps({k:r[k] for k in ('state','title','raster_regions','cut_paths','appearance_max_channel_error','physical_device_io')}))
