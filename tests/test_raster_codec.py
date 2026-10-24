"""External-capture regression and boundary checks for the offline codec."""
from pathlib import Path
import random
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from convert_job import convert
from raster_codec import compress7, decompress7, pack7, unpack7


class PackingTests(unittest.TestCase):
    def test_observed_header_values(self):
        self.assertEqual(unpack7(bytes.fromhex("131d0000")), 3731)
        self.assertEqual(unpack7(bytes.fromhex("2a040000")), 554)
        self.assertEqual(unpack7(bytes.fromhex("58180a00")), 167000)
        self.assertEqual(unpack7(bytes.fromhex("4101")), 0xc1)
        self.assertEqual(pack7(3731, 4), bytes.fromhex("131d0000"))

    def test_high_bit_rejected(self):
        with self.assertRaisesRegex(ValueError, "High bit"):
            unpack7(b"\x80\x00")
        with self.assertRaises(ValueError):
            pack7(1 << 28, 4)


class CompressionTests(unittest.TestCase):
    def test_dictionary_boundaries_and_resets(self):
        # Incompressible data forces multiple 9/10/11/12-bit transitions and
        # dictionary clears. The captured-job test below supplies an independent
        # reference to avoid depending only on our compressor/decoder agreement.
        source = random.Random(42).randbytes(100_000)
        encoded = compress7(source)
        decoded, consumed, counters = decompress7(encoded, max_output=len(source))
        self.assertEqual(decoded, source)
        self.assertEqual(consumed, len(encoded))
        self.assertGreater(counters["dictionary_resets"], 10)
        self.assertTrue(all(value < 128 for value in encoded))

    def test_truncation_and_output_limit(self):
        encoded = compress7(b"A" * 10_000)
        with self.assertRaisesRegex(ValueError, "Truncated"):
            decompress7(encoded[:-1])
        with self.assertRaisesRegex(ValueError, "output limit"):
            decompress7(encoded, max_output=100)

    @unittest.skipUnless((ROOT / "captures/capture-14978-28204/jbs/Default.jbs").exists(),
                         "Private captured reference job is not present")
    def test_byte_exact_match_to_xp_jobserver(self):
        source = (ROOT / "captures/capture-14978-28204/jbs/Default.jbs").read_bytes()
        reference = (ROOT / "captures/capture-14978-28204/jbs/Convert/Default.jbs").read_bytes()
        converted, count = convert(source)
        self.assertEqual(count, 2)
        self.assertEqual(len(converted), 92759)
        self.assertEqual(converted, reference)


if __name__ == "__main__":
    unittest.main()
