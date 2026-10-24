from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

from aurora_jobserver.artwork import encode, ProcessSettings
from tools.compare_preference_jobs import compare, decode, pixel_matches, png_gray
from tools.make_preferences_sample import bmp24, create, sample
from tests.test_output_modes import CAPTURES, PROCESS, sample as scene


class PreferenceComparisonTests(unittest.TestCase):
    def test_all_modes_raw_and_cg_decode_without_network_or_pixel_commands(self):
        for mode, counts in (('raster-and-vector', (1, 1)), ('raster-only', (1, 0)), ('vector-only', (0, 1))):
            with self.subTest(mode=mode), patch('socket.socket') as sock:
                raw, cg = encode(scene(), ProcessSettings.parse(PROCESS), 'Offline', output_mode=mode)
                a, b = decode(raw), decode(cg)
                self.assertEqual((len(a['rasters']), len(a['vector_paths'])), counts)
                self.assertEqual(a['commands'], b['commands'])
                self.assertEqual(a['vector_paths'], b['vector_paths'])
                for raster in a['rasters'] + b['rasters']:
                    self.assertEqual(raster['pixels'], b'\0\x80\xff\x01\x02\x03')
                    self.assertEqual(raster['origin_units'], [60, 120])
                    self.assertEqual(raster['resolution_dpi'], [167, 167])
                sock.assert_not_called()

    def test_binary_pixels_are_not_parsed_as_commands_and_multiple_rasters_work(self):
        from dataclasses import replace
        s = replace(scene(), page={'exposure': {'width': 5, 'height': 2, 'x_pixels': 10, 'y_pixels': 20}}, exposure=b'PD\rPICT-UL')
        raw, _ = encode(s, ProcessSettings.parse(PROCESS), 'Binary')
        start, finish = raw.index(b'PICT-UL\r'), raw.index(b'1000. speed\r')
        picture = raw[start:finish]
        doubled = raw[:finish] + picture + raw[finish:]
        result = decode(doubled)
        self.assertEqual(len(result['rasters']), 2)
        self.assertEqual(len(result['vector_paths']), 1)
        self.assertEqual(result['rasters'][0]['pixels'], b'PD\rPICT-UL')

    def test_pixel_transforms_separate_from_placement_and_settings(self):
        r = {'width': 3, 'height': 2, 'pixels': b'\0\x20\xff\x01\x02\x03'}
        variants = {'identity': r['pixels'], 'horizontal_flip': b'\xff\x20\0\x03\x02\x01',
                    'vertical_flip': b'\x01\x02\x03\0\x20\xff', 'rotate_180': r['pixels'][::-1],
                    'identity_and_invert': bytes(255-i for i in r['pixels'])}
        for name, pixels in variants.items():
            result = pixel_matches(r, {**r, 'pixels': pixels})
            self.assertEqual(result['pixel_transform_matches'], [name])
        self.assertFalse(pixel_matches(r, {'width': 2, 'height': 3, 'pixels': r['pixels']})['same_dimensions'])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw, _ = encode(scene(), ProcessSettings.parse(PROCESS), 'Original')
            other = raw.replace(b'60.0 120.0 V', b'66.0 132.0 V').replace(b'PICT-UL', b'PICT-LL')
            (root/'a').write_bytes(raw); (root/'b').write_bytes(other)
            result = compare(root/'a', root/'b', root/'report')
            pair = result['raster_pairs_by_capture_order'][0]
            self.assertEqual(pair['pixel_transform_matches'], ['identity'])
            self.assertEqual(pair['origin_candidate_minus_reference'], [6, 12])
            self.assertFalse(pair['origin_labels_equal'])
            self.assertTrue(result['vector_geometry_equal'])
            self.assertTrue((root/'report/reference-raster-01.png').is_file())
            with self.assertRaises(FileExistsError):
                compare(root/'a', root/'b', root/'report')

    def test_malformed_inputs_do_not_create_reports(self):
        raw, cg = encode(scene(), ProcessSettings.parse(PROCESS), 'Bad')
        variants = (raw[:-10], raw + b'PD\r', raw.replace(b'PICT-UL\r', b'PICT-UNKNOWN\r'),
                    raw.replace(b'\0\xff\x03\x02\x01', b'\0\x00\x03\x02\x01'),
                    cg[:cg.index(b'cG')+21], raw.replace(b'PD\r', b'PD\rPD\r'),
                    raw.replace(b'60.0 120.0 V', b'9'*400+b' 120.0 V'))
        for data in variants:
            with self.subTest(data=data[-15:]):
                with self.assertRaises(ValueError):
                    decode(data)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root/'bad').write_bytes(raw[:-10])
            with self.assertRaises(ValueError): compare(root/'bad', root/'bad', root/'report')
            self.assertFalse((root/'report').exists())

    @unittest.skipUnless(all(p.is_file() for p in CAPTURES.values()), 'Private XP reference captures required')
    def test_independent_xp_modes_preserve_pixels_and_vector_geometry(self):
        both, raster, vector = [decode(CAPTURES[k].read_bytes()) for k in ('raster-and-vector', 'raster-only', 'vector-only')]
        self.assertEqual(both['rasters'][0], raster['rasters'][0])
        self.assertEqual(both['vector_paths'], vector['vector_paths'])
        self.assertEqual(raster['vector_paths'], [])
        self.assertEqual(vector['rasters'], [])

    @unittest.skipUnless(Path('captures/capture-14978-28204/jbs/Convert/Default.jbs').is_file(), 'Private original multi-raster reference required')
    def test_original_large_multi_picture_job_matches_independent_xp_conversion(self):
        root=Path('captures/capture-14978-28204/jbs')
        raw=decode((root/'Default.jbs').read_bytes())
        cg=decode((root/'Convert/Default.jbs').read_bytes())
        self.assertEqual(len(raw['rasters']),2)
        self.assertEqual(len(raw['vector_paths']),23)
        self.assertEqual(raw['commands'],cg['commands'])
        self.assertEqual(raw['vector_paths'],cg['vector_paths'])
        expected=((3731,554,'9022ba89ae1fbb786ad171b27b2e64370d2953ff59a04d0c1aa1f94ce194dee9'),
                  (3202,578,'85b5e92e37bfdb3c7de3b672076576541c42737efb8cced084e2db8533819ae2'))
        for a,b,(w,h,digest) in zip(raw['rasters'],cg['rasters'],expected):
            self.assertEqual((a['width'],a['height'],a['pixels_sha256']),(w,h,digest))
            self.assertEqual(a['pixels'],b['pixels'])
            self.assertEqual(a['origin_units'],b['origin_units'])
            self.assertEqual(a['resolution_dpi'],b['resolution_dpi'])


