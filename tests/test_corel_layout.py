"""Expected corners from actual 100/167-DPI XP captures, not fitted offsets."""
import copy
import struct
import unittest

from aurora_jobserver.corel_layout import COREL_GRID, CorelLayout
from aurora_jobserver.artwork import encode, load_scene, ProcessSettings
from aurora_jobserver.jbs import prepare
from tests import test_artwork as fixture_module


# X7 OpenXPS coordinates of the unchanged one-inch square. Expected outputs
# below were read independently from the two owner's raw XP reference jobs.
POINTS = [[23.071665859222414,31.242000484466555], [48.471665859222412,31.242000484466555],
          [48.471665859222412,56.642000484466557], [23.071665859222414,56.642000484466557]]
EXPECTED = {100:[[900,1220],[1900,1220],[1900,2220],[900,2220]],
            167:[[876,1212],[1878,1212],[1878,2214],[876,2214]]}


class CorelPlacementTests(unittest.TestCase):
    def test_all_corners_match_both_independent_xp_references(self):
        for dpi in (100,167):
            layout = CorelLayout(dpi)
            points = [[int(layout.point(x,0)),int(layout.point(y,1))] for x,y in POINTS]
            self.assertEqual(points, EXPECTED[dpi])

    def test_supported_modes_and_surface_edges_are_bounded(self):
        for dpi, source in [(333,600),(167,1200),(True,600),(100,True)]:
            with self.assertRaises(ValueError):
                CorelLayout(dpi,source)
        for point in (0,762.1):
            with self.assertRaisesRegex(ValueError,'outside'):
                CorelLayout(167).point(point,0)

    def test_encoded_profiles_keep_raster_dpi_pitch_and_draft_guard(self):
        # Reuse only fixture setup/cleanup, without inheriting its test cases.
        fixture = fixture_module.ArtworkTests(); fixture.setUp()
        try:
            original = copy.deepcopy(fixture.doc)
            for dpi in (100,167):
                fixture.doc = copy.deepcopy(original)
                doc = fixture.doc; doc.update(raster_grid=COREL_GRID,dpi=dpi,render_dpi=dpi)
                doc['corel_xp_compatibility'] = {'model':'coreldraw-x7-to-xp11-flatbed-v1',
                    'validation':'reference_fit_not_physical_calibration','source_printer_dpi':600,'target_dpi':dpi}
                page = doc['pages'][0]; layout = CorelLayout(dpi)
                page.update(width_mm=762,height_mm=457.2,pixel_width=layout.surface[0],pixel_height=layout.surface[1])
                page['cuts'][0]['points_mm'] = POINTS
                fixture.write(); scene = load_scene(fixture.intake)
                self.assertEqual(scene.geometry()['paths_units'][0][:-1],EXPECTED[dpi])
                raw, compressed = encode(scene,ProcessSettings.parse(fixture_module.SETTINGS))
                start=raw.index(b'PICT-UL\r')+8
                self.assertEqual(struct.unpack_from('<HIIIIH',raw,start),(0x58c3,3,2,dpi,dpi,0x41))
                self.assertIn(f'{layout.pitch:.3f} set_gspot\r'.encode(),raw)
                for data in (raw,compressed):
                    with self.assertRaisesRegex(ValueError,'uncalibrated draft'):
                        prepare(data)
                doc['corel_xp_compatibility']['source_printer_dpi']=1200
                fixture.write()
                with self.assertRaisesRegex(ValueError,'source 600'):
                    load_scene(fixture.intake)
                doc['corel_xp_compatibility']['source_printer_dpi']=600
                page['width_mm']=700
                fixture.write()
                with self.assertRaisesRegex(ValueError,'30 x 18'):
                    load_scene(fixture.intake)
        finally:
            fixture.tearDown()
