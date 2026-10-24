"""Independent geometry/pixel expectations and blocked draft delivery."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

from aurora_jobserver.artwork import GRID, XP_GRID, ProcessSettings, build, encode, load_scene, units
from aurora_jobserver.jbs import DRAFT_MARKER, prepare
from aurora_jobserver.store import JobStore
from aurora_jobserver.worker import process_one
from aurora_jobserver.wire import raster_plan
from tools.raster_codec import decompress7


SETTINGS = {'schema_version': 1, 'units': 'inches-per-second', 'raster_speed_ips': 30,
            'raster_power_percent': 30, 'vector_speed_ips': 1, 'vector_power_percent': 15, 'vector_ppi': 1000}


class ArtworkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.intake = self.root / 'input'
        self.intake.mkdir()
        source = b'fake document snapshot, not read by the encoder'
        exposure = b'\0\x80\xff\x01\x02\x03'
        (self.intake / 'source.bin').write_bytes(source)
        (self.intake / 'exposure.bin').write_bytes(exposure)
        self.doc = {
            'schema_version': 2, 'raster_grid': GRID, 'dpi': 167, 'render_dpi': 1000 / 6,
            'source_file': 'source.bin', 'source_sha256': hashlib.sha256(source).hexdigest(),
            'pages': [{'width_mm': 50.8, 'height_mm': 50.8, 'pixel_width': 334, 'pixel_height': 334,
                       'review_reasons': [], 'has_visible_artwork': True,
                       'exposure': {'encoding': 'exposure-u8-row-major', 'colored_pixels': 0,
                                    'width': 3, 'height': 2, 'x_pixels': 10, 'y_pixels': 20,
                                    'file': 'exposure.bin', 'sha256': hashlib.sha256(exposure).hexdigest()},
                       'cuts': [{'closed': True, 'points_mm': [[0, 0], [25.4, 0], [25.4, 25.4], [0, 25.4]]}]}],
        }
        self.write()

    def tearDown(self):
        self.temp.cleanup()

    def write(self):
        (self.intake / 'document.json').write_text(json.dumps(self.doc))

    def scene(self):
        self.write()
        return load_scene(self.intake)

    def test_ips_and_power_are_encoded_as_requested(self):
        raw, converted = encode(self.scene(), ProcessSettings.parse(SETTINGS), 'Test')
        self.assertIn(b'30000. speed\r30.00 power\r', raw)
        self.assertIn(b'1000. speed\r15.00 power\r1000. set_vppi\r', raw)
        self.assertIn(b'normalstart START\r', raw)
        self.assertNotIn(b'autostart', raw)
        self.assertEqual(prepare(converted, allow_draft=True).data, converted)

    def test_one_inch_square_and_explicit_closure(self):
        scene = self.scene()
        self.assertEqual(scene.geometry()['paths_units'][0], [[0, 0], [1000, 0], [1000, 1000], [0, 1000], [0, 0]])
        raw, _ = encode(scene, ProcessSettings.parse(SETTINGS))
        self.assertIn(b'1000.0 1000.0 V\r0.0 1000.0 V\r0.0 0.0 V\rPU', raw)
        self.assertEqual(str(units(12.7)), '500.0')

    def test_xp_nominal_grid_matches_reference_square_scale(self):
        self.doc['raster_grid'] = XP_GRID
        self.doc['render_dpi'] = 167
        scene = self.scene()
        self.assertEqual(scene.geometry()['raster_grid'], XP_GRID)
        self.assertEqual(scene.geometry()['paths_units'][0], [[0, 0], [1002, 0], [1002, 1002], [0, 1002], [0, 0]])
        raw, compressed = encode(scene, ProcessSettings.parse(SETTINGS))
        self.assertIn(b'1002.0 1002.0 V\r', raw)
        self.assertIn(b'60.0 120.0 V\r', raw)
        for data in (raw, compressed):
            with self.assertRaisesRegex(ValueError, 'uncalibrated draft'):
                prepare(data)
        self.doc['render_dpi'] = 1000 / 6
        with self.assertRaisesRegex(ValueError, 'sampling rate'):
            self.scene()

    def test_xp_bed_bounds_and_fixed_point_rounding(self):
        self.doc['raster_grid'] = XP_GRID
        self.doc['render_dpi'] = 167
        self.doc['pages'][0].update(width_mm=762, height_mm=457.2, pixel_width=5010, pixel_height=3006)
        self.scene()
        # Independent fixed-coordinate cases: +1/16 pixel * 6 rounds to zero;
        # +2/16 pixel * 6 rounds to one. Exact one inch is 167 * 6.
        self.assertEqual(units(25.4 / 167 / 16, XP_GRID), 0)
        self.assertEqual(units(25.4 / 167 / 8, XP_GRID), 1)
        self.assertEqual(units(25.4, XP_GRID), 1002)
        self.doc['pages'][0]['pixel_width'] = 5000
        with self.assertRaisesRegex(ValueError, 'Raster size'):
            self.scene()

    def test_raster_origin_snake_order_and_independent_decode(self):
        raw, compressed = encode(self.scene(), ProcessSettings.parse(SETTINGS))
        self.assertIn(b'60.0 120.0 V\r6.000 set_gspot\rPICT-UL\r', raw)
        offset = raw.index(b'PICT-UL\r') + 8
        self.assertEqual(struct.unpack_from('<HIIIIH', raw, offset), (0x58c3, 3, 2, 167, 167, 0x41))
        expected = b'\0\x80\xff\0\xff\x03\x02\x01\0\xff'
        self.assertEqual(raw[offset+20:offset+30], expected)
        packed = compressed.index(b'PICT-UL\r') + 8
        pixels, _, _ = decompress7(compressed, packed + 20, max_output=10)
        self.assertEqual(pixels, expected)

    def test_draft_blocked_by_queue_and_wire(self):
        raw, compressed = encode(self.scene(), ProcessSettings.parse(SETTINGS))
        for data in (raw, compressed):
            with self.assertRaisesRegex(ValueError, 'uncalibrated draft'):
                prepare(data)
            with self.assertRaisesRegex(ValueError, 'uncalibrated draft'):
                raster_plan(data, r'c:\xfiles\jbs\Convert\Default.jbs')
        path = self.root / 'draft.jbs'
        path.write_bytes(raw)
        store = JobStore(self.root / 'queue')
        job = store.submit(path)
        process_one(store)
        self.assertEqual(store.get(job)['state'], 'failed')
        self.assertIn('uncalibrated draft', store.get(job)['error'])

    def test_wrong_grid_and_unresolved_review_rejected(self):
        original = copy.deepcopy(self.doc)
        for field, value in [('schema_version', 1), ('raster_grid', 'document-dpi'), ('render_dpi', 167), ('text_rendering', 'unknown')]:
            self.doc = copy.deepcopy(original); self.doc[field] = value
            with self.assertRaises(ValueError):
                self.scene()
        self.doc = original; self.doc['pages'][0]['review_reasons'] = ['clipped']
        with self.assertRaisesRegex(ValueError, 'review'):
            self.scene()

    def test_tampered_exposure_source_and_path_rejected(self):
        (self.intake / 'exposure.bin').write_bytes(b'xxxxxx')
        with self.assertRaisesRegex(ValueError, 'Exposure integrity'):
            self.scene()
        self.doc['pages'][0]['exposure']['file'] = '../outside.bin'
        with self.assertRaisesRegex(ValueError, 'artifact filename'):
            self.scene()
        (self.intake / 'source.bin').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Source snapshot'):
            self.scene()

    def test_bounds_and_colored_engraving_rejected(self):
        original = copy.deepcopy(self.doc)
        for field, value in [('x_pixels', 333), ('colored_pixels', 1), ('width', 0)]:
            self.doc = copy.deepcopy(original); self.doc['pages'][0]['exposure'][field] = value
            with self.assertRaises(ValueError):
                self.scene()
        self.doc = original; self.doc['pages'][0]['cuts'][0]['points_mm'][1][0] = 100
        with self.assertRaisesRegex(ValueError, 'cut X'):
            self.scene()

    def test_settings_require_explicit_units_and_valid_values(self):
        for key, value in [('units', 'percent'), ('raster_speed_ips', float('nan')), ('vector_ppi', True),
                           ('raster_power_percent', 101), ('vector_speed_ips', 0), ('raster_power_percent', 1.234)]:
            settings = dict(SETTINGS); settings[key] = value
            with self.assertRaises(ValueError):
                ProcessSettings.parse(settings)

    def test_geometry_audit_without_process_settings_and_no_overwrite(self):
        result = build(self.intake, self.root / 'audit')
        self.assertEqual(result['state'], 'awaiting_process_settings')
        self.assertEqual(len(list((self.root / 'audit').iterdir())), 1)
        result = build(self.intake, self.root / 'encoded', SETTINGS)
        self.assertEqual(result['native_commands']['raster_speed'], 30000)
        self.assertEqual(result['state'], 'draft_encoded')
        self.assertTrue((self.root / 'encoded' / 'job.cg.jbs.draft').read_bytes().startswith(b'!ZX\r' + DRAFT_MARKER))
        with self.assertRaises(FileExistsError):
            build(self.intake, self.root / 'encoded', SETTINGS)

    def test_vector_only_and_raster_only_drafts(self):
        raster = copy.deepcopy(self.doc['pages'][0]['exposure'])
        self.doc['pages'][0]['exposure'] = None
        raw, converted = encode(self.scene(), ProcessSettings.parse(SETTINGS))
        self.assertEqual(raw, converted)
        self.assertEqual(prepare(raw, allow_draft=True).rasters, 0)
        self.doc['pages'][0]['exposure'] = raster
        self.doc['pages'][0]['cuts'] = []
        raw, _ = encode(self.scene(), ProcessSettings.parse(SETTINGS))
        self.assertIn(b'PICT-UL', raw)
        self.assertNotIn(b'set_vppi', raw)
        self.doc['pages'][0]['exposure'] = None
        with self.assertRaisesRegex(ValueError, 'No engraving or cutting'):
            self.scene()

    def test_injection_and_nonfinite_points_rejected(self):
        with self.assertRaisesRegex(ValueError, 'title'):
            encode(self.scene(), ProcessSettings.parse(SETTINGS), 'bad\rPD')
        self.doc['pages'][0]['cuts'][0]['points_mm'][0][0] = float('inf')
        with self.assertRaisesRegex(ValueError, 'Nonfinite'):
            self.scene()


if __name__ == '__main__':
    unittest.main()
