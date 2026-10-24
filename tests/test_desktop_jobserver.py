"""Desktop lifecycle against real LPR, converter and loopback controller only."""
from dataclasses import asdict
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch, MagicMock

from aurora_jobserver.artwork import ProcessSettings, _encode, load_scene
from aurora_jobserver.desktop_server import DesktopJobServer
from aurora_jobserver.printer_settings import default_selection, decode
from aurora_jobserver.sender import DeviceGuard
from aurora_jobserver.transport import Endpoint
from aurora_jobserver.worker import process_one
from tools.controller_simulator import ControllerSimulator
from test_print_pipeline import CAPTURE, INTAKE, CHECKED, FAST, document_with_settings, capture_document


@unittest.skipUnless(CAPTURE.is_file() and INTAKE.is_file() and CHECKED.is_dir(),
                     'Native frontend and private Corel reference required')
class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.document=document_with_settings(default_selection())
        self.backends=[]
        self.addCleanup(self.shutdown)

    def shutdown(self):
        for backend in self.backends:
            backend.close()
            self.assertTrue(backend.wait_closed(12),'Desktop failed to stop')

    def start(self, endpoint=None, *, start_enabled=False):
        backend=DesktopJobServer(self.root/'desktop',INTAKE,port=0,
            endpoint=endpoint or Endpoint('127.0.0.1'),timing=FAST,locks=self.root/'locks')
        backend.start(start_enabled=start_enabled)
        self.backends.append(backend)
        return backend

    def until(self, predicate, timeout=12):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            result=predicate()
            if result:
                return result
            time.sleep(.02)
        self.fail('Timed out waiting for desktop state')

    def print_job(self, backend, document=None, queue=b'aurora-direct'):
        with socket.create_connection(backend.server.server_address,timeout=3) as client:
            client.sendall(b'\2'+queue+b'\n')
            self.assertEqual(client.recv(1),b'\0')
            for kind,data in ((b'\2',b'Hlocal\nPxws\nJDesktop Corel test\n'),
                              (b'\3',self.document if document is None else document)):
                client.sendall(kind+str(len(data)).encode()+b' printfile\n')
                self.assertEqual(client.recv(1),b'\0')
                client.sendall(data+b'\0')
                self.assertEqual(client.recv(1),b'\0')
            client.shutdown(socket.SHUT_WR)
            self.assertEqual(client.recv(1),b'')

    def expected(self, backend):
        # Independently encode the checked artwork, never the worker's output.
        capture=next(backend.service.captures.glob('*/capture.json')).parent
        return _encode(load_scene(CHECKED),ProcessSettings.parse(decode(default_selection())['process_settings']),
                       'Print_'+capture.name[:8],draft=False)[1]

    def test_capture_only_and_restart_never_replay_old_prints(self):
        backend=self.start()
        with patch('aurora_jobserver.desktop_server.socket.create_connection') as network:
            self.print_job_unpatched(backend)
            self.until(lambda:backend.snapshot()['rows'])
            self.assertEqual(backend.snapshot()['rows'][0]['state'],'captured_locally')
            backend.enable_live()
            time.sleep(.3)
            self.assertEqual(backend.service.store.list(),[])
            network.assert_not_called()
        backend.capture_only()
        old=capture_document(backend.service.captures,self.document).name
        backend.close()
        self.assertTrue(backend.wait_closed(5))
        restarted=self.start()
        self.until(lambda:len(restarted.snapshot()['rows'])==2)
        self.assertEqual(restarted.snapshot()['mode'],'capture_only')
        self.assertEqual(next(r for r in restarted.snapshot()['rows'] if r['id']==old)['state'],'held')
        restarted.enable_live()
        time.sleep(.3)
        self.assertEqual(restarted.service.store.list(),[])

    def test_enabled_start_uses_fresh_session_and_prints_only_new_submissions(self):
        old=self.start()
        captured=capture_document(old.capture_root,self.document).name
        old.enable_live();old.capture_only()
        waiting=capture_document(old.service.captures,self.document).name
        old_session=old.session
        old.close();self.assertTrue(old.wait_closed(5))
        with ControllerSimulator(lambda:self.expected(backend),echo=False) as sim:
            backend=self.start(sim.endpoint,start_enabled=True)
            self.assertEqual(backend.snapshot()['mode'],'live')
            self.assertNotEqual(backend.session,old_session)
            self.until(lambda:len(backend.snapshot()['rows'])==2)
            rows={r['id']:r for r in backend.snapshot()['rows']}
            self.assertEqual(rows[captured]['state'],'captured_locally')
            self.assertEqual(rows[waiting]['state'],'held')
            self.assertFalse(sim.upload_received.is_set())
            self.print_job(backend)
            self.until(lambda:any(r['state']=='completed' for r in backend.snapshot()['rows']))
            self.assertEqual(len(backend.service.store.list()),1)
            job=backend.service.store.list()[0]['id']
            self.assertEqual(sum(e['kind']=='uploaded' for e in backend.service.store.history(job)),1)

    def test_enabled_start_preserves_unresolved_guard_and_leaves_capture_only(self):
        with DeviceGuard('127.0.0.1',self.root/'locks') as guard:
            guard.marker.write_text('{"unresolved_prior_delivery":true}')
        with patch('aurora_jobserver.desktop_server.socket.create_connection') as network:
            backend=self.start(start_enabled=True)
            state=backend.snapshot()
            self.assertEqual(state['mode'],'capture_only')
            self.assertIn('earlier delivery is unresolved',state['error'])
            self.assertIsNone(backend.session)
            self.assertTrue(guard.marker.exists())
            network.assert_not_called()

    def test_history_ignores_unpublished_receipts_before_reading_them(self):
        backend=DesktopJobServer(self.root/'desktop',INTAKE,port=0,
            endpoint=Endpoint('127.0.0.1'),locks=self.root/'locks')
        pending=backend.capture_root/'.receiving-63fb32fb-dc87-43f1-9856-d3e5a15dedfc'
        pending.mkdir()
        # A receipt may be incomplete, complete, or a failed rename's leftover.
        # None is a published capture; the catalog must never open it.
        (pending/'capture.json').write_text('{partial receipt')
        published=capture_document(backend.capture_root,self.document)
        backend._collect()
        self.assertEqual(list(backend.inventory),[published.name])
        self.assertEqual(backend.error,'')
        self.assertEqual(backend.mode,'capture_only')

    def print_job_unpatched(self, backend):
        # The receiver path must remain real even while laser connections are mocked.
        with socket.socket() as client:
            client.settimeout(3)
            client.connect(backend.server.server_address)
            client.sendall(b'\2aurora-direct\n')
            self.assertEqual(client.recv(1),b'\0')
            for kind,data in ((b'\2',b'JCapture only\n'),(b'\3',self.document)):
                client.sendall(kind+str(len(data)).encode()+b' file\n')
                self.assertEqual(client.recv(1),b'\0')
                client.sendall(data+b'\0')
                self.assertEqual(client.recv(1),b'\0')
            client.shutdown(socket.SHUT_WR)
            self.assertEqual(client.recv(1),b'')

    def test_live_print_automatically_delivers_exact_job_and_settings(self):
        backend=None
        with ControllerSimulator(lambda:self.expected(backend),warning=True,echo=False) as sim:
            backend=self.start(sim.endpoint)
            backend.enable_live()
            self.print_job(backend)
            rows=self.until(lambda:[r for r in backend.snapshot()['rows'] if r['state']=='completed_with_warning'])
            self.assertEqual(rows[0]['settings'],decode(default_selection()))
            self.assertTrue(sim.upload_received.is_set())
            self.assertEqual(len(backend.service.store.list()),1)
            job_id=rows[0]['job_id']
            self.assertEqual(sum(e['kind']=='uploaded' for e in backend.service.store.history(job_id)),1)
            backend.capture_only()
            backend.close()
            self.assertTrue(backend.wait_closed(5))

    def test_pause_finishes_current_and_holds_later_prints(self):
        hold=threading.Event()
        backend=None
        with ControllerSimulator(lambda:self.expected(backend),hold=hold) as sim:
            backend=self.start(sim.endpoint)
            backend.enable_live()
            self.print_job(backend)
            self.assertTrue(sim.upload_received.wait(8))
            self.print_job(backend)
            self.until(lambda:len(backend.snapshot()['rows'])==2)
            waiting=next(r for r in backend.snapshot()['rows'] if r['state']=='waiting')
            backend.cancel_pending(waiting['id'])
            self.assertEqual(next(r for r in backend.snapshot()['rows'] if r['id']==waiting['id'])['state'],'canceled')
            self.print_job(backend)
            backend.capture_only()
            self.assertEqual(backend.snapshot()['mode'],'finishing_current')
            self.print_job(backend)
            self.until(lambda:len(backend.snapshot()['rows'])==4)
            self.assertEqual(len(backend.service.store.list()),1)
            hold.set()
            self.until(lambda:backend.snapshot()['mode']=='capture_only')
            states=[r['state'] for r in backend.snapshot()['rows']]
            self.assertCountEqual(states,['completed','canceled','held','captured_locally'])
            backend.close()
            self.assertTrue(backend.wait_closed(5))

    def test_close_waits_for_active_delivery(self):
        hold=threading.Event()
        backend=None
        with ControllerSimulator(lambda:self.expected(backend),hold=hold) as sim:
            backend=self.start(sim.endpoint)
            backend.enable_live()
            self.print_job(backend)
            self.assertTrue(sim.upload_received.wait(8))
            backend.close()
            self.assertFalse(backend.wait_closed(.1))
            hold.set()
            self.assertTrue(backend.wait_closed(5))
            self.assertEqual(backend.snapshot()['rows'][0]['state'],'completed')

    def test_close_finishes_accepted_receive_without_dispatch(self):
        backend=self.start()
        with socket.create_connection(backend.server.server_address,timeout=3) as client:
            client.sendall(b'\2aurora-direct\n')
            self.assertEqual(client.recv(1),b'\0')
            backend.close()
            self.assertFalse(backend.wait_closed(.15))
            for kind,data in ((b'\2',b'JClosing\n'),(b'\3',self.document)):
                client.sendall(kind+str(len(data)).encode()+b' file\n')
                self.assertEqual(client.recv(1),b'\0')
                client.sendall(data+b'\0')
                self.assertEqual(client.recv(1),b'\0')
            client.shutdown(socket.SHUT_WR)
            self.assertEqual(client.recv(1),b'')
        self.assertTrue(backend.wait_closed(5))
        self.assertEqual(backend.snapshot()['rows'][0]['state'],'captured_locally')

    def test_capture_started_before_enable_remains_local_after_enable(self):
        backend=self.start()
        with socket.create_connection(backend.server.server_address,timeout=3) as client:
            client.sendall(b'\2aurora-direct\n')
            self.assertEqual(client.recv(1),b'\0')
            with patch('aurora_jobserver.desktop_server.socket.create_connection') as network:
                backend.enable_live()
                for kind,data in ((b'\2',b'JBefore enable\n'),(b'\3',self.document)):
                    client.sendall(kind+str(len(data)).encode()+b' file\n')
                    self.assertEqual(client.recv(1),b'\0')
                    client.sendall(data+b'\0')
                    self.assertEqual(client.recv(1),b'\0')
                client.shutdown(socket.SHUT_WR)
                self.assertEqual(client.recv(1),b'')
                self.until(lambda:backend.snapshot()['rows'])
                time.sleep(.3)
                self.assertEqual(backend.snapshot()['rows'][0]['state'],'captured_locally')
                self.assertEqual(backend.service.store.list(),[])
                network.assert_not_called()

    def test_conversion_failure_stops_automatic_printing_and_retains_document(self):
        backend=self.start()
        backend.enable_live()
        self.print_job(backend,b'Invalid document')
        self.until(lambda:backend.snapshot()['error'])
        self.assertEqual(backend.snapshot()['mode'],'capture_only')
        self.assertTrue(next(backend.service.captures.glob('*/source.bin')).is_file())
        self.until(lambda:backend.snapshot()['rows'])
        self.assertEqual(backend.snapshot()['rows'][0]['state'],'needs_attention')

    def test_duplicate_host_and_port_collision_leave_original_receiver_working(self):
        backend=self.start()
        duplicate=DesktopJobServer(backend.root,INTAKE,port=0)
        with self.assertRaises(RuntimeError):
            duplicate.start()
        collision=DesktopJobServer(self.root/'other',INTAKE,port=backend.server.server_address[1])
        with self.assertRaises(OSError):
            collision.start()
        self.print_job(backend)
        self.until(lambda:backend.snapshot()['rows'])
        collision.port=0
        collision.start()
        self.backends.append(collision)

    def test_status_check_opens_only_status_channel(self):
        with ControllerSimulator(b'') as sim:
            backend=self.start(sim.endpoint)
            backend.check_connection()
            self.until(lambda:not backend.snapshot()['probing'])
            self.assertEqual(backend.snapshot()['connection'],'Laser responded')
            self.assertEqual(sim.status_tx,b'\xff\xe0\x01')
            self.assertEqual(sim.main_tx,b'')
            self.assertFalse(sim.reset_seen.is_set())

    def test_crash_history_recovers_uncertainty_and_requires_observed_resolution(self):
        backend=self.start()
        backend.enable_live()
        backend.capture_only()
        folder=capture_document(backend.service.captures,self.document)
        print_id=folder.name
        # Construct the persisted state left by a killed sender after upload starts.
        source=self.root/'encoded.jbs'
        source.write_bytes(self.expected(backend))
        store=backend.service.store
        job_id=backend.service.bridge.accept(source,print_id,decode(default_selection()))
        self.assertEqual(process_one(store)['state'],'ready')
        attempt=store.begin_delivery(job_id,asdict(backend.endpoint))
        store.delivery_stage(attempt,'uploading',{})
        with DeviceGuard(backend.endpoint.host,self.root/'locks') as guard:
            guard.mark(store,job_id,attempt)
        backend.close()
        self.assertTrue(backend.wait_closed(5))
        restarted=self.start()
        rows=self.until(lambda:restarted.snapshot()['rows'])
        self.assertEqual(rows[0]['state'],'delivery_unknown')
        with self.assertRaisesRegex(RuntimeError,'unresolved'):
            restarted.enable_live()
        restarted.resolve(print_id,'completed','Observed a complete engraving')
        self.assertEqual(restarted.snapshot()['rows'][0]['state'],'completed_with_warning')
        restarted.enable_live()
        self.assertEqual(restarted.service.store.list(),[])


    def test_no_cut_print_stays_live_and_history_survives_restart_without_replay(self):
        from test_vector_only_print import vector_document
        self.document=vector_document(thick=True)
        backend=self.start()
        with patch('aurora_jobserver.desktop_server.socket.create_connection') as network:
            backend.enable_live()
            self.print_job_unpatched(backend)
            rows=self.until(lambda:[r for r in backend.snapshot()['rows'] if r['state']=='nothing_to_cut'])
            self.until(lambda:not backend.snapshot()['busy'])
            self.assertIn('Nothing was sent',rows[0]['notice'])
            self.assertEqual(backend.snapshot()['mode'],'live')
            self.assertEqual(backend.snapshot()['error'],'')
            self.assertEqual(backend.service.store.list(),[])
            backend.capture_only();backend.close()
            self.assertTrue(backend.wait_closed(5))
            restarted=self.start()
            self.until(lambda:[r for r in restarted.snapshot()['rows'] if r['state']=='nothing_to_cut'])
            restarted.enable_live()
            time.sleep(.3)
            self.assertEqual(restarted.service.store.list(),[])
            network.assert_not_called()


