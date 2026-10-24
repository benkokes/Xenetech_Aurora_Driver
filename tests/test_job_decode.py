"""Check decoding against explicit bytes, including malformed row boundaries."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from inspect_job import inspect


class RawRasterTests(unittest.TestCase):
    def sample(self):
        # Expected image in scan order is [0,1,2] then [3,4,5]. Odd rows are
        # transmitted in reverse. The last two bytes of each row are 00 FF.
        return (b"!ZX\rPICT-UL\r" + struct.pack("<HIIIIH", 0x58C3, 3, 2, 167, 167, 0x41)
                + b"\x00\x01\x02\x00\xff\x05\x04\x03\x00\xffEND_PLOT\r")

    def test_explicit_pixel_order_and_footer(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            source = output / "fixture.jbs"
            source.write_bytes(self.sample())
            result = inspect(source, output)
            image = output / "fixture-raster-01.pgm"
            self.assertEqual(image.read_bytes(), b"P5\n3 2\n255\n\xff\xfe\xfd\xfc\xfb\xfa")
            self.assertEqual(result["text_segments"][-1]["text"], "END_PLOT\r")
            self.assertEqual(result["rasters"][0]["rows_with_valid_trailers"], 2)

    def test_corrupted_row_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            source = output / "broken.jbs"
            source.write_bytes(self.sample().replace(b"\x05\x04\x03\x00\xff", b"\x05\x04\x03\x00\xfe"))
            with self.assertRaisesRegex(ValueError, "Invalid row trailer"):
                inspect(source, output)
            self.assertFalse(list(output.glob("*.pgm")))

    def test_truncated_payload_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            source = output / "short.jbs"
            source.write_bytes(self.sample()[:33])
            with self.assertRaisesRegex(ValueError, "Truncated raster"):
                inspect(source, output)


if __name__ == "__main__":
    unittest.main()