class PreferenceSampleTests(unittest.TestCase):
    def test_bmp_rows_padding_dpi_and_png_samples_are_independent_and_exact(self):
        # Odd width needs three padding bytes; the BMP's first stored row is bottom.
        pixels = bytes([255, 128, 0, 16, 32, 64])
        bitmap = bmp24(3, 2, pixels)
        self.assertEqual(bitmap[:2], b'BM')
        self.assertEqual(struct.unpack_from('<I', bitmap, 2)[0], len(bitmap))
        self.assertEqual(struct.unpack_from('<ii', bitmap, 18), (3, 2))
        self.assertEqual(struct.unpack_from('<ii', bitmap, 38), (6575, 6575))
        self.assertEqual(bitmap[54:66], b'\x10'*3+b'\x20'*3+b'\x40'*3+b'\0'*3)
        image = png_gray(3, 2, pixels)
        cursor = 8; compressed = bytearray()
        while cursor < len(image):
            size, = struct.unpack_from('>I', image, cursor)
            kind, body = image[cursor+4:cursor+8], image[cursor+8:cursor+8+size]
            if kind == b'IDAT': compressed.extend(body)
            self.assertEqual(zlib.crc32(kind+body), struct.unpack_from('>I', image, cursor+8+size)[0])
            cursor += size+12
        self.assertEqual(zlib.decompress(compressed), b'\0\xff\x80\0\0\x10\x20\x40')

    def test_sample_distinguishes_all_flips_and_inversion_and_bundle_cannot_overwrite(self):
        w, h, pixels = sample()
        raster = {'width': w, 'height': h, 'pixels': pixels}
        self.assertEqual(pixel_matches(raster, raster)['pixel_transform_matches'], ['identity'])
        self.assertEqual(sorted(set(pixels)), [0, 64, 96, 128, 160, 192, 224, 255])
        with tempfile.TemporaryDirectory() as temp, patch('socket.socket') as sock:
            out = Path(temp)/'sample'
            result = create(out)
            self.assertFalse(result['xp_reference_captured'])
            self.assertFalse(result['physical_device_io_performed'])
            for label in ('baseline', 'invert', 'bottom-up'):
                script = (out/f'xp-reference-collect-bitmap-{label}.cmd').read_bytes()
                self.assertIn(f'requested_bitmap_case={label}'.encode(), script)
                self.assertIn(f'bitmap-{label}-%RANDOM%-%RANDOM%'.encode(), script)
                self.assertEqual(script.replace(b'\r\n', b'').find(b'\n'), -1)
                self.assertNotIn(b'del ', script.lower())
            with self.assertRaises(FileExistsError): create(out)
            sock.assert_not_called()


if __name__ == '__main__':
    unittest.main()
