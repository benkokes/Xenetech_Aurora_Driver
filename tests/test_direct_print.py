"""Automatic dispatch runs only against a loopback controller in these tests."""
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import uuid

from aurora_jobserver.direct_print import DirectPrintBridge, PrintBridgeBlocked
from aurora_jobserver.jbs import DRAFT_MARKER, prepare
from aurora_jobserver.store import JobStore
from aurora_jobserver.transport import Endpoint, Timing
from aurora_jobserver.wire import raster_plan
from tools.controller_simulator import ControllerSimulator


RAW = (b'!ZX\rJOB direct\rnormalstart START\rPICT-UL\r'
       + struct.pack('<HIIIIH', 0x58c3, 2, 1, 167, 167, 0x41)
       + b'\x80\xff\x00\xffEND_PLOT\r')
FAST = Timing(connect=1, handshake=1, job=2, sync_delay=.005,
              feature_delay=.005, sync_quiet=.005)


class DirectPrintTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = JobStore(self.root / 'print-queue')
        self.source = self.root / 'printed.jbs'
        self.source.write_bytes(RAW)
        self.data = prepare(RAW).data

    def bridge(self, endpoint, **kwargs):
        return DirectPrintBridge(self.store, endpoint, timing=kwargs.pop('timing', FAST),
                                 locks=self.root / 'locks', **kwargs)

    def accept(self, bridge, print_id=None, settings=None):
        return bridge.accept(self.source, print_id or str(uuid.uuid4()),
                             settings if settings is not None else {'raster_power_percent': 45})

    def test_print_is_sent_without_a_second_send_action_and_not_resent_on_restart(self):
        with ControllerSimulator(self.data, echo=False, fragment=True, warning=True) as sim:
            bridge = self.bridge(sim.endpoint)
            receipt = str(uuid.uuid4())
            settings = {'raster_power_percent': 45, 'nested': {'material': 'test'}}
            job = self.accept(bridge, receipt, settings)
            settings['nested']['material'] = 'changed'
            result = bridge.step()
            self.assertEqual(result['id'], job)
            self.assertEqual(result['state'], 'completed_with_warning')
            self.assertEqual(bytes(sim.upload), raster_plan(self.data, bridge.controller_path)[6].request)
            self.assertFalse(result['auto_start'])
            self.assertFalse(sim.reset_seen.is_set())
            self.assertEqual(result['settings']['printer_settings']['nested']['material'], 'test')
            restarted = self.bridge(sim.endpoint)
            self.assertEqual(self.accept(restarted, receipt,
                {'raster_power_percent': 45, 'nested': {'material': 'test'}}), job)
            self.assertIsNone(restarted.step())
            self.assertEqual(sum(e['kind'] == 'uploaded' for e in self.store.history(job)), 1)

    def test_same_receipt_cannot_change_bytes_or_printer_settings(self):
        bridge = self.bridge(Endpoint('127.0.0.1'))
        receipt = str(uuid.uuid4())
        self.accept(bridge, receipt)
        with self.assertRaisesRegex(ValueError, 'different bytes or settings'):
            self.accept(bridge, receipt, {'raster_power_percent': 30})
        self.source.write_bytes(RAW.replace(b'JOB direct', b'JOB changed'))
        with self.assertRaisesRegex(ValueError, 'different bytes or settings'):
            self.accept(bridge, receipt)
        self.assertEqual(len(self.store.list()), 1)

    def test_two_deliberate_prints_are_distinct_and_keep_print_order(self):
        with ControllerSimulator(self.data) as first:
            bridge = self.bridge(first.endpoint)
            job1 = self.accept(bridge)
            job2 = self.accept(bridge)
            self.assertNotEqual(job1, job2)
            self.assertEqual(bridge.step()['id'], job1)
            self.assertEqual(self.store.get(job2)['state'], 'queued')

    def test_failure_stops_following_prints_and_never_retries(self):
        for failure in ('preflight', 'uncertain'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp:
                self.store = JobStore(Path(temp) / 'queue')
                options = {'feature': 1234} if failure == 'preflight' else {'disconnect': 'after_upload'}
                with ControllerSimulator(self.data, **options) as sim:
                    bridge = self.bridge(sim.endpoint)
                    bad = self.accept(bridge)
                    following = self.accept(bridge)
                    with self.assertRaises(PrintBridgeBlocked):
                        bridge.step()
                    expected = 'delivery_failed' if failure == 'preflight' else 'delivery_unknown'
                    self.assertEqual(self.store.get(bad)['state'], expected)
                    with patch('aurora_jobserver.direct_print.send_job') as send:
                        with self.assertRaises(PrintBridgeBlocked):
                            bridge.step()
                        send.assert_not_called()
                    self.assertEqual(self.store.get(following)['state'], 'queued')
                    self.assertEqual(sum(e['kind'] == 'connecting' for e in self.store.history(bad)), 1)

    def test_old_manual_jobs_and_target_changes_do_not_send(self):
        bridge = self.bridge(Endpoint('127.0.0.1'))
        self.store.submit(self.source)
        with patch('aurora_jobserver.direct_print.send_job') as send:
            with self.assertRaises(PrintBridgeBlocked):
                bridge.step()
            send.assert_not_called()
        self.store = JobStore(self.root / 'other')
        original = self.bridge(Endpoint('127.0.0.1'))
        self.accept(original)
        changed = self.bridge(Endpoint('127.0.0.2'))
        with patch('aurora_jobserver.direct_print.send_job') as send:
            with self.assertRaises(PrintBridgeBlocked):
                changed.step()
            send.assert_not_called()

    def test_drafts_and_vector_only_documents_are_not_accepted(self):
        bridge = self.bridge(Endpoint('127.0.0.1'))
        for data in (DRAFT_MARKER + RAW, b'!ZX\rJOB vector\rPU\rEND_PLOT\r'):
            self.source.write_bytes(data)
            with self.assertRaises(ValueError):
                self.accept(bridge)
        self.assertEqual(self.store.list(), [])

    def test_interrupted_preparation_can_resume_but_interrupted_send_cannot(self):
        with ControllerSimulator(self.data) as sim:
            bridge = self.bridge(sim.endpoint)
            job = self.accept(bridge)
            self.store.claim()
            self.assertEqual(bridge.step()['state'], 'completed')
            self.assertEqual(self.store.get(job)['attempts'], 2)
        # Use another dedicated queue to avoid changing the earlier endpoint.
        self.store = JobStore(self.root / 'interrupted')
        bridge = self.bridge(Endpoint('127.0.0.1'))
        job = self.accept(bridge)
        from aurora_jobserver.worker import process_one
        process_one(self.store)
        self.store.begin_delivery(job, {'host': '127.0.0.1'})
        with patch('aurora_jobserver.direct_print.send_job') as send:
            with self.assertRaises(PrintBridgeBlocked):
                bridge.step()
            send.assert_not_called()

    def test_frontend_file_change_after_validation_cannot_change_accepted_bytes(self):
        bridge = self.bridge(Endpoint('127.0.0.1'))
        submit = self.store.submit
        def replace_original_then_submit(*args, **kwargs):
            self.source.write_bytes(b'changed while accepting')
            return submit(*args, **kwargs)
        with patch.object(self.store, 'submit', side_effect=replace_original_then_submit):
            job = self.accept(bridge)
        self.assertEqual((self.store.directory(job) / 'source.jbs').read_bytes(), RAW)


if __name__ == '__main__':
    unittest.main()
