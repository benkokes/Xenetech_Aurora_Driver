import json
from pathlib import Path
import unittest

from aurora_jobserver.replies import ChannelMessageStream, MainReplyStream
from aurora_jobserver.delivery import DeliveryTracker
from aurora_jobserver.wire import TERMINATE
from aurora_jobserver.wire import raster_plan
from tools.analyze_job_session import find_jobs
from tools.reassemble_tcp import reassemble


def segment(seq, data=b'', flags=0x10, ack=0):
    return {'seq': seq, 'ack': ack, 'flags': flags, 'payload_hex': data.hex()}


class TcpReassemblyTests(unittest.TestCase):
    def test_out_of_order_retransmissions_and_wrap(self):
        packets = [segment(0xfffffffd, flags=2), segment(1, b'def'),
                   segment(0xfffffffe, b'abc'), segment(0xffffffff, b'bcde'),
                   segment(4, flags=0x11)]
        stream = reassemble(packets)
        self.assertEqual(stream.data, b'abcdef')
        self.assertEqual(stream.duplicate_bytes, 4)
        self.assertTrue(stream.has_syn and stream.has_fin)
        self.assertFalse(stream.acknowledged_by([segment(10, ack=3)]))
        self.assertTrue(stream.acknowledged_by([segment(10, ack=4)]))

    def test_gap_conflict_missing_head_tail_and_flow_reuse(self):
        bad = [
            [segment(100, b'ab'), segment(103, b'd')],
            [segment(100, b'abc'), segment(101, b'Xd')],
            [segment(99, flags=2), segment(101, b'b')],
            [segment(100, b'ab'), segment(103, flags=0x11)],
            [segment(99, flags=2), segment(199, flags=2)],
        ]
        for packets in bad:
            with self.subTest(packets=packets), self.assertRaises(ValueError):
                reassemble(packets)

    def test_capture_without_syn_and_bound(self):
        stream = reassemble([segment(103, b'def'), segment(100, b'abc')])
        self.assertEqual(stream.data, b'abcdef')
        self.assertFalse(stream.has_syn)
        with self.assertRaises(ValueError):
            reassemble([segment(0, flags=2), segment(1, b'abc')], max_bytes=2)


