"""Independent XP bitmap references plus native conversion and loopback only."""
import copy
from dataclasses import replace
from pathlib import Path
import socket
import tempfile
import unittest
import uuid
from unittest.mock import patch

from aurora_jobserver.artwork import Scene, ProcessSettings, encode, load_scene
from aurora_jobserver.classic_settings import carriers, decode as decode_classic, parse
from aurora_jobserver.direct_print import DirectPrintBridge, CONTROLLER_PATH
from aurora_jobserver.jbs import prepare
from aurora_jobserver.print_pipeline import encode_print, prepare_capture
from aurora_jobserver.store import JobStore
from aurora_jobserver.wire import raster_plan
from tests.test_classic_settings import payload
from tests.test_output_modes import PROCESS, sample, full_document
from tests.test_print_pipeline import CAPTURE, INTAKE, CHECKED, FAST, capture_document
from tools.compare_preference_jobs import decode
from tools.controller_simulator import ControllerSimulator


ROOT=Path(__file__).resolve().parents[1]
XP=ROOT/'captures/xp-bitmap-preferences-20261019'
REFERENCES={
    (False,False):XP/'bitmap-baseline-13084-7847/inbox/Default.jbs',
    # Original collector name is preserved; owner's correction identifies Invert On.
    (True,False):XP/'bitmap-baseline-7794-27967/inbox/Default.jbs',
    (False,True):XP/'bitmap-bottom-up-26829-22394/inbox/Default.jbs',
}


def settings(invert=False,bottom=False,**changes):
    encoded=payload(InvertRaster=invert,BottomUp=bottom,**changes)
    return decode_classic(carriers(parse(encoded)),encoded)


def reference_scene():
    baseline=decode(REFERENCES[False,False].read_bytes())
    raster=baseline['rasters'][0]
    x,y=raster['origin_units']
    return Scene({'dpi':167,'raster_grid':'coreldraw-xp-draft','text_rendering':'outline-aliased'},
        {'exposure':{'width':raster['width'],'height':raster['height'],
                     'x_pixels':int(x/6),'y_pixels':int(y/6)}},raster['pixels'],())


class RasterPreferenceTests(unittest.TestCase):
    def test_flags_preserve_scene_paths_process_settings_and_rectangle(self):
        source=sample();original=copy.deepcopy(source)
        expected={
            (False,False):b'\0\x80\xff\x01\x02\x03',
            (True,False):b'\xff\x7f\0\xfe\xfd\xfc',
            (False,True):b'\x01\x02\x03\0\x80\xff',
            (True,True):b'\xfe\xfd\xfc\xff\x7f\0',
        }
        for (invert,bottom),pixels in expected.items():
            with self.subTest(invert=invert,bottom=bottom),patch('socket.socket') as network:
                s=settings(invert,bottom)
                self.assertEqual(s['held_features'],[])
                raw,cg=encode_print(source,s,'Flags')
                a,b=decode(raw),decode(cg)
                self.assertEqual(a['rasters'][0]['pixels'],pixels)
                self.assertEqual(b['rasters'][0]['pixels'],pixels)
                self.assertEqual(a['rasters'][0]['origin_label'],'LL' if bottom else 'UL')
                self.assertEqual(a['rasters'][0]['origin_units'],[60,126 if bottom else 120])
                self.assertEqual(a['vector_paths'][0]['points'],[list(p) for p in source.paths[0]])
                self.assertEqual(a['rasters'][0]['settings']['power'],45)
                self.assertFalse(a['autostart'])
                network.assert_not_called()
        self.assertEqual(source,original)

    def test_odd_and_single_row_bottom_origins_have_no_extra_row(self):
        for height in (1,3):
            source=replace(sample(),page={'exposure':{'width':3,'height':height,'x_pixels':10,'y_pixels':20}},
                           exposure=bytes(range(height*3)))
            raw,_=encode_print(source,settings(False,True),'Rows')
            raster=decode(raw)['rasters'][0]
            expected=b''.join(bytes(range(y*3,y*3+3)) for y in range(height-1,-1,-1))
            self.assertEqual(raster['pixels'],expected)
            self.assertEqual(raster['origin_units'],[60,(20+height-1)*6])

    def test_other_dpi_and_other_unverified_features_remain_held(self):
        for invert,bottom in ((True,False),(False,True),(True,True)):
            s=settings(invert,bottom,Resolution=100)
            with patch('aurora_jobserver.print_pipeline._encode') as encoder:
                with self.assertRaisesRegex(ValueError,'Print held:'):encode_print(None,s,'Held')
                encoder.assert_not_called()
        for changes in ({'Orientation':'Right90'},{'Mirror':True},{'DitherBitmaps':True},{'UseColors':True}):
            with self.subTest(changes=changes),self.assertRaisesRegex(ValueError,'Print held:'):
                encode_print(None,settings(True,True,**changes),'Held')
        low=replace(sample(),manifest=sample().manifest|{'dpi':100})
        with self.assertRaisesRegex(ValueError,'only at 167'):encode(low,ProcessSettings.parse(PROCESS),bottom_up=True)
        with self.assertRaisesRegex(ValueError,'explicit booleans'):encode(sample(),ProcessSettings.parse(PROCESS),invert_raster=1)

    def test_draft_marker_remains_effective_with_both_raster_options(self):
        raw,cg=encode(sample(),ProcessSettings.parse(PROCESS),invert_raster=True,bottom_up=True)
        self.assertEqual(prepare(cg,allow_draft=True).rasters,1)
        for data in (raw,cg):
            with self.assertRaisesRegex(ValueError,'uncalibrated draft'):raster_plan(data,CONTROLLER_PATH)


