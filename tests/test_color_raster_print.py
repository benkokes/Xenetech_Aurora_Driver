"""Native color printing candidate tests. Equipment access is forbidden here."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from aurora_jobserver.color_scene import load_color_scene
from aurora_jobserver.print_pipeline import prepare_capture, encode_print
from aurora_jobserver.print_service import PrintService
from aurora_jobserver.transport import Endpoint
from tests.test_color_job_review import synthetic_snapshot
from tests.test_print_pipeline import capture_document
from tools.build_color_raster_review import reference_palette
from tools.compare_preference_jobs import decode
from tools.controller_simulator import ControllerSimulator
from tests.test_print_pipeline import FAST

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'captures/host-color-mixed-preferences-20261020/6ef4b165-0e4c-4806-ad34-43fc6630db0c/source.bin'
INTAKE=ROOT/'build/frontend/Aurora.XpsIntake.exe'


def safe_palette():
    table=reference_palette()
    # The XP identification fixture has a legacy 100 ips White fallback.
    # This synthetic job explicitly selects a supported fallback speed.
    table[15]['SpeedIps']='1'
    return table


@unittest.skipUnless(SOURCE.is_file() and INTAKE.is_file(),'Private native Corel fixture required')
class NativeColorPrintTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def capture(self,name,**changes):
        return capture_document(self.root/name,synthetic_snapshot(SOURCE,table=changes.pop('table',safe_palette()),
            **({'Output':'RasterOnly','Autostart':False,'SortColors':True}|changes)))

    def prepare(self,capture,name='prepared'):
        return prepare_capture(capture,self.root/name,INTAKE,allow_color_rasters=True)

    def test_native_masks_settings_and_raster_only_filter_survive_encoding(self):
        with patch('socket.socket') as network:
            capture=self.capture('capture')
            with self.assertRaisesRegex(ValueError,'UseColors'):
                prepare_capture(capture,self.root/'held',INTAKE,allow_color_rasters=False)
            result=self.prepare(capture)
            self.assertEqual(result['state'],'encoded_for_direct_print')
            scene=load_color_scene(self.root/'prepared/intake')
            self.assertEqual(scene.appearance_error,0)
            self.assertEqual(len(scene.paths),5)
            actual=decode((self.root/'prepared/job.cg.jbs').read_bytes())
            self.assertEqual([r['settings']['power'] for r in actual['rasters']],[45,11,22])
            self.assertEqual([r['settings']['speed'] for r in actual['rasters']],[30000,1000,2000])
            self.assertEqual(actual['vector_paths'],[])
            self.assertEqual(result,self.prepare(capture))
            with self.assertRaisesRegex(ValueError,'UseColors'):
                prepare_capture(capture,self.root/'prepared',INTAKE,allow_color_rasters=False)
            network.assert_not_called()

    def test_mixed_candidate_remains_held_until_independent_boundary_evidence(self):
        with patch('socket.socket') as network:
            with patch('aurora_jobserver.color_print.MIXED_BOUNDARY_VERIFIED',False),self.assertRaisesRegex(ValueError,'independent XP capture'):
                self.prepare(self.capture('mixed',Output='RasterAndVector'))
            # Exercise candidate composition only, without changing the release gate.
            scene=load_color_scene(self.root/'prepared/intake')
            from aurora_jobserver.printer_settings import settings_from_xps
            settings=settings_from_xps(self.root/'prepared/source.oxps')
            raw,cg=encode_print(scene,settings,'OfflineMixed',allow_color_rasters=True)
            actual=decode(cg)
            self.assertEqual(len(actual['rasters']),3)
            self.assertEqual(len(actual['vector_paths']),5)
            self.assertIn(b'normalstart START\r',raw)
            network.assert_not_called()

    def test_all_disabled_is_durable_local_outcome_and_next_fresh_job_proceeds(self):
        table=safe_palette()
        for color in table:color['Enabled']=False
        service=PrintService(self.root/'service',Endpoint('127.0.0.1'),INTAKE,
            locks=self.root/'locks',allow_color_rasters=True)
        capture=capture_document(service.captures,synthetic_snapshot(SOURCE,table=table,Output='RasterAndVector',Autostart=False))
        with patch('socket.socket') as network:
            result=service.poll_once()
            self.assertEqual(result['state'],'nothing_to_print')
            self.assertIsNone(result['delivery'])
            self.assertIsNone(service.poll_once())
            self.assertEqual(len(service.store.print_outcomes()),1)
            self.assertFalse(list((self.root/'locks').glob('*.pending.json')))
            network.assert_not_called()
        fresh=self.prepare(self.capture('fresh'),'fresh-prepared')
        self.assertEqual(fresh['state'],'encoded_for_direct_print')
        self.assertNotEqual(capture.name,fresh['print_id'])

    def test_native_evidence_tampering_and_unsupported_content_fail_closed(self):
        self.prepare(self.capture('capture'))
        intake=self.root/'prepared/intake';path=intake/'document.json'
        original=json.loads(path.read_text())
        changes=(lambda d:d['pages'][0]['review_reasons'].append('Unsupported bitmap'),
            lambda d:d['pages'][0]['color_layers']['layers'][0]['coverage'].update(sha256='0'*64),
            lambda d:d['pages'][0]['cuts'][0].update(width_mm=.5),
            lambda d:d.update(cut_color='any'))
        for change in changes:
            doc=copy.deepcopy(original);change(doc);path.write_text(json.dumps(doc))
            with self.assertRaises(ValueError):load_color_scene(intake)
        path.write_text(json.dumps(original))

    def test_independent_xp_mixed_capture_matches_complete_raw_and_cg(self):
        from tools.verify_mixed_color_reference import verify
        report=verify(self.root/'xp-verified')
        self.assertEqual(report['raster_regions'],2)
        self.assertEqual(report['vector_paths'],3)
        self.assertTrue(report['complete_raw_matches_except_draft_marker'])
        self.assertFalse(report['requested_all_enabled_case'])

    def test_normal_default_service_sends_mixed_colors_once_only_to_loopback(self):
        service_root=self.root/'normal-service'
        capture=capture_document(service_root/'captures',synthetic_snapshot(SOURCE,table=safe_palette(),
            Output='RasterAndVector',Autostart=False,SortColors=True))
        result=prepare_capture(capture,service_root/'prepared-prints'/capture.name,INTAKE)
        cg=(service_root/'prepared-prints'/capture.name/'job.cg.jbs').read_bytes()
        with ControllerSimulator(cg,echo=False,fragment=True) as sim:
            service=PrintService(service_root,sim.endpoint,INTAKE,timing=FAST,locks=self.root/'locks')
            delivered=service.poll_once()
            self.assertEqual(delivered['state'],'completed')
            self.assertTrue(sim.upload_received.is_set())
            self.assertIsNone(service.poll_once())
            self.assertEqual(sum(e['kind']=='uploaded' for e in service.store.history(delivered['id'])),1)
        actual=decode(cg)
        self.assertEqual(len(actual['rasters']),3)
        self.assertEqual(len(actual['vector_paths']),5)
        self.assertEqual(result['printer_settings']['held_features'],[])

    def test_unverified_color_transform_combinations_hold_before_native_conversion(self):
        for key in ('BottomUp','InvertRaster','PauseColors'):
            capture=self.capture(key,**{key:True})
            with patch('aurora_jobserver.print_pipeline.subprocess.run') as native:
                with self.assertRaisesRegex(ValueError,'ColorRaster'+key):
                    prepare_capture(capture,self.root/(key+'-held'),INTAKE)
                native.assert_not_called()