class MainReplyTests(unittest.TestCase):
    def test_fragmentation_does_not_change_events(self):
        data = (b'0 dsp_feature 1 wchar #0000005459\n\x01\n> '
                b'1 wchar pre_job_table \x01\x04\n'
                b"\x07Error 2: Token 'set_xyup_feed' not found.\n"
                b'\x06A0\x06\xad\x05\x06E0\x06\xac\xadP\n\r'
                b'JOB_TIME 202.0140\n\r\x04\xac')
        whole = MainReplyStream()
        expected = whole.feed(data) + whole.finish()
        fragmented = MainReplyStream()
        actual = []
        for byte in data:
            actual.extend(fragmented.feed(bytes([byte])))
        actual.extend(fragmented.finish())
        self.assertEqual(actual, expected)
        self.assertEqual([e.value for e in actual if e.kind == 'feature_value'], [5459])
        self.assertEqual([e.value for e in actual if e.kind == 'job_time'], [202.014])
        self.assertEqual([e.value['code'] for e in actual if e.kind == 'controller_error'], [2])
        self.assertEqual(sum(e.value == 4 for e in actual if e.kind == 'control'), 2)
        self.assertEqual([e.value for e in actual if e.kind == 'channel_select'], [5, 80])
        self.assertEqual([e.channel for e in actual if e.kind == 'job_time'], [80])

    def test_reply_limit_and_unterminated_text(self):
        parser = MainReplyStream(max_line=4)
        with self.assertRaises(ValueError):
            parser.feed(b'12345')
        parser = MainReplyStream()
        self.assertEqual(parser.feed(b'hello'), [])
        self.assertEqual(parser.finish()[0].raw, b'hello')
        parser.feed(b'\xad')
        with self.assertRaises(ValueError):
            parser.finish()

    def test_complete_job_extraction_and_partial_rejection(self):
        data = b'!ZX\rJOB test\rPU\rEND_PLOT\r'
        jobs = find_jobs(b'\nM99\n!ZX\n' + data + b'ifexists host_terminate host_terminate\n')
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0][2].data, data)
        with self.assertRaises(ValueError):
            find_jobs(data[:-2])

    def test_actual_startup_job_capture(self):
        root = Path(__file__).resolve().parents[1] / 'captures/network/startup-job-20261017-01-decoded'
        if not root.is_dir():
            self.skipTest('Private capture is unavailable')
        client = json.loads((root / 'flow-04.json').read_text())['segments']
        server = json.loads((root / 'flow-08.json').read_text())['segments']
        tx, rx = reassemble(client), reassemble(server)
        self.assertEqual(len(tx.data), 19340)
        self.assertEqual(len(rx.data), 681)
        self.assertTrue(tx.has_syn and rx.has_syn)
        self.assertTrue(tx.acknowledged_by(server) and rx.acknowledged_by(client))
        self.assertEqual(tx.duplicate_bytes, 0)
        jobs = find_jobs(tx.data)
        self.assertEqual(len(jobs), 1)
        job = jobs[0][2]
        self.assertEqual((len(job.data), job.input_format, job.rasters), (18994, 'compressed', 1))
        self.assertTrue(job.auto_start)
        plan = raster_plan(job.data, r'c:\xfiles\jbs\Convert\Default.jbs')
        self.assertEqual(b''.join(step.request for step in plan), tx.data)
        self.assertEqual(plan[-2].gate, 'channel_5_06_E0_06_then_ac')
        self.assertEqual(plan[-3].gate, 'empty_01_04_table')
        parser = MainReplyStream()
        events = parser.feed(rx.data) + parser.finish()
        self.assertEqual([e.value for e in events if e.kind == 'feature_value'], [5459, 330476101])
        self.assertEqual([e.value for e in events if e.kind == 'job_time'], [202.014])
        self.assertEqual([e.value for e in events if e.kind == 'channel_select'], [5, 80])
        errors = [e.value for e in events if e.kind == 'controller_error']
        # This firmware does not terminate the error before its first scale report.
        self.assertEqual(errors, [{'code': 2, 'message':
                         "Token 'set_xyup_feed' not found. laser scale=0.0002  "
                         'used iters=22  Speed= 31000.0000, Power= 0.9990'}])
        tracker = DeliveryTracker()
        tracker.begin_upload()
        # Pre-job EOT does not complete the physical job or trigger termination.
        self.assertEqual(tracker.feed(rx.data[:159]), [])
        self.assertEqual(tracker.state, 'awaiting_end')
        self.assertEqual(tracker.feed(rx.data[159:656]), [TERMINATE])
        self.assertEqual(tracker.state, 'awaiting_job_report')
        self.assertIsNone(tracker.job_time)
        self.assertEqual(tracker.feed(rx.data[656:]), [])
        self.assertEqual(tracker.state, 'completed_with_warning')
        self.assertEqual(tracker.job_time, 202.014)

    def test_wire_profile_rejects_unknown_jobtype_and_command_injection(self):
        import struct
        from aurora_jobserver.jbs import prepare
        raw = (b'!ZX\rJOB pixel\rPICT-UL\r'
               + struct.pack('<HIIIIH', 0x58c3, 1, 1, 167, 167, 0x41)
               + b'\x80\x00\xffEND_PLOT\r')
        job = prepare(raw).data
        for path in ['Default.jbs', 'c:\\jobs\\bad\rM99.jbs', 'c:\\jobs\\has spaces.jbs']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                raster_plan(job, path)
        with self.assertRaises(ValueError):
            raster_plan(b'!ZX\rJOB vector\rPU\rEND_PLOT\r', r'c:\jobs\vector.jbs')