@unittest.skipUnless(all(p.is_file() for p in REFERENCES.values()),'Private XP bitmap references required')
class XpRasterPreferenceTests(unittest.TestCase):
    def test_three_complete_raw_jobs_match_independent_xp_files_byte_for_byte(self):
        scene=reference_scene()
        for (invert,bottom),source in REFERENCES.items():
            with self.subTest(invert=invert,bottom=bottom),patch('socket.socket') as network:
                raw,cg=encode_print(scene,settings(invert,bottom,Output='RasterOnly'),'Default.jbs')
                self.assertEqual(raw,source.read_bytes())
                self.assertEqual(cg,prepare(source.read_bytes()).data)
                network.assert_not_called()

    def test_bottom_up_reference_dispatches_once_to_loopback_controller(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            expected=prepare(REFERENCES[False,True].read_bytes()).data
            raw,_=encode_print(reference_scene(),settings(False,True,Output='RasterOnly'),'Default.jbs')
            source=root/'bottom.jbs';source.write_bytes(raw)
            connect=socket.create_connection
            def loopback_only(address,*args,**kwargs):
                if address[0]!='127.0.0.1':raise AssertionError('Non-loopback connection forbidden in test')
                return connect(address,*args,**kwargs)
            with ControllerSimulator(expected,fragment=True,echo=False) as sim,patch('socket.create_connection',side_effect=loopback_only):
                store=JobStore(root/'queue')
                bridge=DirectPrintBridge(store,sim.endpoint,timing=FAST,locks=root/'locks')
                bridge.accept(source,str(uuid.uuid4()),settings(False,True,Output='RasterOnly'))
                self.assertEqual(bridge.step()['state'],'completed')
                self.assertTrue(sim.upload_received.is_set())
                self.assertIsNone(bridge.step())
                self.assertEqual(sum(e['kind']=='uploaded' for e in store.history(store.list()[0]['id'])),1)


@unittest.skipUnless(CAPTURE.is_file() and INTAKE.is_file() and CHECKED.is_dir(),
                     'Native frontend and private X7 reference required')
class NativeRasterPreferenceTests(unittest.TestCase):
    def test_complete_print_tickets_reach_native_conversion_and_raster_encoding(self):
        scene=load_scene(CHECKED)
        raster=scene.page['exposure'];width,height=raster['width'],raster['height']
        with tempfile.TemporaryDirectory() as temp,patch('socket.socket') as network:
            root=Path(temp)
            for invert,bottom in ((True,False),(False,True),(True,True)):
                case=root/f'{invert}-{bottom}'
                capture=capture_document(case/'captures',full_document('RasterAndVector',InvertRaster=invert,BottomUp=bottom))
                result=prepare_capture(capture,case/'prepared',INTAKE)
                for flag,value in (('InvertRaster',invert),('BottomUp',bottom)):
                    self.assertEqual(result['printer_settings']['classic_preferences'][flag],value)
                decoded=decode((case/'prepared/job.cg.jbs').read_bytes())
                actual=decoded['rasters'][0]
                rows=[scene.exposure[y*width:(y+1)*width] for y in range(height)]
                if bottom:rows.reverse()
                expected=b''.join(rows)
                if invert:expected=bytes(255-v for v in expected)
                self.assertEqual(actual['pixels'],expected)
                self.assertEqual(actual['origin_units'],[raster['x_pixels']*scene.pitch,
                    (raster['y_pixels']+(height-1 if bottom else 0))*scene.pitch])
                self.assertEqual(actual['origin_label'],'LL' if bottom else 'UL')
                self.assertEqual(len(decoded['vector_paths']),len(scene.paths))
                self.assertFalse(decoded['autostart'])
            network.assert_not_called()


if __name__=='__main__':unittest.main()
