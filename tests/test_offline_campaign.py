import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.test_classic_settings import REFERENCE, ticket
from tools.offline_raster_campaign import run
from tools.verify_native_preferences_matrix import verify


class OfflineCampaignTests(unittest.TestCase):
    def test_campaign_checks_samples_malformed_inputs_and_draft_guards(self):
        with tempfile.TemporaryDirectory() as temp:
            result = run(Path(temp)/'campaign', cases=3, seed=91)
            self.assertEqual(result['state'], 'complete')
            self.assertEqual(result['completed_cases'], 3)
            self.assertEqual(result['raw_cg_decodes'], 6)
            self.assertEqual(result['malformed_inputs_rejected'], 12)
            self.assertEqual(result['draft_guards_checked'], 6)
            self.assertEqual(result['shape_pattern_mode_dpi_combinations'], 3)
            self.assertFalse(result['physical_device_io_performed'])
            with self.assertRaises(FileExistsError): run(Path(temp)/'campaign', cases=1)

    def test_failure_is_checkpointed_with_reproducible_drafts_and_no_network(self):
        with tempfile.TemporaryDirectory() as temp, patch('tools.offline_raster_campaign.decode', side_effect=ValueError('synthetic failure')):
            root=Path(temp)/'campaign'
            result=run(root, cases=1)
            self.assertEqual(result['state'], 'failed')
            self.assertEqual(result['completed_cases'], 0)
            self.assertIn('synthetic failure', result['error'])
            self.assertTrue((root/'failing.raw.jbs.draft').read_bytes().startswith(b'!ZX\r'))
            self.assertEqual(json.loads((root/'progress.json').read_text())['state'], 'failed')
        for bounds in ({'cases':0}, {'cases':100001}, {'max_seconds':0}, {'max_seconds':30000}):
            with tempfile.TemporaryDirectory() as temp, self.assertRaises(ValueError): run(Path(temp)/'invalid', **bounds)

    def native_fixture(self, root):
        root.mkdir()
        xml=REFERENCE.read_text(encoding='utf-8-sig')
        encoded=base64.b64encode(xml.encode()).decode()
        (root/'expected-0.xml').write_text(xml,encoding='utf-8')
        (root/'validated-0.xml').write_bytes(ticket(encoded))
        (root/'restored-0.xml').write_bytes(ticket(encoded))
        (root/'cases.tsv').write_text('index\tcase\tpayload_characters\tdevmode_bytes\n0\tfixture\t'+str(len(encoded))+'\t41404\n')
        (root/'result.txt').write_text('PASS: 1 independent full snapshots survived native validation and DEVMODE roundtrip.')

    def test_saved_native_verifier_reads_both_stages_without_spooler_or_sockets(self):
        with tempfile.TemporaryDirectory() as temp, patch('socket.socket') as socket:
            root=Path(temp); self.native_fixture(root/'native')
            report=verify(root/'native', root/'report')
            self.assertEqual(report['case_count'],1)
            self.assertEqual(report['native_stages_verified'],2)
            self.assertFalse(report['printer_or_device_io_performed'])
            socket.assert_not_called()

    def test_native_verifier_rejects_changed_payload_and_incomplete_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.native_fixture(root/'native')
            changed=(root/'native/expected-0.xml').read_text().replace('<RasterPower>45</RasterPower>', '<RasterPower>46</RasterPower>')
            (root/'native/expected-0.xml').write_text(changed)
            with self.assertRaisesRegex(AssertionError,'disagree'): verify(root/'native',root/'report')
            self.assertFalse((root/'report').exists())
            (root/'native/result.txt').write_text('PASS: 2 independent full snapshots')
            with self.assertRaisesRegex(ValueError,'manifest disagree'): verify(root/'native',root/'report')


if __name__=='__main__': unittest.main()