class DeliveryTrackingTests(unittest.TestCase):
    END = b'\xad\x05\x06E0\x06\xac'
    REPORT = b'\xadP\n\rJOB_TIME 202.0140\n\r\x04\xac'

    def test_actual_live_controller_no_echo_replies(self):
        self.check_live_fixture('aurora-live-no-echo.json')

    def test_generated_square_calibration_controller_replies(self):
        self.check_live_fixture('aurora-square-calibration.json')

    def check_live_fixture(self, name):
        import hashlib
        path = Path(__file__).parent / 'fixtures' / name
        fixture = json.loads(path.read_text())
        data = bytes.fromhex(fixture['main_rx_hex'])
        self.assertEqual(hashlib.sha256(data).hexdigest(), fixture['main_rx_sha256'])
        tracker = DeliveryTracker()
        tracker.begin_upload()
        actions = []
        parser = MainReplyStream()
        events = []
        for byte in data:
            chunk = bytes([byte])
            actions.extend(tracker.feed(chunk))
            events.extend(parser.feed(chunk))
        events.extend(parser.finish())
        self.assertEqual(actions, [TERMINATE])
        self.assertEqual(tracker.state, fixture['expected_state'])
        self.assertEqual(tracker.job_time, fixture['expected_job_time'])
        self.assertEqual([e.value for e in events if e.kind == 'feature_value'], fixture['expected_features'])
        self.assertEqual([e['code'] for e in tracker.errors], [2])

    def test_fragmented_completion_and_duplicate_end(self):
        tracker = DeliveryTracker()
        tracker.begin_upload()
        actions = []
        for byte in self.END + self.END + self.REPORT:
            actions.extend(tracker.feed(bytes([byte])))
        self.assertEqual(actions, [TERMINATE])
        self.assertEqual(tracker.state, 'completed')
        self.assertEqual(tracker.end_code, '0')
        self.assertEqual(tracker.job_time, 202.014)

    def test_idle_prejob_and_other_channel_do_not_trigger_termination(self):
        tracker = DeliveryTracker()
        self.assertEqual(tracker.feed(self.END), [])
        self.assertEqual(tracker.state, 'idle')
        tracker.begin_upload()
        self.assertEqual(tracker.feed(b'\x01\x04\xad\x06\x06E0\x06\xac' + self.REPORT), [])
        self.assertEqual(tracker.state, 'awaiting_end')

    def test_disconnect_and_unrecognized_end_are_uncertain(self):
        tracker = DeliveryTracker()
        tracker.begin_upload()
        tracker.disconnected()
        self.assertEqual(tracker.state, 'delivery_unknown')
        with self.assertRaises(ValueError):
            tracker.begin_upload()
        tracker = DeliveryTracker()
        tracker.begin_upload()
        self.assertEqual(tracker.feed(self.END.replace(b'E0', b'ER')), [])
        self.assertEqual(tracker.state, 'delivery_unknown')
        # A real stopped-job capture returned E1. Do not assume success or
        # infer that it was an empty vector job; operator resolution is needed.
        tracker = DeliveryTracker()
        tracker.begin_upload()
        self.assertEqual(tracker.feed(self.END.replace(b'E0', b'E1')), [])
        self.assertEqual(tracker.state, 'delivery_unknown')
        self.assertEqual(tracker.end_code, '1')
        tracker = DeliveryTracker()
        tracker.begin_upload()
        tracker.feed(self.END)
        tracker.disconnected()
        self.assertEqual(tracker.state, 'delivery_unknown')

    def test_channel_framing_bounds_and_interruption(self):
        parser = ChannelMessageStream()
        self.assertEqual(parser.feed(b'\xad'), [])
        self.assertEqual(parser.feed(b'\x05\x06E0\x06'), [])
        message, = parser.feed(b'\xac')
        self.assertEqual((message.channel, message.payload), (5, b'\x06E0\x06'))
        parser.finish()
        with self.assertRaises(ValueError):
            ChannelMessageStream(max_message=2).feed(b'\xad\x05123')
        parser = ChannelMessageStream()
        parser.feed(b'\xad\x05')
        with self.assertRaises(ValueError):
            parser.finish()
        with self.assertRaises(ValueError):
            parser.feed(b'\xadP')


if __name__ == '__main__':
    unittest.main()
