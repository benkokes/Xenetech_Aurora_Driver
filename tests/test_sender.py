from dataclasses import replace
import json
from pathlib import Path
import random
import socket
import sqlite3
import struct
import tempfile
import threading
import unittest
from unittest.mock import patch

from tools.controller_simulator import ControllerSimulator
from aurora_jobserver.jbs import prepare
from aurora_jobserver.sender import DeviceGuard, send_job, recover_controller, resolve_job
from aurora_jobserver.store import JobStore
from aurora_jobserver.transport import Endpoint, Timing
from aurora_jobserver.worker import process_one
from aurora_jobserver.wire import raster_plan


PATH = r'c:\xfiles\jbs\Convert\Default.jbs'
FAST = Timing(connect=1, handshake=1, job=2, sync_delay=.005, feature_delay=.005, sync_quiet=.005)
RAW = (b'!ZX\rJOB pixel\rautostart START\rPICT-UL\r'
       + struct.pack('<HIIIIH', 0x58c3, 2, 1, 167, 167, 0x41)
       + b'\x80\xff\x00\xffEND_PLOT\r')


class SenderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = JobStore(self.root / 'queue')
        self.locks = self.root / 'locks'
        self.job, self.data = self.add_job()

    def add_job(self, data=RAW, store=None):
        store = store or self.store
        source = self.root / 'source.jbs'
        source.write_bytes(data)
        job = store.submit(source)
        while store.get(job)['state'] == 'queued':
            process_one(store)
        return job, store.prepared_bytes(job)

    def send(self, simulator, job=None, store=None, timing=FAST, reset=False):
        return send_job(store or self.store, job or self.job, simulator.endpoint, PATH,
                        timing=timing, locks=self.locks, reset_connection=reset)

    def test_full_socket_exchange_persists_completion_and_transcripts(self):
        with ControllerSimulator(self.data, fragment=True, warning=True) as sim:
            result = self.send(sim)
            self.assertEqual(result['state'], 'completed_with_warning')
            self.assertEqual(result['delivery']['result']['job_time'], 202.014)
            self.assertEqual(result['delivery']['result']['warnings'][0]['code'], 2)
            directory = self.store.directory(self.job) / 'deliveries' / result['delivery']['id']
            self.assertEqual((directory / 'main-tx.bin').read_bytes(), b''.join(s.request for s in raster_plan(self.data, PATH)))
            self.assertEqual((directory / 'status-tx.bin').read_bytes(), b'\xff\xe0\x01' * 2)
            self.assertEqual([e['kind'] for e in self.store.history(self.job)][-4:],
                             ['uploading','uploaded','awaiting_report','completed_with_warning'])
            self.assertEqual(JobStore(self.store.root).get(self.job)['state'], 'completed_with_warning')
        self.assertFalse(list(self.locks.glob('*.pending.json')))
        for action in (self.store.cancel, self.store.retry):
            with self.assertRaises(ValueError):
                action(self.job)

    def test_full_original_captured_job(self):
        capture = Path(__file__).resolve().parents[1] / 'captures/network/startup-job-20261017-01-session-v2'
        if not capture.is_dir():
            self.skipTest('Private capture is unavailable')
        data = (capture / 'session-01-job-01.jbs').read_bytes()
        job, prepared = self.add_job(data)
        with ControllerSimulator(prepared) as sim:
            result = self.send(sim, job)
            self.assertEqual(result['state'], 'completed')
            self.assertEqual(bytes(sim.main_tx), (capture / 'session-01-client.bin').read_bytes())

    def test_preflight_rejections_never_start_upload(self):
        cases = [{'custom_table': b'move_something\n'}, {'feature': 1234},
                 {'status': b'\xff\xe1\x01\x00\x00\x12\x02\x00'}]
        for case in cases:
            job, _ = self.add_job()
            with self.subTest(case=case), ControllerSimulator(self.data, **case) as sim:
                result = self.send(sim, job)
                self.assertEqual(result['state'], 'delivery_failed')
                self.assertFalse(result['delivery']['upload_started'])
                self.assertEqual(sim.upload, b'')
            self.store.retry(job)
            self.assertEqual(self.store.get(job)['state'], 'queued')
        self.assertFalse(list(self.locks.glob('*.pending.json')))

    def test_startup_status_transitions_only_after_main_sync(self):
        with ControllerSimulator(self.data, startup_status=b'\xff\xe1\x01\x00\x00\x12\x02\x00') as sim:
            result = self.send(sim)
            self.assertEqual(result['state'], 'completed')
            initial = next(e for e in self.store.history(self.job) if e['kind'] == 'status_initial')
            self.assertEqual(json.loads(initial['detail'])['flags_4_5'], 0x1200)
            self.assertEqual(result['delivery']['result']['status']['flags_4_5'], 0x0200)

    def test_no_echo_controller_uses_timed_sync_and_bare_features(self):
        with ControllerSimulator(self.data, echo=False, fragment=True) as sim:
            result = self.send(sim)
            self.assertEqual(result['state'], 'completed')
            self.assertEqual(result['delivery']['result']['features'], [5459, 330476101])

    def test_explicit_legacy_recovery_is_recorded_before_upload(self):
        with ControllerSimulator(self.data, echo=False, require_reset=True) as sim:
            result = self.send(sim, reset=True)
            self.assertEqual(result['state'], 'completed')
            self.assertTrue(sim.reset_seen.is_set())
            events = [e['kind'] for e in self.store.history(self.job)]
            self.assertLess(events.index('connection_reset'), events.index('uploading'))

    def test_refused_legacy_recovery_still_requires_verified_handshake(self):
        with ControllerSimulator(self.data, echo=False) as sim:
            connect = socket.create_connection
            def refuse_recovery(address, *args, **kwargs):
                if address[1] == sim.endpoint.recovery_port:
                    raise ConnectionRefusedError(10061, 'Simulated legacy recovery refusal')
                return connect(address, *args, **kwargs)
            with patch('aurora_jobserver.transport.socket.create_connection', side_effect=refuse_recovery):
                result = self.send(sim, reset=True)
            self.assertEqual(result['state'], 'completed')
            event = next(e for e in self.store.history(self.job) if e['kind'] == 'connection_reset')
            self.assertEqual(json.loads(event['detail'])['result'], 'refused')

    def test_disconnects_and_timeout_are_unknown_and_block_another_queue(self):
        for failure in ('mid_upload','after_upload','after_end','stall'):
            job, _ = self.add_job()
            with self.subTest(failure=failure), ControllerSimulator(self.data, disconnect=failure) as sim:
                result = self.send(sim, job, timing=replace(FAST, job=.2))
                self.assertEqual(result['state'], 'delivery_unknown')
                self.assertTrue(result['delivery']['upload_started'])
                other = JobStore(self.root / ('other-' + failure))
                other_job, _ = self.add_job(store=other)
                with self.assertRaises(RuntimeError):
                    self.send(sim, other_job, other)
                self.assertEqual(other.get(other_job)['state'], 'ready')
                for action in (self.store.cancel, self.store.retry):
                    with self.assertRaises(ValueError):
                        action(job)
                resolved = resolve_job(self.store, job, 'completed', 'Operator verified completed engraving and idle machine',
                                       locks=self.locks)
                self.assertEqual(resolved['state'], 'completed_with_warning')
            self.assertFalse(list(self.locks.glob('*.pending.json')))

    def test_two_queues_cannot_send_to_same_controller_concurrently(self):
        release = threading.Event()
        results = []
        with ControllerSimulator(self.data, hold=release) as sim:
            def run():
                try:
                    results.append(self.send(sim))
                except BaseException as exc:
                    results.append(exc)
            thread = threading.Thread(target=run)
            thread.start()
            try:
                self.assertTrue(sim.upload_received.wait(2))
                other = JobStore(self.root / 'other')
                job, _ = self.add_job(store=other)
                with self.assertRaises(RuntimeError):
                    self.send(sim, job, other)
            finally:
                release.set()
                thread.join(3)
            self.assertFalse(thread.is_alive())
            self.assertEqual(results[0]['state'], 'completed')

    def test_recovery_and_explicit_not_started_resolution(self):
        endpoint = Endpoint('127.0.0.1')
        with DeviceGuard(endpoint.host, self.locks) as guard:
            attempt = self.store.begin_delivery(self.job, {'host': endpoint.host})
            self.store.delivery_stage(attempt, 'uploading', {})
            guard.mark(self.store, self.job, attempt)
        self.assertEqual(recover_controller(self.store, endpoint, locks=self.locks), 1)
        self.assertEqual(self.store.get(self.job)['state'], 'delivery_unknown')
        with self.assertRaises(ValueError):
            resolve_job(self.store, self.job, 'not_started', '', locks=self.locks)
        resolve_job(self.store, self.job, 'not_started', 'Operator confirmed no job reached the laser', locks=self.locks)
        self.store.retry(self.job)
        self.assertEqual(self.store.get(self.job)['state'], 'queued')

    def test_recovery_before_upload_is_retryable(self):
        self.store.begin_delivery(self.job, {'host': '127.0.0.1'})
        self.assertEqual(recover_controller(self.store, Endpoint('127.0.0.1'), locks=self.locks), 1)
        self.assertEqual(self.store.get(self.job)['state'], 'delivery_failed')
        self.assertFalse(self.store.get(self.job)['delivery']['upload_started'])

    def test_operator_stopped_resolution_is_local_and_preserves_failure_history(self):
        from aurora_jobserver.desktop_server import DesktopJobServer
        print_id='e3287eec-739d-4827-92f1-273623bfeb73'
        source=self.root/'stopped.jbs'
        source.write_bytes(RAW)
        job=self.store.submit(source,{'direct_print':{'print_id':print_id}})
        process_one(self.store)
        with DeviceGuard('127.0.0.1',self.locks) as guard:
            attempt=self.store.begin_delivery(job,{'host':'127.0.0.1'})
            self.store.delivery_stage(attempt,'uploading',{})
            guard.mark(self.store,job,attempt)
            self.store.finish_delivery(attempt,error='Unrecognized controller job outcome: 1')
        backend=DesktopJobServer(self.root/'desktop',Path(__file__),locks=self.locks)
        backend.history_stores['previous-session']=self.store
        backend.error='Print needs attention'
        backend.capture_errors[print_id]=backend.error
        with patch('aurora_jobserver.transport.socket.create_connection') as network:
            with self.assertRaises(ValueError):
                backend.resolve(print_id,'stopped','')
            self.assertTrue((self.locks/'127.0.0.1.pending.json').exists())
            result=backend.resolve(print_id,'stopped','Operator stopped the job; laser is idle')
            network.assert_not_called()
        self.assertEqual(result['state'],'delivery_failed')
        self.assertEqual(result['delivery']['result']['operator_outcome'],'stopped')
        self.assertEqual(result['delivery']['id'],attempt)
        self.assertEqual(backend.mode,'capture_only')
        self.assertIsNone(backend.service)
        self.assertEqual(backend.error,'')
        self.assertNotIn(print_id,backend.capture_errors)
        self.assertFalse((self.locks/'127.0.0.1.pending.json').exists())
        history=self.store.history(job)
        self.assertEqual(sum(e['kind']=='connecting' for e in history),1)
        self.assertTrue(any(e['kind']=='delivery_unknown' and 'outcome: 1' in e['detail'] for e in history))
        self.assertEqual(json.loads(history[-1]['detail'])['operator_outcome'],'stopped')

    def test_resolution_preserves_unrelated_desktop_error(self):
        from aurora_jobserver.desktop_server import DesktopJobServer
        source=self.root/'stopped.jbs'
        source.write_bytes(RAW)
        job=self.store.submit(source,{'direct_print':{'print_id':'stopped-print'}})
        process_one(self.store)
        with DeviceGuard('127.0.0.1',self.locks) as guard:
            attempt=self.store.begin_delivery(job,{'host':'127.0.0.1'})
            self.store.delivery_stage(attempt,'uploading',{})
            guard.mark(self.store,job,attempt)
            self.store.finish_delivery(attempt,error='Connection ended')
        backend=DesktopJobServer(self.root/'desktop',Path(__file__),locks=self.locks)
        backend.history_stores['previous-session']=self.store
        backend.capture_errors['stopped-print']='Old delivery error'
        backend.error='Another print has invalid artwork'
        backend.resolve('stopped-print','stopped','Operator stopped job; laser idle')
        self.assertEqual(backend.error,'Another print has invalid artwork')

    def test_integrity_and_unsupported_job_fail_before_connecting(self):
        (self.store.directory(self.job) / 'prepared.jbs').write_bytes(b'tampered')
        with self.assertRaises(ValueError):
            send_job(self.store, self.job, Endpoint('127.0.0.1'), PATH, locks=self.locks)
        self.assertIsNone(self.store.get(self.job)['delivery'])
        job, _ = self.add_job(b'!ZX\rJOB vector\rPU\rEND_PLOT\r')
        with self.assertRaises(ValueError):
            send_job(self.store, job, Endpoint('127.0.0.1'), PATH, locks=self.locks)
        self.assertIsNone(self.store.get(job)['delivery'])

    def test_large_upload_drains_replies_under_backpressure(self):
        width, height = 1024, 200
        pixels = random.Random(123).randbytes(width * height)
        raw = (b'!ZX\rJOB large\rPICT-UL\r' + struct.pack('<HIIIIH', 0x58c3, width, height, 167, 167, 0x41)
               + b''.join(pixels[n*width:(n+1)*width] + b'\x00\xff' for n in range(height)) + b'END_PLOT\r')
        job, data = self.add_job(raw)
        connect = socket.create_connection
        def small_buffers(*args, **kwargs):
            sock = connect(*args, **kwargs)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
            return sock
        with ControllerSimulator(data, echo_upload=True) as sim, patch(
                'aurora_jobserver.transport.socket.create_connection', side_effect=small_buffers):
            result = self.send(sim, job, timing=replace(FAST, job=10))
            self.assertEqual(result['state'], 'completed')
            self.assertGreater(len(sim.upload), 200000)

    def test_v1_schema_migration_retains_jobs_events_and_receipts(self):
        folder = self.root / 'legacy'
        folder.mkdir()
        with sqlite3.connect(folder / 'queue.sqlite3') as db:
            db.executescript('''
                CREATE TABLE jobs (
                  id TEXT PRIMARY KEY, created REAL NOT NULL, updated REAL NOT NULL,
                  state TEXT NOT NULL CHECK(state IN ('queued','preparing','ready','failed','canceled')),
                  source_name TEXT NOT NULL, source_hash TEXT NOT NULL, source_bytes INTEGER NOT NULL,
                  settings TEXT NOT NULL, output_hash TEXT, output_bytes INTEGER, rasters INTEGER,
                  input_format TEXT, auto_start INTEGER, title TEXT, error TEXT, attempts INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE events (seq INTEGER PRIMARY KEY AUTOINCREMENT,
                  job_id TEXT NOT NULL REFERENCES jobs(id), time REAL NOT NULL,kind TEXT NOT NULL,detail TEXT NOT NULL);
                CREATE TABLE receipts (token TEXT PRIMARY KEY,job_id TEXT NOT NULL REFERENCES jobs(id));
            ''')
            db.execute("INSERT INTO jobs(id,created,updated,state,source_name,source_hash,source_bytes,settings) VALUES(?,1,1,'queued','source','hash',1,'{}')", (self.job,))
            db.execute("INSERT INTO events(job_id,time,kind,detail) VALUES(?,1,'submitted','preserve this')", (self.job,))
            db.execute("INSERT INTO receipts VALUES('receipt',?)", (self.job,))
        db.close()
        migrated = JobStore(folder)
        self.assertEqual(migrated.get(self.job)['state'], 'queued')
        self.assertEqual(migrated.history(self.job)[0]['detail'], 'preserve this')
        self.assertTrue((folder / 'queue-v1-backup.sqlite3').is_file())
        with migrated.connect() as db:
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
            self.assertEqual(db.execute("SELECT job_id FROM receipts WHERE token='receipt'").fetchone()[0], self.job)


if __name__ == '__main__':
    unittest.main()
