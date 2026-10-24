"""A physical-test staging path is limited to the exact reviewed reference."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from aurora_jobserver.artwork import load_scene, encode, ProcessSettings
from aurora_jobserver.calibration import stage, validate_reference, SETTINGS
from aurora_jobserver.jbs import prepare


INTAKE = Path(__file__).resolve().parents[1] / 'runtime/coreldraw-compat-167-checked'


class CalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not INTAKE.is_dir():
            raise unittest.SkipTest('Private reviewed artwork intake is unavailable')
        cls.scene = load_scene(INTAKE)

    def test_exact_reference_stages_held_non_autostart_job_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            destination=Path(temp)/'calibration'
            result=stage(INTAKE,destination)
            self.assertEqual(result['state'],'staged_offline_awaiting_operator_readiness')
            self.assertFalse(result['physical_size_validated'])
            for name in ('calibration.raw.jbs','calibration.cg.jbs'):
                job=prepare((destination/name).read_bytes())
                self.assertFalse(job.auto_start)
                self.assertEqual(job.rasters,1)
                self.assertEqual(job.title,'AuroraCalibration167')
            self.assertEqual((destination/'calibration.cg.jbs').read_bytes(),prepare((destination/'calibration.raw.jbs').read_bytes()).data)
            self.assertIn('data:image/png;base64,',(destination/'preview.svg').read_text())
            measurement=json.loads((destination/'measurements-template.json').read_text())
            self.assertIsNone(measurement['square_width_mm'])
            with self.assertRaises(FileExistsError):
                stage(INTAKE,destination)

    def test_other_source_pixels_positions_or_modes_cannot_be_released(self):
        for mutation in ('source','pixels','path','dpi','text'):
            scene=copy.deepcopy(self.scene)
            if mutation=='source': scene.manifest['source_sha256']='0'*64
            elif mutation=='pixels': object.__setattr__(scene,'exposure',b'\0'*len(scene.exposure))
            elif mutation=='path': object.__setattr__(scene,'paths',scene.paths+scene.paths)
            elif mutation=='dpi': scene.manifest['dpi']=100
            else: scene.manifest['text_rendering']='auto'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_reference(scene)

    def test_requested_fifty_percent_increase_changes_only_raster_power_and_title(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            stage(INTAKE,root/'old')
            result=stage(INTAKE,root/'next',raster_power_percent=45)
            self.assertEqual(result['process_settings']['raster_power_percent'],45)
            a=(root/'old/calibration.raw.jbs').read_bytes()
            b=(root/'next/calibration.raw.jbs').read_bytes()
            self.assertEqual(b,a.replace(b'JOB AuroraCalibration167\n\r',b'JOB AuroraCal167P45\n\r').replace(b'30.00 power\r',b'45.00 power\r',1))
            self.assertIn(b'30000. speed\r45.00 power\r',b)
            self.assertIn(b'1000. speed\r15.00 power\r1000. set_vppi\r',b)
            self.assertFalse(prepare(b).auto_start)
            for power in (True,44,80,45.0):
                with self.assertRaises(ValueError):
                    stage(INTAKE,root/'rejected',raster_power_percent=power)

    def test_ordinary_encoding_of_the_same_artwork_stays_blocked(self):
        raw,compressed=encode(self.scene,ProcessSettings.parse(SETTINGS))
        for data in (raw,compressed):
            with self.assertRaisesRegex(ValueError,'uncalibrated draft'):
                prepare(data)
