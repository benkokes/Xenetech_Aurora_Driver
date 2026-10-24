"""Raster masks and serializers checked against four actual XP captures."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from aurora_jobserver.color_settings import ColorProcess
from aurora_jobserver.color_rasters import (ExposureSurface,FlatColorSurface,RasterPlan,RasterRegion,
    plan_color_rasters,plan_global_rasters,encode_raster_draft)
from aurora_jobserver.jbs import DRAFT_MARKER,prepare
from aurora_jobserver.wire import raster_plan
from tools.build_color_raster_review import REFERENCES,reference_palette,reference_surface,build
from tools.compare_preference_jobs import decode


ROOT=Path(__file__).resolve().parents[1]
XP=ROOT/'captures/xp-color-raster-preferences-20261019'


def surface(colors):
    return FlatColorSurface(10,20,len(colors),1,
        b''.join(bytes(((rgb>>16)&255,(rgb>>8)&255,rgb&255)) for rgb in colors),b'\xff'*len(colors))


class ColorRasterTests(unittest.TestCase):
    def test_color_groups_crop_combine_and_omit_unknown_without_mutating_input(self):
        source=reference_surface();palette=reference_palette()
        before=repr((source,palette))
        plan=plan_color_rasters(source,palette)
        self.assertEqual([r.color_index for r in plan.regions],[0,1,9])
        self.assertEqual(plan.unmatched_pixels,441)
        self.assertEqual([(r.image.x_pixels,r.image.y_pixels,r.image.width,r.image.height)
                          for r in plan.regions],[(161,163,21,21),(244,246,188,21),(161,246,188,21)])
        for region in plan.regions[1:]:
            self.assertEqual(region.image.pixels,(b'\xff'*21+b'\0'*146+b'\xff'*21)*21)
        self.assertEqual(repr((source,palette)),before)

    def test_disabled_zero_power_fractional_and_pause_combinations(self):
        source=reference_surface()
        for change in ({'Enabled':False},{'PowerPercent':'0'}):
            table=reference_palette();table[9].update(change)
            self.assertEqual([r.color_index for r in plan_color_rasters(source,table).regions],[0,1])
            with self.assertRaisesRegex(ValueError,'independent XP evidence'):
                plan_color_rasters(source,table,pause_colors=True)
        table=reference_palette();table[1]['PowerPercent']='11.25'
        with self.assertRaisesRegex(ValueError,'Fractional color power'):
            plan_color_rasters(source,table)
        for source in (surface((0xff8000,)),replace(surface((0,)),coverage=b'\0')):
            with self.assertRaisesRegex(ValueError,'No enabled matched'):
                plan_color_rasters(source,reference_palette())

    def test_invalid_buffers_bounds_partial_coverage_and_unverified_vertical_regions(self):
        source=surface((0,0xff0000))
        cases=(replace(source,rgb=b'\0'),replace(source,coverage=b'\xff'),
               replace(source,coverage=b'\xff\x80'),replace(source,width=True),
               replace(source,x_pixels=-1),replace(source,x_pixels=5009),
               replace(source,rgb=bytearray(source.rgb)))
        for index,bad in enumerate(cases):
            with self.subTest(case=index),self.assertRaises(ValueError):
                plan_color_rasters(bad,reference_palette())
        separated=FlatColorSurface(0,0,1,3,b'\0'*9,b'\xff\0\xff')
        with self.assertRaisesRegex(ValueError,'Multiple vertical regions'):
            plan_color_rasters(separated,reference_palette())
        with self.assertRaisesRegex(ValueError,'explicit boolean'):
            plan_color_rasters(source,reference_palette(),pause_colors=1)

    def test_global_bands_preserve_gray_samples_offsets_and_serpentine_order(self):
        source=ExposureSurface(10,20,4,4,bytes((0,10,20,0, 0,0,30,0, 0,0,0,0, 40,0,0,0)))
        plan=plan_global_rasters(source,ColorProcess(30000,45,1000))
        self.assertEqual([(r.image.x_pixels,r.image.y_pixels,r.image.width,r.image.height)
                          for r in plan.regions],[(11,20,2,2),(10,23,1,1)])
        self.assertEqual(plan.regions[0].image.pixels,bytes((10,20,0,30)))
        raw,cg=encode_raster_draft(plan)
        for data in (raw,cg):
            rasters=decode(data)['rasters']
            self.assertEqual(rasters[0]['pixels'],bytes((10,20,0,30)))
            self.assertEqual(rasters[1]['pixels'],b'\x28')
        self.assertEqual(raw.count(b'30000. speed\r'),1)
        self.assertNotIn(b'set_vppi',raw)
        with self.assertRaisesRegex(ValueError,'No raster exposure'):
            plan_global_rasters(replace(source,pixels=b'\0'*16),ColorProcess(30000,45,1000))

    def test_pauses_use_color_identity_cache_fields_and_track_footer_pen_up(self):
        table=reference_palette();table[9].update(SpeedIps='1',PowerPercent='11')
        plan=plan_color_rasters(surface((0x0000ff,0xff0000)),table,pause_colors=True)
        raw,cg=encode_raster_draft(plan)
        self.assertEqual(raw.count(b'1000. speed\r'),1)
        self.assertEqual(raw.count(b'11.00 power\r'),1)
        self.assertEqual(decode(raw)['commands'].count('PAUSE'),1)
        self.assertIn(b'PU\r0. 0. V\rPAUSE\r',raw)
        self.assertFalse(raw.endswith(b'PU\r0. 0. V\rEND_PLOT\r'))
        single,_=encode_raster_draft(plan_color_rasters(surface((0xff0000,)),table,pause_colors=True))
        self.assertEqual(decode(single)['commands'].count('PAUSE'),0)
        self.assertTrue(single.endswith(b'PU\r0. 0. V\rEND_PLOT\r'))
        self.assertEqual(decode(raw)['commands'],decode(cg)['commands'])

    def test_drafts_never_prepare_or_plan_for_delivery_and_titles_cannot_inject(self):
        with patch('socket.socket') as network:
            plan=plan_color_rasters(reference_surface(),reference_palette(),pause_colors=True)
            for data in encode_raster_draft(plan):
                self.assertTrue(data.startswith(b'!ZX\r'+DRAFT_MARKER+b'\r'))
                self.assertFalse(prepare(data,allow_draft=True).auto_start)
                with self.assertRaisesRegex(ValueError,'uncalibrated draft'):prepare(data)
                with self.assertRaisesRegex(ValueError,'uncalibrated draft'):
                    raster_plan(data,r'c:\xfiles\jbs\Convert\Default.jbs')
            for title in ('Bad\rautostart START','a'*65,''):
                with self.assertRaisesRegex(ValueError,'title'):encode_raster_draft(plan,title)
            network.assert_not_called()

    def test_manually_constructed_plans_still_validate(self):
        plan=plan_color_rasters(surface((0,0xff0000)),reference_palette())
        bad=(replace(plan,regions=()),replace(plan,pause_colors=1),
             replace(plan,regions=plan.regions[::-1]),replace(plan,color_mode=False),
             replace(plan,regions=(replace(plan.regions[0],process=ColorProcess(1,101,1000)),)),
             replace(plan,regions=(replace(plan.regions[0],image=ExposureSurface(0,0,1,1,b'\x01')),)))
        for case in bad:
            with self.assertRaises(ValueError):encode_raster_draft(case)


@unittest.skipUnless(all((XP/folder/'inbox/Default.jbs').is_file() for folder,_ in REFERENCES.values()),
                     'Private XP raster color references required')
class XpColorRasterTests(unittest.TestCase):
    def test_four_complete_raw_jobs_and_cg_output_match_independent_xp_evidence(self):
        with tempfile.TemporaryDirectory() as temp,patch('socket.socket') as network:
            root=Path(temp)/'review'
            report=build(XP,root)
            self.assertEqual(len(report['cases']),4)
            self.assertTrue(all(c['complete_raw_matches_xp_except_draft_marker'] for c in report['cases']))
            self.assertEqual([c['raster_count'] for c in report['cases']],[2,3,3,2])
            self.assertEqual([c['unmatched_pixels'] for c in report['cases']],[0,441,441,441])
            self.assertEqual(len(list(root.glob('*.jbs.draft'))),8)
            with self.assertRaisesRegex(ValueError,'fresh review directory'):build(XP,root)
            network.assert_not_called()
