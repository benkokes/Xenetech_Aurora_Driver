"""Collector regression: real WSH fixture copies plus independent host decode.

All jobs are tiny generated fixtures, never submitted to a printer or device.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from aurora_jobserver.artwork import encode, _encode, ProcessSettings
from tests.test_output_modes import sample, PROCESS
from tools.xp_reference_collector import arm, case_path, verify

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'tools/xp-reference-collector/collect-new-jobs.vbs'
CSCRIPT=shutil.which('cscript.exe')


def fixture(**changes):
    return _encode(sample(),ProcessSettings.parse(PROCESS),'CollectorFixture',draft=False,**changes)


class CandidateValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.case=self.root/'case-one';self.case.mkdir()
        self.raw,self.cg=fixture()

    def tearDown(self):self.temp.cleanup()

    def test_complete_raw_and_compressed_candidates_validate_without_network_and_are_immutable(self):
        for label,data in (('raw',self.raw),('compressed',self.cg)):
            case=self.root/label;case.mkdir();(case/'candidate.jbs').write_bytes(data)
            with patch('socket.socket') as network:
                report=verify(self.root,label)
            network.assert_not_called()
            self.assertEqual(report['state'],'verified_offline_reference')
            self.assertEqual((case/'Default.jbs').read_bytes(),data)
            self.assertEqual(len(report['decoded']['rasters']),1)
            self.assertTrue((case/'verified.json').is_file())
            with self.assertRaises(FileExistsError):verify(self.root,label)

    def test_empty_incomplete_and_corrupt_row_candidates_never_publish_success(self):
        # Keep the footer in the malformed-row fixture: framing alone must not
        # turn a structurally damaged binary picture into a successful capture.
        damaged=self.raw.replace(b'\x00\x80\xff\x00\xff',b'\x00\x80\xff\x00\xfe',1)
        self.assertNotEqual(damaged,self.raw)
        for data in (b'',self.raw[:20],self.raw[:-1],self.raw[:-15],damaged,self.cg[:-15]):
            with self.subTest(length=len(data)):
                (self.case/'candidate.jbs').write_bytes(data)
                with self.assertRaises(ValueError):verify(self.root,'case-one')
                self.assertFalse((self.case/'verified.json').exists())
                self.assertFalse((self.case/'Default.jbs').exists())
                self.assertEqual((self.case/'candidate.jbs').read_bytes(),data)

    def test_autostart_draft_and_empty_artwork_are_not_accepted_as_safe_reference(self):
        for data in (fixture(autostart=True)[0],
                     encode(sample(),ProcessSettings.parse(PROCESS),'Draft')[0],
                     b'!ZX\rEND_PLOT\r'):
            (self.case/'candidate.jbs').write_bytes(data)
            with self.assertRaises(ValueError):verify(self.root,'case-one')
            self.assertFalse((self.case/'verified.json').exists())

    def test_stopped_unarmed_used_and_invalid_cases_fail_closed(self):
        for label in ('../outside','Upper','x'*49,'','a/b'):
            with self.assertRaises(ValueError):case_path(self.root,label)
        (self.root/'stop-collector.txt').touch()
        with self.assertRaisesRegex(ValueError,'stopped'):arm(self.root,'stopped')
        self.assertFalse((self.root/'request.txt').exists())
        (self.root/'stop-collector.txt').unlink()
        with self.assertRaises(TimeoutError):arm(self.root,'not-armed',timeout=.01)
        (self.case/'candidate.jbs').write_bytes(b'')
        with self.assertRaises(FileExistsError):arm(self.root,'case-one')


@unittest.skipUnless(os.name=='nt' and CSCRIPT,'Windows Script Host required')
class GuestSnapshotTests(unittest.TestCase):
    def test_changed_binary_content_during_stability_wait_never_publishes_candidate(self):
        raw,_=fixture()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'source.jbs';target=root/'candidate.jbs'
            source.write_bytes(raw)
            process=subprocess.Popen([CSCRIPT,'//nologo','//T:10',str(SCRIPT),'--snapshot',str(source),str(target)],
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                time.sleep(.4)
                # Same framing, size and valid binary structure. A different
                # raster signal must reset stability rather than archive either.
                changed=raw.replace(b'\x00\x80\xff\x00\xff',b'\x00\x81\xff\x00\xff',1)
                self.assertNotEqual(changed,raw)
                source.write_bytes(changed)
                stdout,stderr=process.communicate(timeout=15)
                self.assertEqual(process.returncode,2,stdout+stderr)
                self.assertIn('CHANGING',stdout)
                self.assertFalse(target.exists())
            finally:
                if process.poll() is None:process.kill();process.wait()

    def test_real_vbscript_rejects_intermediate_files_then_copies_completed_file_once(self):
        raw,cg=fixture()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'source.jbs';target=root/'candidate.jbs'
            def snapshot():
                return subprocess.run([CSCRIPT,'//nologo','//T:10',str(SCRIPT),'--snapshot',str(source),str(target)],
                    capture_output=True,text=True,timeout=15)
            # Reproduce observed zero-byte intermediate before the very same
            # source finishes. Failure must leave no destination to block retry.
            for data in (b'',raw[:20],raw[:-1],b'wrong\rEND_PLOT\r'):
                source.write_bytes(data);result=snapshot()
                self.assertEqual(result.returncode,2,result.stdout+result.stderr)
                self.assertIn('INCOMPLETE',result.stdout)
                self.assertFalse(target.exists())
            source.write_bytes(raw);result=snapshot()
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('CANDIDATE ONLY',result.stdout)
            self.assertEqual(target.read_bytes(),raw)
            source.write_bytes(cg);result=snapshot()
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(target.read_bytes(),raw)


if __name__=='__main__':unittest.main()
