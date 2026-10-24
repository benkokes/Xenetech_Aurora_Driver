"""Static XP rotary arithmetic and blocked offline drafts, without device I/O."""
import copy
from dataclasses import replace
import math
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from aurora_jobserver.artwork import ProcessSettings
from aurora_jobserver.classic_settings import carriers, decode as settings_decode, parse
from aurora_jobserver.direct_print import CONTROLLER_PATH
from aurora_jobserver.jbs import DRAFT_MARKER, prepare
from aurora_jobserver.print_pipeline import encode_print
from aurora_jobserver.rotary import (XP_PI, XP_TENTH_MM_TO_INCHES,
                                    encode_rotary_draft, setup_from_devmode)
from aurora_jobserver.wire import raster_plan
from tests.test_classic_settings import payload
from tests.test_output_modes import PROCESS, sample
from tools.compare_preference_jobs import decode


ROOT = Path(__file__).resolve().parents[1]


class RotaryTests(unittest.TestCase):
    @unittest.skipUnless((ROOT/'analysis/extracted/laser-driver/XP_Files/xtlasergr.dll').is_file()
                         and (ROOT/'analysis/extracted/laser-driver/XP_Files/xtlaserui.dll').is_file(),
                         'Matched private XP binaries required for static comparison')
    def test_static_model_uses_matched_binary_constants_and_branch(self):
        from tools.recover_rotary_setup import recover
        evidence = recover()
        self.assertFalse(evidence['physical_device_io'])
        self.assertEqual(evidence['constants']['pi']['double'], XP_PI)
        self.assertEqual(evidence['constants']['tenth_mm_to_inches']['double'], XP_TENTH_MM_TO_INCHES)
        branch = '\n'.join(evidence['snippets']['graphics_rotary_branch']['instructions'])
        for instruction in ('test byte ptr [esi + 0x11c], 4', 'cmp al, bl', 'cmp al, 3',
                            'movsx edi, word ptr [esi + 0x90]', 'movsx edi, word ptr [esi + 0x92]',
                            'fmul qword ptr [0x403208]', 'fdivr qword ptr [0x403200]'):
            self.assertIn(instruction, branch)
        self.assertIn('00407537: inc ebx', evidence['snippets']['graphics_ebx_is_one']['instructions'])

    def test_recovered_constants_and_non_square_orientation_selection(self):
        self.assertEqual(struct.pack('<d', XP_PI).hex(), '182d4454fb210940')
        self.assertEqual(struct.pack('<d', XP_TENTH_MM_TO_INCHES).hex(), '080402814020703f')
        # BL is explicitly 1 in the graphics routine. Orientation values 1/3
        # select width; 0/2 select length. Unequal values catch axis swaps.
        for orientation, dimension, inches in (
            ('Normal', 'height', 2), ('UpsideDown', 'height', 2),
            ('Left90', 'width', 4), ('Right90', 'width', 4),
        ):
            setup = setup_from_devmode(1016, 508, orientation=orientation)
            self.assertEqual(setup.selected_dimension, dimension)
            self.assertAlmostEqual(setup.axis_scale, math.pi / inches)
            self.assertEqual(setup.commands, f'1 set_rotary\r{math.pi/inches:.5f} zset_axis\r'.encode())

    def test_bad_dimensions_and_orientations_never_produce_commands(self):
        for value in (True, False, None, '508', 508.0, -1, 0, 32768, float('inf')):
            for width, height in ((value, 508), (1016, value)):
                with self.subTest(width=width, height=height), self.assertRaises(ValueError):
                    setup_from_devmode(width, height)
        for orientation in (None, True, 0, '90', 'normal'):
            with self.assertRaises(ValueError):
                setup_from_devmode(1016, 508, orientation=orientation)

    def test_draft_preserves_artwork_and_process_and_cannot_be_delivered(self):
        scene = sample()
        original = copy.deepcopy(scene)
        with patch('socket.socket') as network:
            raw, cg = encode_rotary_draft(scene, ProcessSettings.parse(PROCESS),
                paper_width_tenth_mm=1016, paper_height_tenth_mm=508)
            for data in (raw, cg):
                decoded = decode(data)
                self.assertTrue(decoded['draft'])
                self.assertFalse(decoded['autostart'])
                self.assertIn('1 set_rotary', decoded['commands'])
                self.assertIn('1.57080 zset_axis', decoded['commands'])
                self.assertNotIn('0 set_rotary', decoded['commands'])
                self.assertEqual(decoded['rasters'][0]['pixels'], scene.exposure)
                self.assertEqual(decoded['rasters'][0]['origin_units'], [60, 120])
                self.assertEqual(decoded['rasters'][0]['settings']['power'], 45)
                self.assertEqual(decoded['vector_paths'][0]['points'], [list(p) for p in scene.paths[0]])
                self.assertTrue(data.startswith(b'!ZX\r'+DRAFT_MARKER+b'\r'))
                with self.assertRaisesRegex(ValueError, 'uncalibrated draft'):
                    prepare(data)
                with self.assertRaisesRegex(ValueError, 'uncalibrated draft'):
                    raster_plan(data, CONTROLLER_PATH)
            network.assert_not_called()
        self.assertEqual(scene, original)

    def test_command_like_binary_samples_are_never_modified(self):
        pixels = b'0 set_rotary\r100. set_xyup_feed\r0 PMC\r'
        scene = replace(sample(), page={'exposure':{'width':len(pixels), 'height':1,
                        'x_pixels':10, 'y_pixels':20}}, exposure=pixels)
        for data in encode_rotary_draft(scene, ProcessSettings.parse(PROCESS),
                paper_width_tenth_mm=1016, paper_height_tenth_mm=508):
            self.assertEqual(decode(data)['rasters'][0]['pixels'], pixels)

    def test_wrong_review_profile_rejected(self):
        for change in ({'dpi':100}, {'raster_grid':'other'}, {'text_rendering':'other'}):
            scene = replace(sample(), manifest=sample().manifest | change)
            with self.assertRaisesRegex(ValueError, '167-DPI Corel review profile'):
                encode_rotary_draft(scene, ProcessSettings.parse(PROCESS),
                    paper_width_tenth_mm=1016, paper_height_tenth_mm=508)

    def test_normal_printing_still_holds_cylindrical_before_encoding(self):
        snapshot = payload(Cylindrical=True)
        settings = settings_decode(carriers(parse(snapshot)), snapshot)
        self.assertIn('Cylindrical', settings['held_features'])
        with patch('aurora_jobserver.print_pipeline._encode') as encoder, patch('socket.socket') as network:
            with self.assertRaisesRegex(ValueError, 'Cylindrical'):
                encode_print(sample(), settings, 'HeldRotary')
            encoder.assert_not_called()
            network.assert_not_called()


if __name__ == '__main__':
    unittest.main()
