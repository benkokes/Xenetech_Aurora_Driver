"""Per-job palette transport and native color printing; controller is loopback."""
import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import socket
import tempfile
import time
import unittest
from unittest.mock import patch
from xml.dom import minidom
from xml.etree import ElementTree as ET
import zipfile

from aurora_jobserver.classic_settings import PARAMETER
from aurora_jobserver.print_pipeline import prepare_capture
from aurora_jobserver.print_service import PrintService
from aurora_jobserver.printer_settings import PSF
from aurora_jobserver.transport import Endpoint
from tests.test_output_modes import full_document
from tests.test_print_pipeline import CAPTURE, INTAKE, CHECKED, FAST, capture_document
from tools.compare_preference_jobs import decode
from tools.controller_simulator import ControllerSimulator


def color_document(*, disabled=(), power_overrides=None, thick=False, output='VectorOnly',
                   autostart=False, **changes):
    """Synthetic full PrintTicket/paths built from the saved X7 source."""
    result=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(full_document(output,UseColors=True,Autostart=autostart,**changes))) as original, zipfile.ZipFile(result,'w') as target:
        for entry in original.infolist():
            data=original.read(entry.filename)
            if entry.filename=='Metadata/Job_PT.xml':
                ticket=minidom.parseString(data)
                for parameter in ticket.getElementsByTagNameNS(PSF,'ParameterInit'):
                    if parameter.getAttribute('name').rsplit(':',1)[-1] != PARAMETER:
                        continue
                    value=parameter.getElementsByTagNameNS(PSF,'Value')[0]
                    prefs=ET.fromstring(base64.b64decode(value.firstChild.nodeValue))
                    for color in prefs.find('Colors'):
                        color.find('SpeedIps').text='1'
                        color.find('PowerPercent').text='15'
                        name=color.find('Name').text
                        color.find('Enabled').text='false' if name in disabled else 'true'
                        if name=='Red':
                            color.find('SpeedIps').text='2'
                            color.find('PowerPercent').text='20'
                            color.find('Ppi').text='750'
                        elif name=='Blue':
                            color.find('SpeedIps').text='3'
                            color.find('PowerPercent').text='25'
                            color.find('Ppi').text='500'
                        if power_overrides and name in power_overrides:
                            color.find('PowerPercent').text=str(power_overrides[name])
                    value.firstChild.nodeValue=base64.b64encode(ET.tostring(prefs,encoding='utf-8')).decode('ascii')
                data=ticket.toxml(encoding='utf-8')
            elif entry.filename.endswith('.fpage'):
                page=ET.fromstring(data)
                for parent in list(page.iter()):
                    for child in list(parent):
                        if child.tag.rsplit('}',1)[-1]!='Path' or 'Stroke' not in child.attrib:
                            continue
                        child.set('Stroke','#ff000000')
                        if thick:child.set('StrokeThickness','0.666667')
                        for color in ('#ffff0000','#ff0000ff'):
                            clone=copy.deepcopy(child)
                            clone.set('Stroke',color)
                            parent.append(clone)
                data=ET.tostring(page,encoding='utf-8',xml_declaration=True)
            target.writestr(entry,data)
    return result.getvalue()


@unittest.skipUnless(CAPTURE.is_file() and INTAKE.is_file() and CHECKED.is_dir(),
                     'Native converter and private saved X7 source required')
class ColorVectorPrintTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_explicit_optout_holds_and_normal_route_carries_each_color_process(self):
        capture=capture_document(self.root/'captures',color_document())
        with patch('aurora_jobserver.print_pipeline.subprocess.run') as renderer:
            with self.assertRaisesRegex(ValueError,'UseColors'):
                prepare_capture(capture,self.root/'held',INTAKE,allow_color_vectors=False)
            renderer.assert_not_called()
        output=self.root/'validated'
        with patch('socket.create_connection') as network:
            result=prepare_capture(capture,output,INTAKE)
            network.assert_not_called()
        self.assertEqual(result['state'],'encoded_for_direct_print')
        self.assertTrue(result['printer_settings']['classic_preferences']['UseColors'])
        self.assertEqual(result['printer_settings']['held_features'],[])
        job=decode((output/'job.cg.jbs').read_bytes())
        self.assertFalse(job['draft'])
        self.assertFalse(job['autostart'])
        self.assertEqual(job['rasters'][0]['pixels'],b'\0')
        self.assertEqual(job['rasters'][0]['settings']['power'],0)
        actual=sorted(tuple(p['settings'][k] for k in ('speed','power','set_vppi')) for p in job['vector_paths'])
        self.assertEqual(actual,[(1000,15,1000),(2000,20,750),(3000,25,500)])

    def test_resume_respects_explicit_optout_and_keeps_attached_palette(self):
        first=capture_document(self.root/'captures',color_document())
        output=self.root/'first'
        initial=prepare_capture(first,output,INTAKE,allow_color_vectors=True)
        digest=hashlib.sha256((output/'job.cg.jbs').read_bytes()).hexdigest()
        with patch('aurora_jobserver.print_pipeline.subprocess.run') as renderer:
            self.assertEqual(prepare_capture(first,output,INTAKE,allow_color_vectors=True),initial)
            with self.assertRaisesRegex(ValueError,'UseColors'):
                prepare_capture(first,output,INTAKE,allow_color_vectors=False)
            renderer.assert_not_called()
        second=capture_document(self.root/'captures',color_document(power_overrides={'Red':21,'Blue':26}))
        prepare_capture(second,self.root/'second',INTAKE,allow_color_vectors=True)
        self.assertEqual(hashlib.sha256((output/'job.cg.jbs').read_bytes()).hexdigest(),digest)
        before=decode((output/'job.cg.jbs').read_bytes())
        after=decode((self.root/'second/job.cg.jbs').read_bytes())
        self.assertEqual(sorted(p['settings']['power'] for p in before['vector_paths']),[15,20,25])
        self.assertEqual(sorted(p['settings']['power'] for p in after['vector_paths']),[15,21,26])

    def test_all_disabled_is_durable_noop_then_corrected_print_sends_once(self):
        root=self.root/'service'
        capture=capture_document(root/'captures',color_document(disabled=('Black','Red','Blue')))
        service=PrintService(root,Endpoint('127.0.0.1'),INTAKE,timing=FAST,
                             locks=self.root/'locks')
        with patch('socket.create_connection') as network:
            self.assertEqual(service.poll_once()['state'],'nothing_to_cut')
            self.assertEqual(service.store.list(),[])
            outcome=service.store.print_outcomes()[0]
            self.assertIn('disabled',outcome['message'])
            self.assertIsNone(service.poll_once())
            restarted=PrintService(root,Endpoint('127.0.0.1'),INTAKE,timing=FAST,
                                   locks=self.root/'locks')
            self.assertIsNone(restarted.poll_once())
            self.assertFalse((root/'prepared-prints'/capture.name/'job.cg.jbs').exists())
            # Rechecking conversion verifies the enabled paths were all omitted,
            # rather than expecting an empty scene as in the thick-line case.
            prepare_capture(capture,root/'prepared-prints'/capture.name,INTAKE,allow_color_vectors=True)
            network.assert_not_called()
        second=capture_document(root/'captures',color_document())
        prepare_capture(second,self.root/'expected',INTAKE,allow_color_vectors=True)
        expected=(self.root/'expected/job.cg.jbs').read_bytes()
        connect=socket.create_connection
        def loopback_only(address,*args,**kwargs):
            if address[0]!='127.0.0.1':raise AssertionError('Physical connection forbidden')
            return connect(address,*args,**kwargs)
        with ControllerSimulator(expected,echo=False,fragment=True) as sim, patch('socket.create_connection',side_effect=loopback_only):
            corrected=PrintService(root,sim.endpoint,INTAKE,timing=FAST,
                                   locks=self.root/'locks')
            result=corrected.poll_once()
            self.assertEqual(result['state'],'completed')
            self.assertIsNone(corrected.poll_once())
            self.assertEqual(sum(e['kind']=='uploaded' for e in corrected.store.history(result['id'])),1)
            self.assertEqual(len(corrected.store.list()),1)

    def test_noop_resume_rejects_changed_enabled_colors(self):
        capture=capture_document(self.root/'captures',color_document(disabled=('Black','Red','Blue')))
        output=self.root/'prepared'
        prepare_capture(capture,output,INTAKE,allow_color_vectors=True)
        result=json.loads((output/'print-job.json').read_text())
        result['printer_settings']['classic_preferences']['Colors'][0]['Enabled']=True
        (output/'print-job.json').write_text(json.dumps(result))
        with self.assertRaisesRegex(ValueError,'Nothing-to-cut evidence changed'):
            prepare_capture(capture,output,INTAKE,allow_color_vectors=True)

    def test_thick_colored_lines_remain_nothing_to_cut(self):
        capture=capture_document(self.root/'captures',color_document(thick=True))
        result=prepare_capture(capture,self.root/'prepared',INTAKE,allow_color_vectors=True)
        self.assertEqual(result['state'],'nothing_to_cut')
        self.assertIn('hairline',result['message'])

    def test_autostart_is_preserved_only_from_the_per_job_snapshot(self):
        capture=capture_document(self.root/'captures',color_document(autostart=True))
        prepare_capture(capture,self.root/'prepared',INTAKE,allow_color_vectors=True)
        self.assertTrue(decode((self.root/'prepared/job.cg.jbs').read_bytes())['autostart'])

    def test_color_vectors_keep_unverified_features_and_explicit_mode_optout_held(self):
        cases=({'output':'RasterAndVector'},{'output':'RasterOnly'},{'Mirror':True},
               {'Cylindrical':True},{'Resolution':100},{'DitherBitmaps':True})
        for case in cases:
            with self.subTest(case=case):
                capture=capture_document(self.root/'captures',color_document(**case))
                with patch('aurora_jobserver.print_pipeline.subprocess.run') as renderer:
                    with self.assertRaisesRegex(ValueError,'Print held'):
                        prepare_capture(capture,self.root/capture.name,INTAKE,allow_color_vectors=True,allow_color_rasters=False)
                    renderer.assert_not_called()

    def test_desktop_default_print_route_delivers_colors_once_to_loopback(self):
        from dataclasses import replace
        from aurora_jobserver.artwork import ProcessSettings,load_scene
        from aurora_jobserver.color_vector_job import _encode_color_vector_job
        from aurora_jobserver.corel_layout import COREL_HAIRLINE_MAX_MM
        from aurora_jobserver.desktop_server import DesktopJobServer
        from aurora_jobserver.printer_settings import settings_from_xps

        backend=None
        def expected():
            capture=next(backend.service.captures.glob('*/capture.json')).parent
            settings=settings_from_xps(capture/'source.bin')
            base=load_scene(CHECKED)
            cuts=[]
            for color in ('#FF000000','#FFFF0000','#FF0000FF'):
                cut=dict(base.page['cuts'][0],color=color)
                cuts.append(cut)
            scene=replace(base,manifest=base.manifest | {'cut_color':'any',
                'max_cut_width_mm':COREL_HAIRLINE_MAX_MM},
                page=base.page | {'cuts':cuts},paths=base.paths*3)
            prefs=settings['classic_preferences']
            return _encode_color_vector_job(scene,ProcessSettings.parse(settings['process_settings']),
                prefs['Colors'],'Print_'+capture.name[:8],sort_colors=prefs['SortColors'],
                pause_colors=prefs['PauseColors'],draft=False)[1]

        connect=socket.create_connection
        def loopback_only(address,*args,**kwargs):
            if address[0]!='127.0.0.1':raise AssertionError('Physical connection forbidden')
            return connect(address,*args,**kwargs)
        with ControllerSimulator(expected,echo=False,fragment=True) as sim, patch('socket.create_connection',side_effect=loopback_only):
            backend=DesktopJobServer(self.root/'desktop',INTAKE,port=0,endpoint=sim.endpoint,
                timing=FAST,locks=self.root/'locks')
            backend.start()
            try:
                self.assertEqual(backend.snapshot()['mode'],'capture_only')
                backend.enable_live()
                with socket.create_connection(backend.server.server_address,timeout=3) as client:
                    client.sendall(b'\2aurora-direct\n')
                    self.assertEqual(client.recv(1),b'\0')
                    for kind,data in ((b'\2',b'Hlocal\nPtest\nJColor vector test\n'),(b'\3',color_document())):
                        client.sendall(kind+str(len(data)).encode()+b' printfile\n')
                        self.assertEqual(client.recv(1),b'\0')
                        client.sendall(data+b'\0')
                        self.assertEqual(client.recv(1),b'\0')
                    client.shutdown(socket.SHUT_WR)
                    self.assertEqual(client.recv(1),b'')
                deadline=time.monotonic()+12
                while time.monotonic()<deadline:
                    rows=backend.snapshot()['rows']
                    if rows and rows[0]['state']=='completed':break
                    time.sleep(.02)
                self.assertEqual(rows[0]['state'],'completed',backend.snapshot())
                self.assertTrue(sim.upload_received.is_set())
                store=backend.service.store
                self.assertEqual(sum(e['kind']=='uploaded' for e in store.history(rows[0]['job_id'])),1)
                self.assertEqual(rows[0]['settings']['held_features'],[])
                status=json.loads((self.root/'desktop/desktop-status.json').read_text())
                self.assertEqual(status['print_pipeline_version'],4)
                self.assertEqual(status['per_color_raster_dpi'],[167])
                self.assertEqual(status['per_color_mixed_dpi'],[167])
                self.assertEqual(status['per_color_vector_dpi'],[167])
                backend.capture_only()
            finally:
                backend.close()
                self.assertTrue(backend.wait_closed(12))


if __name__=='__main__':
    unittest.main()
