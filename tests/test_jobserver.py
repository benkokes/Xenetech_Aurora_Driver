"""Queue integration: restart, immutable snapshots, cancellation, and ingestion."""
from pathlib import Path
import os
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aurora_jobserver.jbs import prepare
from aurora_jobserver.store import JobStore, SourceChangedError
from aurora_jobserver.worker import InboxWatcher, WorkerLock, process_one


VECTOR = b"!ZX\rJOB rectangle.jbs\n\rnormalstart START\rPU\r0. 0. V\rPD\r100. 100. V\rPU\rEND_PLOT\r"
RAW = (b"!ZX\rJOB pixels.jbs\n\rautostart START\rPICT-UL\r"
       + struct.pack("<HIIIIH", 0x58c3, 3, 2, 167, 167, 0x41)
       + b"\0\1\2\0\xff\5\4\3\0\xffEND_PLOT\r")


class ValidationTests(unittest.TestCase):
    def test_vector_and_compressed_passthrough(self):
        vector = prepare(VECTOR)
        self.assertEqual(vector.data, VECTOR)
        self.assertEqual(vector.input_format, "vector-only")
        self.assertFalse(vector.auto_start)
        compressed = prepare(RAW)
        self.assertTrue(compressed.auto_start)
        self.assertEqual(prepare(compressed.data).data, compressed.data)
        self.assertEqual(prepare(compressed.data).input_format, "compressed")

    def test_unsupported_picture_and_missing_footer(self):
        with self.assertRaisesRegex(ValueError, "not supported"):
            prepare(b"!ZX\rPICT3-UL\rEND_PLOT\r")
        with self.assertRaisesRegex(ValueError, "incomplete"):
            prepare(VECTOR[:-10])


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = JobStore(self.root / "queue")
        self.source = self.root / "input.jbs"
        self.source.write_bytes(VECTOR)

    def test_restart_retains_snapshot_settings_and_history(self):
        settings = {"material": "reference", "nested": {"label": "original"}}
        job_id = self.store.submit(self.source, settings)
        settings["nested"]["label"] = "changed"
        self.source.write_bytes(b"changed after submission")
        restarted = JobStore(self.store.root)
        result = process_one(restarted)
        self.assertEqual(result["state"], "ready")
        self.assertEqual(result["settings"]["nested"]["label"], "original")
        self.assertEqual((restarted.directory(job_id) / "prepared.jbs").read_bytes(), VECTOR)
        self.assertEqual([e["kind"] for e in restarted.history(job_id)], ["submitted", "preparing", "ready"])

    def test_interrupted_preparation_recovers_under_worker_lock(self):
        job_id = self.store.submit(self.source)
        self.store.claim()
        with WorkerLock(self.store.root):
            with self.assertRaisesRegex(RuntimeError, "already running"):
                with WorkerLock(self.store.root):
                    pass
            self.assertEqual(self.store.recover(), 1)
            result = process_one(self.store)
        self.assertEqual(result["id"], job_id)
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(result["state"], "ready")

    def test_cancel_during_preparation_is_not_overwritten(self):
        job_id = self.store.submit(self.source)
        def cancel_while_preparing(data):
            self.store.cancel(job_id)
            return prepare(data)
        with patch("aurora_jobserver.worker.prepare", side_effect=cancel_while_preparing):
            result = process_one(self.store)
        self.assertEqual(result["state"], "canceled")
        with self.assertRaises(ValueError):
            self.store.export(job_id, self.root / "canceled.jbs")
        self.store.retry(job_id)
        self.assertEqual(process_one(self.store)["state"], "ready")

    def test_failed_job_does_not_block_following_job(self):
        self.source.write_bytes(b"invalid printer output")
        bad = self.store.submit(self.source)
        self.source.write_bytes(VECTOR)
        good = self.store.submit(self.source)
        self.assertEqual(process_one(self.store)["state"], "failed")
        self.assertEqual(process_one(self.store)["state"], "ready")
        self.assertEqual(self.store.get(bad)["state"], "failed")
        self.assertEqual(self.store.get(good)["state"], "ready")

    def test_hash_checks_and_export_does_not_mean_sent(self):
        job_id = self.store.submit(self.source)
        process_one(self.store)
        destination = self.root / "export.jbs"
        self.store.export(job_id, destination)
        self.assertEqual(destination.read_bytes(), VECTOR)
        self.assertEqual(self.store.get(job_id)["state"], "ready")
        with self.assertRaises(FileExistsError):
            self.store.export(job_id, destination)
        (self.store.directory(job_id) / "prepared.jbs").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "integrity"):
            self.store.export(job_id, self.root / "bad-export.jbs")
        self.assertFalse((self.root / "bad-export.jbs").exists())

    def test_tampered_source_and_empty_prn(self):
        job_id = self.store.submit(self.source)
        (self.store.directory(job_id) / "source.jbs").write_bytes(b"tampered")
        result = process_one(self.store)
        self.assertEqual(result["state"], "failed")
        self.assertIn("integrity", result["error"])
        self.source.write_bytes(b"")
        with self.assertRaisesRegex(ValueError, "empty"):
            self.store.submit(self.source)

    def test_watcher_partial_files_restarts_and_intentional_reprints(self):
        inbox = self.store.root / "inbox"
        pending = inbox / "Default.jbs"
        pending.write_bytes(VECTOR[:-10])
        watcher = InboxWatcher(self.store)
        self.assertEqual(watcher.poll(), [])
        self.assertEqual(watcher.poll(), [])
        pending.write_bytes(VECTOR)
        self.assertEqual(watcher.poll(), [])
        self.assertEqual(len(watcher.poll()), 1)
        self.assertEqual(watcher.poll(), [])
        watcher = InboxWatcher(JobStore(self.store.root))
        self.assertEqual(watcher.poll(), [])
        self.assertEqual(watcher.poll(), [])
        stat = pending.stat()
        os.utime(pending, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
        self.assertEqual(watcher.poll(), [])
        self.assertEqual(len(watcher.poll()), 1)
        self.assertEqual(len(self.store.list()), 2)
        self.assertEqual(pending.read_bytes(), VECTOR)

    def test_watcher_observation_cannot_snapshot_a_new_generation(self):
        stat = self.source.stat()
        with self.assertRaises(SourceChangedError):
            self.store.submit(self.source, expected_stat=(stat.st_size, stat.st_mtime_ns-1))
        self.assertEqual(self.store.list(), [])

    @unittest.skipUnless((ROOT / "captures/capture-14978-28204/jbs/Default.jbs").exists(), "Private reference absent")
    def test_queue_pipeline_matches_original_jobserver(self):
        raw = ROOT / "captures/capture-14978-28204/jbs/Default.jbs"
        expected = (ROOT / "captures/capture-14978-28204/jbs/Convert/Default.jbs").read_bytes()
        job_id = self.store.submit(raw)
        self.assertEqual(process_one(self.store)["state"], "ready")
        self.assertEqual((self.store.directory(job_id) / "prepared.jbs").read_bytes(), expected)


if __name__ == "__main__":
    unittest.main()
