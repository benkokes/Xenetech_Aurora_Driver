"""Native Windows conversion and automatic sending, exclusively to loopback.

The private Corel capture is copied and given synthetic driver PrintTicket
options. This tests the settings transport/converter, not driver installation.
"""
import hashlib
import io
import json
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch
import uuid
from xml.dom import minidom
import zipfile

from aurora_jobserver.artwork import ProcessSettings, _encode, load_scene
from aurora_jobserver.jbs import prepare
from aurora_jobserver.printer_settings import PRIVATE, PSF, default_selection, decode, make_ticket
from aurora_jobserver.print_pipeline import prepare_capture
from aurora_jobserver.print_capture import CaptureServer
from aurora_jobserver.print_service import PrintService, run_host, main as service_main
from aurora_jobserver.transport import Timing
from tools.controller_simulator import ControllerSimulator


ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT/'runtime/print-capture/1a0f7e91-725d-4daa-a037-3e822b54806e/source.bin'
INTAKE = ROOT/'build/frontend/Aurora.XpsIntake.exe'
CHECKED = ROOT/'runtime/coreldraw-compat-167-checked'
FAST = Timing(connect=1,handshake=1,job=3,sync_delay=.005,feature_delay=.005,sync_quiet=.005)


def document_with_settings(selection):
    out = io.BytesIO()
    with zipfile.ZipFile(CAPTURE) as original, zipfile.ZipFile(out,'w') as modified:
        for info in original.infolist():
            data = original.read(info.filename)
            if info.filename == 'Metadata/Job_PT.xml' and selection is not None:
                xml = minidom.parseString(data)
                properties = minidom.parseString(make_ticket(selection))
                xml.documentElement.setAttribute('xmlns:aur',PRIVATE)
                xml.documentElement.setAttribute('xmlns:psf',PSF)
                for feature in list(properties.documentElement.childNodes):
                    xml.documentElement.appendChild(xml.importNode(feature,True))
                data = xml.toxml(encoding='utf-8')
            modified.writestr(info,data)
    return out.getvalue()


def capture_document(root, data, *, queue='aurora-direct'):
    print_id = str(uuid.uuid4())
    folder = root/print_id
    folder.mkdir(parents=True)
    (folder/'source.bin').write_bytes(data)
    receipt = {'schema_version':1,'id':print_id,'state':'captured','queue':queue,'received_ns':1,
               'files':{'document':{'file':'source.bin','bytes':len(data),
                                    'sha256':hashlib.sha256(data).hexdigest()}}}
    (folder/'capture.json').write_text(json.dumps(receipt))
    return folder


@unittest.skipUnless(CAPTURE.is_file() and INTAKE.is_file() and CHECKED.is_dir(),
                     'Native frontend and private Corel reference required')
class PrintPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_corel_print_settings_convert_and_dispatch_automatically_once(self):
        selection = default_selection()
        document = document_with_settings(selection)
        service_root = self.root/'service'
        # Exercise the actual spooler-facing LPR receiver before conversion.
        with CaptureServer(service_root/'captures',port=0,queue='aurora-direct') as receiver:
            thread = threading.Thread(target=receiver.serve_forever,kwargs={'poll_interval':.01},daemon=True)
            thread.start()
            try:
                with socket.create_connection(receiver.server_address,timeout=3) as client:
                    client.sendall(b'\2aurora-direct\n')
                    self.assertEqual(client.recv(1),b'\0')
                    for kind,data in ((b'\2',b'Hlocal\nPxws\nJCorel direct print\n'),(b'\3',document)):
                        client.sendall(kind+str(len(data)).encode()+b' printfile\n')
                        self.assertEqual(client.recv(1),b'\0')
                        client.sendall(data+b'\0')
                        self.assertEqual(client.recv(1),b'\0')
                    client.shutdown(socket.SHUT_WR)
                    self.assertEqual(client.recv(1),b'')
            finally:
                receiver.shutdown(); thread.join()
        capture = next((service_root/'captures').glob('*/capture.json')).parent
        scene = load_scene(CHECKED)
        _, expected = _encode(scene,ProcessSettings.parse(decode(selection)['process_settings']),
                              'Print_'+capture.name[:8],draft=False)
        with ControllerSimulator(expected,echo=False,fragment=True,warning=True) as sim:
            service = PrintService(service_root,sim.endpoint,INTAKE,timing=FAST,locks=self.root/'locks')
            result = service.poll_once()
            self.assertEqual(result['state'],'completed_with_warning')
            self.assertFalse(result['auto_start'])
            job = result['id']
            settings = result['settings']['printer_settings']
            self.assertEqual(settings,decode(selection))
            self.assertEqual((service.store.directory(job)/'prepared.jbs').read_bytes(),expected)
            restarted = PrintService(service_root,sim.endpoint,INTAKE,timing=FAST,locks=self.root/'locks')
            self.assertIsNone(restarted.poll_once())
            self.assertEqual(len(service.store.list()),1)
            self.assertEqual(sum(e['kind']=='uploaded' for e in service.store.history(job)),1)

    def test_changed_properties_reach_commands_and_resume_preserves_them(self):
        selection = default_selection() | {'AuroraAutostart':'On','AuroraRasterPower':'Percent60',
            'AuroraRasterSpeed':'Speed20000','AuroraVectorPower':'Percent20',
            'AuroraVectorSpeed':'Speed500','AuroraVectorPPI':'PPI500'}
        folder = capture_document(self.root/'captures',document_with_settings(selection))
        output = self.root/'prepared'
        result = prepare_capture(folder,output,INTAKE)
        raw = (output/'job.raw.jbs').read_bytes()
        self.assertIn(b'autostart START\r',raw)
        self.assertNotIn(b'normalstart START\r',raw)
        self.assertIn(b'20000. speed\r60.00 power\r',raw)
        self.assertIn(b'500. speed\r20.00 power\r500. set_vppi\r',raw)
        self.assertTrue(prepare((output/'job.cg.jbs').read_bytes()).auto_start)
        with patch('aurora_jobserver.print_pipeline.subprocess.run') as render:
            self.assertEqual(prepare_capture(folder,output,INTAKE),result)
            render.assert_not_called()
        (output/'job.cg.jbs').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError,'integrity'):
            prepare_capture(folder,output,INTAKE)

    def test_single_print_host_stops_before_dispatching_a_second_capture(self):
        selection = default_selection()
        service_root = self.root/'single-print'
        first = capture_document(service_root/'captures',document_with_settings(selection))
        second = capture_document(service_root/'captures',document_with_settings(selection))
        receipt = json.loads((second/'capture.json').read_text())
        receipt['received_ns'] = 2
        (second/'capture.json').write_text(json.dumps(receipt))
        _, expected = _encode(load_scene(CHECKED),ProcessSettings.parse(decode(selection)['process_settings']),
                              'Print_'+first.name[:8],draft=False)
        with ControllerSimulator(expected,echo=False,fragment=True) as sim:
            service = PrintService(service_root,sim.endpoint,INTAKE,timing=FAST,locks=self.root/'locks')
            with CaptureServer(service.captures,port=0,queue='aurora-direct') as receiver:
                run_host(service,receiver,once=True)
            self.assertTrue(sim.upload_received.is_set())
            jobs = service.store.list()
            self.assertEqual(len(jobs),1)
            self.assertEqual(jobs[0]['settings']['direct_print']['print_id'],first.name)
            self.assertEqual(jobs[0]['state'],'completed')
            self.assertTrue((second/'capture.json').exists())
            self.assertFalse((service_root/'prepared-prints'/second.name).exists())
        status = json.loads((service_root/'status.json').read_text())
        self.assertEqual(status['state'],'stopped_after_one_print')

    def test_empty_root_guard_refuses_old_captures_before_starting_receiver(self):
        service_root = self.root/'old-root'
        service_root.mkdir()
        sentinel = service_root/'existing-capture'
        sentinel.write_bytes(b'preserve')
        with patch('aurora_jobserver.print_service.PrintService') as service, \
                patch('aurora_jobserver.print_service.CaptureServer') as receiver, \
                self.assertRaises(SystemExit) as stopped:
            service_main(['--root',str(service_root),'--host','127.0.0.1',
                          '--intake',str(INTAKE),'--once','--require-empty'])
        self.assertEqual(stopped.exception.code,2)
        service.assert_not_called()
        receiver.assert_not_called()
        self.assertEqual(sentinel.read_bytes(),b'preserve')
        self.assertEqual(list(service_root.iterdir()),[sentinel])

    def test_preview_prints_missing_properties_and_tampered_sources_do_not_convert(self):
        cases = [('aurora-capture',default_selection()),('aurora-direct',None)]
        for i,(queue,selection) in enumerate(cases):
            folder = capture_document(self.root/str(i),document_with_settings(selection),queue=queue)
            with patch('aurora_jobserver.print_pipeline.subprocess.run') as render:
                with self.assertRaises(ValueError):
                    prepare_capture(folder,self.root/('out'+str(i)),INTAKE)
                render.assert_not_called()
        folder = capture_document(self.root/'tamper',document_with_settings(default_selection()))
        (folder/'source.bin').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'integrity'):
            prepare_capture(folder,self.root/'bad',INTAKE)


if __name__ == '__main__':
    unittest.main()
