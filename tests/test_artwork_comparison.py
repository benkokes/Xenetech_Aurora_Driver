"""Offline comparisons must distinguish settings, placement and raster samples."""
from pathlib import Path
import struct
import tempfile
import unittest

from tools.compare_artwork_jobs import compare


def job(offset=0, signal=b'\0\xff'):
    return (f'!ZX\r30000. speed\r30.00 power\rPU\r{60+offset}.0 120.0 V\rPICT-UL\r'.encode()
            + struct.pack('<HIIIIH', 0x58c3, 2, 1, 167, 167, 0x41) + signal + b'\0\xff'
            + f'1000. speed\r15.00 power\r1000. set_vppi\rPU\r{100+offset}.0 200.0 V\rPD\r{112+offset}.0 200.0 V\r{112+offset}.0 212.0 V\rPU\r0. 0. V\rEND_PLOT\r'.encode())


class ComparisonTests(unittest.TestCase):
    def test_offset_and_pixel_change_do_not_change_settings_or_dimensions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            a, b = root/'a.jbs', root/'b.jbs'
            a.write_bytes(job()); b.write_bytes(job(6,b'\0\x80'))
            result = compare(a,b,root/'comparison')
            self.assertTrue(result['settings_equal'])
            self.assertFalse(result['vector_commands_equal'])
            self.assertEqual(result['raster_candidate_minus_reference_origin'], [6,0])
            self.assertEqual(result['vectors'], [{'reference_size':[12,12], 'candidate_size':[12,12], 'candidate_minus_reference_origin':[6,0]}])
            self.assertFalse(result['raster_pixels_exact'])
            self.assertEqual(result['crop_top_left_comparison']['mismatched_pixels'],1)
            self.assertEqual(result['crop_top_left_comparison']['mean_absolute_signal_error'],63.5)

    def test_identical_content_and_malformed_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            a, b = root/'a.jbs', root/'b.jbs'
            a.write_bytes(job()); b.write_bytes(job())
            result = compare(a,b,root/'same')
            self.assertTrue(result['raster_pixels_exact'])
            self.assertTrue(result['vector_commands_equal'])
            self.assertTrue(result['initialization_commands_equal'])
            self.assertEqual(result['crop_top_left_comparison']['mean_absolute_signal_error'],0)
            b.write_bytes(job().replace(b'\0\xff1000. speed',b'\0\xfe1000. speed'))
            with self.assertRaisesRegex(ValueError,'row trailer'):
                compare(a,b,root/'bad')
