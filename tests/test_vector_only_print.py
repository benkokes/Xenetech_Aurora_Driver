"""Normal cut-only conversion, no-cut recovery, and loopback-only dispatch."""
from dataclasses import replace
from decimal import Decimal
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET
import zipfile

from aurora_jobserver.artwork import ProcessSettings,_encode,load_scene
from aurora_jobserver.print_pipeline import prepare_capture
from aurora_jobserver.print_service import PrintService
from tests.test_output_modes import full_document,settings,PROCESS
from tests.test_print_pipeline import CAPTURE,INTAKE,CHECKED,FAST,capture_document
from tools.compare_preference_jobs import decode
from tools.controller_simulator import ControllerSimulator


def vector_document(*,color='#ff000000',thick=False,autostart=False):
    out=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(full_document('VectorOnly',Autostart=autostart))) as original,zipfile.ZipFile(out,'w') as target:
        for entry in original.infolist():
            data=original.read(entry.filename)
            if entry.filename.endswith('.fpage'):
                page=ET.fromstring(data)
                for shape in page.iter():
                    if shape.tag.rsplit('}',1)[-1]=='Path' and 'Stroke' in shape.attrib:
                        shape.set('Stroke',color)
                        if thick:shape.set('StrokeThickness','0.666667')
                data=ET.tostring(page,encoding='utf-8',xml_declaration=True)
            target.writestr(entry,data)
    return out.getvalue()


@unittest.skipUnless(CAPTURE.is_file() and INTAKE.is_file() and CHECKED.is_dir(),'Native frontend and private X7 fixture required')
class VectorOnlyPrintTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_black_red_and_blue_hairlines_have_identical_cut_geometry_and_no_engraving(self):
        expected=load_scene(CHECKED).paths
        for color in ('#ff000000','#ffff0000','#ff0000ff'):
            with self.subTest(color=color):
                capture=capture_document(self.root/'captures',vector_document(color=color))
                output=self.root/capture.name
                with patch('socket.create_connection') as network:
                    result=prepare_capture(capture,output,INTAKE)
                    network.assert_not_called()
                job=decode((output/'job.cg.jbs').read_bytes())
                self.assertEqual(result['state'],'encoded_for_direct_print')
                self.assertEqual([p['points'] for p in job['vector_paths']],[[list(map(float,p)) for p in path] for path in expected])
                self.assertEqual(job['rasters'][0]['pixels'],b'\0')
                self.assertEqual(job['rasters'][0]['settings']['power'],0)
                self.assertFalse(job['autostart'])

    def test_autostart_choice_is_retained_for_a_valid_vector_print(self):
        capture=capture_document(self.root/'captures',vector_document(autostart=True))
        output=self.root/'prepared';prepare_capture(capture,output,INTAKE)
        self.assertTrue(decode((output/'job.cg.jbs').read_bytes())['autostart'])

    def test_thick_line_noop_is_durable_local_and_does_not_block_corrected_print(self):
        from aurora_jobserver.transport import Endpoint
        service_root=self.root/'service'
        first=capture_document(service_root/'captures',vector_document(thick=True,autostart=True))
        service=PrintService(service_root,Endpoint('127.0.0.1'),INTAKE,timing=FAST,locks=self.root/'locks')
        with patch('socket.create_connection') as network:
            self.assertEqual(service.poll_once()['state'],'nothing_to_cut')
            self.assertEqual(service.store.list(),[])
            self.assertEqual(len(service.store.print_outcomes()),1)
            self.assertIsNone(service.poll_once())
            restarted=PrintService(service_root,Endpoint('127.0.0.1'),INTAKE,timing=FAST,locks=self.root/'locks')
            with patch('aurora_jobserver.print_pipeline.subprocess.run') as render:
                self.assertIsNone(restarted.poll_once())
                render.assert_not_called()
            network.assert_not_called()
        self.assertFalse(list(self.root.rglob('*.pending.json')))
        self.assertFalse((service_root/'prepared-prints'/first.name/'job.cg.jbs').exists())
        # A corrected deliberate Print has its own UUID; it can run once.
        second=capture_document(service_root/'captures',vector_document())
        source=load_scene(CHECKED)
        carrier=replace(source,page=dict(source.page,exposure={'width':1,'height':1,'x_pixels':0,'y_pixels':0}),exposure=b'\0')
        process=replace(ProcessSettings.parse(PROCESS),raster_power_percent=Decimal(0))
        _,expected=_encode(carrier,process,'Print_'+second.name[:8],draft=False)
        with ControllerSimulator(expected,echo=False,fragment=True) as sim:
            corrected=PrintService(service_root,sim.endpoint,INTAKE,timing=FAST,locks=self.root/'locks')
            result=corrected.poll_once()
            self.assertEqual(result['state'],'completed')
            self.assertTrue(sim.upload_received.is_set())
            self.assertIsNone(corrected.poll_once())
            self.assertEqual(len(corrected.store.list()),1)
            self.assertEqual(sum(e['kind']=='uploaded' for e in corrected.store.history(result['id'])),1)
            with self.assertRaisesRegex(ValueError,'nothing-to-cut'):
                corrected.bridge.accept(service_root/'prepared-prints'/second.name/'job.cg.jbs',first.name,settings('VectorOnly'))

    def test_no_cut_resume_revalidates_evidence_and_rejects_conflicting_outcomes(self):
        from aurora_jobserver.store import JobStore
        capture=capture_document(self.root/'captures',vector_document(thick=True))
        output=self.root/'prepared';result=prepare_capture(capture,output,INTAKE)
        with patch('aurora_jobserver.print_pipeline.subprocess.run') as render:
            self.assertEqual(prepare_capture(capture,output,INTAKE),result)
            render.assert_not_called()
        store=JobStore(self.root/'queue');store.record_no_cut(result);store.record_no_cut(result)
        with self.assertRaisesRegex(ValueError,'changed'):
            store.record_no_cut(dict(result,message='Changed result'))
        manifest=output/'intake/document.json';doc=json.loads(manifest.read_text())
        doc['pages'][0]['cuts']=[{'closed':False,'points_mm':[[10,10],[20,20]]}]
        manifest.write_text(json.dumps(doc))
        with self.assertRaises(ValueError):prepare_capture(capture,output,INTAKE)


if __name__=='__main__':unittest.main()
