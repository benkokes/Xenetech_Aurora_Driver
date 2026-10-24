"""Offline color command model checked against independently captured XP jobs."""
import copy
from dataclasses import replace
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

from aurora_jobserver.artwork import Scene, ProcessSettings, encode
from aurora_jobserver.classic_settings import parse, carriers, decode as decode_settings
from aurora_jobserver.color_vectors import plan_vectors
from aurora_jobserver.jbs import DRAFT_MARKER, prepare
from aurora_jobserver.print_pipeline import encode_print
from aurora_jobserver.wire import raster_plan
from tests.test_classic_settings import payload
from tests.test_output_modes import PROCESS
from tools.compare_preference_jobs import decode


ROOT = Path(__file__).resolve().parents[1]
XP = ROOT / 'captures/xp-color-preferences-20261019'
REFERENCES = {
    'global': ('color-global-2505-1735', 'e63a9df9789326f320e4b5fb9c8bc3b0cd4d20acd5ca9220c5667c628e1d6d27'),
    'unsorted': ('color-unsorted-26428-17920', 'eb7d974ea341e7567a4cce65a92bea5043a5fffe52cb85d317008c42fcef36d2'),
    'sorted': ('color-sorted-22009-23343', '9e466d446e155b429f006affb8726a5e5fc56da873129e0215438c2362bbcaca'),
    'paused': ('color-paused-15968-17857', '5b6bd3265ec1390e7b681c6eb05a3ae5a02ea3a1c21d9acf1e1aabe60fb556be'),
    'disabled-blue': ('color-disabled-blue-16495-29410', '230f87f9dedd076bd83cce2bcda6a9767c7831466a5afea188ab86710355bfcc'),
}
COLORS = (0x0000ff, 0xff0000, 0x0000ff, 0xff0000, 0xff8000)
FOOTER = b'PU\r0. 0. V\rEND_PLOT\r'


def palette():
    result = parse(payload())['Colors']
    for index, power, speed, ppi in ((0, 45, 30, 1000), (1, 11, 1, 500), (9, 22, 2, 750)):
        result[index].update(PowerPercent=str(power), SpeedIps=str(speed), Ppi=ppi)
    return result