class StartupCommandTests(unittest.TestCase):
    def test_command_quotes_paths_and_uses_windowed_runtime(self):
        from aurora_jobserver.startup import command
        result=command(Path('runtime/state with spaces'))
        self.assertIn('pythonw.exe',result)
        self.assertIn('"'+str(Path('run-desktop-jobserver.pyw').resolve())+'"',result)
        self.assertIn('--state "'+str(Path('runtime/state with spaces').resolve())+'"',result)

    def test_reading_startup_does_not_write_and_enabling_stores_exact_command(self):
        from aurora_jobserver import startup
        registry=MagicMock()
        registry.QueryValueEx.side_effect=FileNotFoundError
        with patch.dict('sys.modules',{'winreg':registry}):
            self.assertFalse(startup.enabled('runtime/desktop'))
            registry.CreateKeyEx.assert_not_called()
            registry.SetValueEx.assert_not_called()
            startup.set_enabled('runtime/desktop',True)
            self.assertEqual(registry.SetValueEx.call_args.args[-1],startup.command('runtime/desktop'))

    def test_startup_collision_is_preserved_and_only_own_entry_can_be_removed(self):
        from aurora_jobserver import startup
        registry=MagicMock()
        registry.QueryValueEx.return_value=('another application',1)
        with patch.dict('sys.modules',{'winreg':registry}):
            for enable in (True,False):
                with self.assertRaisesRegex(ValueError,'left unchanged'):
                    startup.set_enabled('runtime/desktop',enable)
            registry.SetValueEx.assert_not_called()
            registry.DeleteValue.assert_not_called()
            registry.QueryValueEx.return_value=(startup.command('runtime/desktop'),1)
            startup.set_enabled('runtime/desktop',False)
            self.assertEqual(registry.DeleteValue.call_args.args[-1],startup.VALUE)


if __name__=='__main__':
    unittest.main()
