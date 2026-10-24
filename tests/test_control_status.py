"""Observed control-channel fixture and stream boundary behavior."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aurora_jobserver.protocol import StatusReplyStream, decode_status_reply


class StatusTests(unittest.TestCase):
    def test_actual_passive_capture_reply(self):
        result = decode_status_reply(bytes.fromhex("ff e1 01 00 00 02 02 00"))
        self.assertEqual(result.flags_4_5, 0x200)
        self.assertEqual(result.legacy_state_code, 1)

    def test_stream_fragmentation_and_coalescing(self):
        fixture = bytes.fromhex("ff e1 01 00 00 02 02 00")
        stream = StatusReplyStream()
        self.assertEqual(stream.feed(fixture[:1]), [])
        self.assertEqual(stream.feed(fixture[1:5]), [])
        self.assertEqual(len(stream.feed(fixture[5:] + fixture)), 2)
        self.assertEqual(stream.buffer, b"")

    def test_unknown_frame_not_reported_as_known_status(self):
        with self.assertRaises(ValueError):
            StatusReplyStream().feed(b"\xff\xe1\x08")
        with self.assertRaises(ValueError):
            decode_status_reply(b"\xff\xe1\x01")


if __name__ == "__main__":
    unittest.main()