class ColorVectorTests(unittest.TestCase):
    def test_sort_reverses_equal_colors_caches_fields_and_does_not_mutate_input(self):
        paths = tuple(((n, 0), (n, 1)) for n in range(5))
        table = palette()
        original = copy.deepcopy((paths, COLORS, table))
        plan = plan_vectors(paths, COLORS, table, sort_colors=True, pause_colors=True)
        self.assertEqual([p.source_index for p in plan.paths], [3, 1, 2, 0, 4])
        self.assertEqual(plan.commands.count(b' speed\r'), 3)
        self.assertEqual(plan.commands.count(b' power\r'), 3)
        self.assertEqual(plan.commands.count(b' set_vppi\r'), 3)
        self.assertEqual(plan.commands.count(b'PAUSE\r'), 2)
        self.assertEqual((paths, COLORS, table), original)

    def test_cache_is_per_process_field_and_pause_is_per_color_identity(self):
        table = palette()
        table[9].update(PowerPercent='11', SpeedIps='1', Ppi=750)
        plan = plan_vectors((((0,0),(1,1)), ((2,2),(3,3))), (0xff0000,0x0000ff), table, pause_colors=True)
        self.assertEqual(plan.commands.count(b' speed\r'), 1)
        self.assertEqual(plan.commands.count(b' power\r'), 1)
        self.assertEqual(plan.commands.count(b' set_vppi\r'), 2)
        self.assertEqual(plan.commands.count(b'PAUSE\r'), 1)

    def test_unknown_lookup_keeps_sentinel_for_order_and_uses_white_process(self):
        paths = (((0,0),(1,1)), ((2,2),(3,3)))
        plan = plan_vectors(paths, (0xff8000,0xffffff), palette(), sort_colors=True)
        self.assertEqual([p.color_index for p in plan.paths], [15,16])
        self.assertEqual([p.palette_index for p in plan.paths], [15,15])
        self.assertEqual([p.process.speed_native for p in plan.paths], [100000,100000])
        self.assertEqual(plan.commands.count(b' speed\r'), 1)

    def test_disabled_zero_power_and_unverified_combinations(self):
        paths = (((0,0),(1,1)), ((2,2),(3,3)))
        for change in ({'Enabled':False}, {'PowerPercent':'0'}):
            table = palette(); table[9].update(change)
            plan = plan_vectors(paths, (0x0000ff,0xff0000), table)
            self.assertEqual([p.source_index for p in plan.paths], [1])
            with self.assertRaisesRegex(ValueError, 'independent XP evidence'):
                plan_vectors(paths, (0x0000ff,0xff0000), table, pause_colors=True)
        table = palette(); table[1]['PowerPercent']='11.5'
        with self.assertRaisesRegex(ValueError, 'Fractional color power'):
            plan_vectors(paths, (0x0000ff,0xff0000), table)
        table = palette(); table[9]['Enabled']=False
        self.assertEqual(plan_vectors((paths[0],), (0x0000ff,), table).commands, b'')

    def test_invalid_inputs_fail_before_emitting_commands(self):
        paths = (((0,0),(1,1)),)
        cases = [([], COLORS, palette(), {}), (paths, (True,), palette(), {}),
                 (paths, (0xff000000,), palette(), {}), (paths,(0,),palette(),{'sort_colors':1}),
                 ((((0,0),(float('nan'),1)),),(0,),palette(),{}),
                 ((((0,0),(.01,1)),),(0,),palette(),{}),
                 ((((0,0),(0,0)),),(0,),palette(),{})]
        for index, (p, c, table, options) in enumerate(cases):
            with self.subTest(case=index), self.assertRaises(ValueError):
                plan_vectors(p,c,table,**options)
        for key,value in (('Enabled',1),('SpeedIps','NaN'),('SpeedIps','150.001'),
                          ('Ppi',True),('R',1),('PowerPercent','101')):
            table=palette();table[0][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                plan_vectors(paths,(0,),table)

    def test_explicit_color_optout_holds_before_encoding(self):
        value = payload(UseColors=True)
        settings = decode_settings(carriers(parse(value)),value)
        with patch('aurora_jobserver.print_pipeline._encode') as encoder:
            with self.assertRaisesRegex(ValueError, 'Print held:'):
                encode_print(None, settings, 'Held',allow_color_rasters=False)
            encoder.assert_not_called()


@unittest.skipUnless(all((XP/folder/'inbox/Default.jbs').is_file() for folder,_ in REFERENCES.values()),
                     'Private XP color captures required')
class XpColorVectorTests(unittest.TestCase):
    def test_complete_jobs_match_all_five_independent_xp_files(self):
        refs={}
        for name,(folder,digest) in REFERENCES.items():
            data=(XP/folder/'inbox/Default.jbs').read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(),digest)
            refs[name]=data
        baseline=decode(refs['global'])
        raster=baseline['rasters'][0]
        scene=Scene({'dpi':167}, {'exposure':{'width':raster['width'],'height':raster['height'],
            'x_pixels':int(raster['origin_units'][0]/6), 'y_pixels':int(raster['origin_units'][1]/6)}},
            raster['pixels'],tuple(tuple(tuple(point) for point in p['points']) for p in baseline['vector_paths']))
        process=ProcessSettings.parse(PROCESS)
        with patch('socket.socket') as network:
            global_raw,_=encode(scene,process,'Default.jbs')
            self.assertEqual(global_raw.replace(DRAFT_MARKER+b'\r',b'',1),refs['global'])
            prefix,_=encode(replace(scene,paths=()),process,'Default.jbs',output_mode='raster-only')
            self.assertTrue(prefix.endswith(FOOTER))
            for name in ('unsorted','sorted','paused','disabled-blue'):
                with self.subTest(case=name):
                    table=palette()
                    if name=='disabled-blue':table[9]['Enabled']=False
                    plan=plan_vectors(scene.paths,COLORS,table,sort_colors=name!='unsorted',pause_colors=name=='paused')
                    draft=prefix[:-len(FOOTER)]+plan.commands+b'0. 0. V\rEND_PLOT\r'
                    self.assertEqual(draft.replace(DRAFT_MARKER+b'\r',b'',1),refs[name])
                    cg=prepare(draft,allow_draft=True).data
                    converted=decode(cg)
                    self.assertEqual(converted['vector_paths'],decode(refs[name])['vector_paths'])
                    for field in ('pixels','width','height','origin_units','origin_label',
                                  'resolution_dpi','settings'):
                        self.assertEqual(converted['rasters'][0][field],raster[field])
                    for data in (draft,cg):
                        with self.assertRaisesRegex(ValueError, 'uncalibrated draft'):prepare(data)
                        with self.assertRaisesRegex(ValueError, 'uncalibrated draft'):
                            raster_plan(data,r'c:\xfiles\jbs\Convert\Default.jbs')
            network.assert_not_called()
