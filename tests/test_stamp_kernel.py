from fractions import Fraction
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.inspect_stamp_kernel import binary32, edge_table, narrow_gap_table, gray_edge_table, inspect


ROOT=Path(__file__).resolve().parents[1]
CONVERTER=ROOT/'analysis/extracted/tools-suite/BmpPict2/bmppict2.dll'
REGISTRY=ROOT/'analysis/extracted/laser-driver/NewWorld_Files/XGWRegistry.dll'


class StampLookupTests(unittest.TestCase):
    def test_binary32_exact_ties_use_even_significand_without_binary64_intermediate(self):
        self.assertEqual(binary32(1+Fraction(1,2**24)),1)
        self.assertEqual(binary32(1+Fraction(3,2**24)),1+Fraction(1,2**22))
        self.assertEqual(binary32(-1-Fraction(1,2**24)),-1)
        self.assertEqual(binary32(0),0)
        self.assertEqual(binary32(255),255)
        self.assertEqual(binary32(Fraction(1,10)),Fraction(13421773,134217728))

    def test_hand_calculated_tables_preserve_split_rounding_and_narrow_gap_centers(self):
        self.assertEqual(edge_table(3,1,60),[153,187,221])
        self.assertEqual(edge_table(5,2,30),[38,76,121,165,210])
        self.assertEqual(edge_table(2,0,0),[85,170])
        self.assertEqual(edge_table(2,0,100),[85,170])
        self.assertEqual(edge_table(1,1,100),[255])
        self.assertEqual(narrow_gap_table(5,2,30,1),[76])
        self.assertEqual(narrow_gap_table(5,2,30,2),[76,76])
        self.assertEqual(narrow_gap_table(5,2,30,3),[38,76,38])

    def test_bounds_reject_unsupported_or_unbounded_model_inputs(self):
        for args in ((0,0,0),(65,1,50),(3,4,50),(3,-1,50),(3,1,101),(3,1,-1),(True,1,50)):
            with self.subTest(args=args),self.assertRaises(ValueError):edge_table(*args)
        for width in (0,4,5,True):
            with self.subTest(width=width),self.assertRaises(ValueError):narrow_gap_table(5,2,30,width)

    def test_gray_sources_shorten_the_edge_table_with_strict_comparison(self):
        self.assertEqual(gray_edge_table(3,1,60,0),[153,187,221])
        self.assertEqual(gray_edge_table(3,1,60,153),[187,221])
        self.assertEqual(gray_edge_table(3,1,60,187),[221])
        self.assertEqual(gray_edge_table(3,1,60,221),[])
        self.assertIsNone(gray_edge_table(3,1,60,255))
        self.assertEqual(gray_edge_table(3,1,0,0),[0,85,170])
        self.assertEqual(gray_edge_table(3,1,0,1),[85,170])
        for value in (-1,256,True):
            with self.assertRaises(ValueError):gray_edge_table(3,1,60,value)

    @unittest.skipUnless(CONVERTER.is_file() and REGISTRY.is_file(),'Private archived sources unavailable')
    def test_all_profile_predictions_are_bounded_and_feature_remains_held(self):
        with patch('socket.socket') as socket:
            report=inspect(CONVERTER,REGISTRY)
            self.assertEqual(len(report['profiles']),45)
            self.assertEqual(sum(len(p['narrow_gaps']) for p in report['profiles']),301)
            for profile in report['profiles']:
                edge=profile['edge_samples']
                self.assertEqual(len(edge),profile['parameters'][0])
                self.assertEqual(edge,sorted(edge))
                for gap in profile['narrow_gaps']:
                    samples=gap['samples']
                    self.assertEqual(len(samples),gap['width'])
                    self.assertLessEqual(max(abs(a-b) for a,b in zip(samples,reversed(samples))),1)
                self.assertTrue(all(0<=v<=255 for v in edge))
            self.assertFalse(report['full_stamp_filter_implemented'])
            self.assertFalse(report['production_feature_hold_removed'])
            self.assertFalse(report['vendor_code_executed'])
            socket.assert_not_called()
        with tempfile.TemporaryDirectory() as temp:
            wrong=Path(temp)/'converter.dll';wrong.write_bytes(b'wrong version')
            with self.assertRaisesRegex(ValueError,'archived BmpPict2'):inspect(wrong,REGISTRY)


if __name__=='__main__':unittest.main()
