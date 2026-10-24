"""Review per-color vector composition without physical-device connections."""
import copy
from dataclasses import replace
import unittest
from unittest.mock import patch

from aurora_jobserver.artwork import ProcessSettings
from aurora_jobserver.classic_settings import parse
from aurora_jobserver.color_vector_job import encode_color_vector_draft, plan_scene_vectors
from aurora_jobserver.corel_layout import COREL_HAIRLINE_MAX_MM
from aurora_jobserver.direct_print import CONTROLLER_PATH
from aurora_jobserver.jbs import prepare
from aurora_jobserver.wire import raster_plan
from tests.test_classic_settings import payload
from tests.test_output_modes import sample, PROCESS
from tools.compare_preference_jobs import decode


def fixture():
    base = sample()
    paths = tuple(tuple((x+offset,y) for x,y in base.paths[0]) for offset in (0,2000,4000))
    cuts = [{'color':c,'width_mm':.0254} for c in ('#FF000000','#FFFF0000','#FF0000FF')]
    scene = replace(base, manifest=base.manifest | {'cut_color':'any',
                    'max_cut_width_mm':COREL_HAIRLINE_MAX_MM},
                    page=base.page | {'cuts':cuts}, paths=paths)
    table = parse(payload())['Colors']
    for index, speed, power, ppi in ((0,'1',15,1000),(1,'2',20,750),(9,'3',25,500)):
        table[index].update(SpeedIps=speed, PowerPercent=str(power), Ppi=ppi)
    return scene, table


class ColorVectorJobTests(unittest.TestCase):
    def test_three_hairline_colors_use_independent_processes_and_zero_carrier(self):
        scene, table = fixture()
        original_scene, original_table = copy.deepcopy(scene), copy.deepcopy(table)
        with patch('socket.socket') as network:
            raw, cg = encode_color_vector_draft(scene, ProcessSettings.parse(PROCESS), table)
            for data in (raw,cg):
                job = decode(data)
                self.assertTrue(job['draft'])
                self.assertFalse(job['autostart'])
                self.assertEqual(len(job['rasters']),1)
                self.assertEqual(job['rasters'][0]['pixels'],b'\0')
                self.assertEqual(job['rasters'][0]['settings']['power'],0)
                paths = job['vector_paths']
                self.assertEqual(len(paths),3)
                self.assertEqual([p['points'] for p in paths], [[list(p) for p in path] for path in scene.paths])
                for path, expected in zip(paths, ((1000,15,1000),(2000,20,750),(3000,25,500))):
                    self.assertEqual(tuple(path['settings'][k] for k in ('speed','power','set_vppi')),expected)
                with self.assertRaisesRegex(ValueError,'uncalibrated draft'):
                    prepare(data)
                with self.assertRaisesRegex(ValueError,'uncalibrated draft'):
                    raster_plan(data,CONTROLLER_PATH)
            network.assert_not_called()
        self.assertEqual(scene,original_scene)
        self.assertEqual(table,original_table)

    def test_disabled_and_zero_power_colors_skip_paths_and_empty_result(self):
        scene, table = fixture()
        table[1]['Enabled'] = False
        table[9]['PowerPercent'] = '0'
        raw, _ = encode_color_vector_draft(scene,ProcessSettings.parse(PROCESS),table)
        self.assertEqual(len(decode(raw)['vector_paths']),1)
        table[0]['Enabled'] = False
        with self.assertRaisesRegex(ValueError,'Nothing to cut'):
            encode_color_vector_draft(scene,ProcessSettings.parse(PROCESS),table)

    def test_malformed_identity_and_wider_strokes_are_rejected(self):
        scene, table = fixture()
        for color in ('#000000','#80000000',None,'#FFzzzzzz'):
            changed = copy.deepcopy(scene.page)
            changed['cuts'][0]['color'] = color
            with self.assertRaisesRegex(ValueError,'opaque RGB'):
                plan_scene_vectors(replace(scene,page=changed),table)
        for width in (.2,0,True,float('nan')):
            changed = copy.deepcopy(scene.page)
            changed['cuts'][0]['width_mm'] = width
            with self.assertRaisesRegex(ValueError,'hairline threshold'):
                plan_scene_vectors(replace(scene,page=changed),table)
        with self.assertRaisesRegex(ValueError,'one source color'):
            plan_scene_vectors(replace(scene,page=scene.page | {'cuts':[]}),table)

    def test_legacy_fast_color_speed_does_not_escape_review_limits(self):
        scene, table = fixture()
        # The unused legacy 100 ips palette entries are not motion commands.
        self.assertEqual(len(plan_scene_vectors(scene,table).paths),3)
        table[1]['SpeedIps'] = '100'
        with self.assertRaisesRegex(ValueError,'15 ips'):
            plan_scene_vectors(scene,table)

    def test_unknown_color_uses_original_white_fallback(self):
        scene, table = fixture()
        changed = copy.deepcopy(scene.page)
        changed['cuts'][1]['color'] = '#FFFF8000'
        table[15].update(SpeedIps='4',PowerPercent='10',Ppi=250)
        plan = plan_scene_vectors(replace(scene,page=changed),table)
        self.assertEqual(plan.paths[1].color_index,16)
        self.assertEqual(plan.paths[1].palette_index,15)
        self.assertEqual(plan.paths[1].process.speed_native,4000)


if __name__ == '__main__':
    unittest.main()
