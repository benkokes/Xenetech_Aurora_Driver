"""Portable phase/geometry/hold tests and independent private XP regressions."""
import copy
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from aurora_jobserver.artwork import ProcessSettings, Scene
from aurora_jobserver.classic_settings import carriers, decode as decode_settings, parse
from aurora_jobserver.corel_layout import COREL_GRID
from aurora_jobserver.direct_print import CONTROLLER_PATH
from aurora_jobserver.jbs import DRAFT_MARKER, prepare
from aurora_jobserver.ordered_dither import ordered_exposure, encode_ordered_draft
from aurora_jobserver.print_pipeline import encode_print
from aurora_jobserver.wire import raster_plan
from tests.test_classic_settings import payload
from tests.test_output_modes import PROCESS, sample
from tools.compare_preference_jobs import decode
from tools.build_ordered_dither_review import build


class OrderedDitherTests(unittest.TestCase):
    def test_measured_threshold_edges_and_extremes(self):
        # Literal measured thresholds at two different reference phases.
        for mode,phase,threshold in [('Ordered4',(2,1),7),('Ordered8',(6,5),1),
                                      ('Ordered4',(3,1),247),('Ordered8',(7,5),253)]:
            for signal, expected in [(0,0),(threshold,0),(threshold+1,255),(255,255)]:
                with self.subTest(mode=mode,phase=phase,signal=signal):
                    self.assertEqual(ordered_exposure(bytes([signal]),1,1,mode,
                        phase_x=phase[0],phase_y=phase[1]),bytes([expected]))

    def test_crop_and_tile_phases_preserve_whole_image_output(self):
        width,height=23,19
        pixels=bytes((x*31+y*17)%256 for y in range(height) for x in range(width))
        for mode,size in [('Ordered4',4),('Ordered8',8)]:
            whole=ordered_exposure(pixels,width,height,mode,phase_x=1,phase_y=3)
            # Odd row widths and non-multiple tile offsets expose row-wrap bugs.
            for x,y,w,h in [(1,2,17,13),(0,0,1,19),(22,0,1,19),(2,18,19,1)]:
                data=b''.join(pixels[j*width+x:j*width+x+w] for j in range(y,y+h))
                expected=b''.join(whole[j*width+x:j*width+x+w] for j in range(y,y+h))
                self.assertEqual(ordered_exposure(data,w,h,mode,
                    phase_x=(1+x)%size,phase_y=(3+y)%size),expected)

    def test_invalid_inputs_and_implicit_phase_are_rejected(self):
        for pixels,w,h,mode,px,py in [
            (b'\0',True,1,'Ordered4',0,0),(b'',0,1,'Ordered4',0,0),
            (b'\0',5001,1,'Ordered4',0,0),(b'\0',1,3001,'Ordered4',0,0),
            (bytearray(1),1,1,'Ordered4',0,0),(b'\0',2,1,'Ordered4',0,0),
            (b'\0',1,1,'FloydSteinberg',0,0),(b'\0',1,1,None,0,0),
            (b'\0',1,1,'Ordered4',4,0),(b'\0',1,1,'Ordered8',0,-1),
            (b'\0',1,1,'Ordered4',False,0),(b'\0',1,1,'Ordered8',0,1.0)]:
            with self.subTest(values=(w,h,mode,px,py)),self.assertRaises(ValueError):
                ordered_exposure(pixels,w,h,mode,phase_x=px,phase_y=py)
        with self.assertRaises(TypeError):ordered_exposure(b'\0',1,1,'Ordered4')

    def test_drafts_preserve_paths_rectangle_settings_and_input(self):
        source=sample(); original=copy.deepcopy(source)
        for method in ('Ordered4','Ordered8'):
            with patch('socket.socket') as network,patch('socket.create_connection') as connect:
                raw,cg=encode_ordered_draft(source,ProcessSettings.parse(PROCESS),method,
                    phase_x=0,phase_y=0,title='Ordered')
                for data in (raw,cg):
                    job=decode(data)
                    self.assertTrue(job['draft']);self.assertFalse(job['autostart'])
                    self.assertEqual(job['rasters'][0]['origin_units'],[60,120])
                    self.assertEqual(job['rasters'][0]['settings']['power'],45)
                    self.assertEqual(job['vector_paths'][0]['points'],[list(p) for p in source.paths[0]])
                    self.assertEqual((job['rasters'][0]['width'],job['rasters'][0]['height']),(3,2))
                    with self.assertRaisesRegex(ValueError,'uncalibrated draft'):prepare(data)
                    with self.assertRaisesRegex(ValueError,'uncalibrated draft'):raster_plan(data,CONTROLLER_PATH)
                a,b=decode(raw)['rasters'][0],decode(cg)['rasters'][0]
                for key in ('pixels','width','height','origin_units','origin_label','resolution_dpi','settings'):
                    self.assertEqual(a[key],b[key],key)
                network.assert_not_called();connect.assert_not_called()
        self.assertEqual(source,original)

    def test_scene_boundaries_and_unverified_combinations_stop(self):
        scene=sample(); process=ProcessSettings.parse(PROCESS)
        for source in [replace(scene,manifest=scene.manifest|{'dpi':100}),
                       replace(scene,manifest=scene.manifest|{'raster_grid':'other'}),
                       replace(scene,page={'exposure':None}),
                       replace(scene,page={'exposure':{'x_pixels':4999,'y_pixels':0,'width':3,'height':2}})]:
            with self.assertRaises(ValueError):encode_ordered_draft(source,process,'Ordered4',phase_x=0,phase_y=0)
        with self.assertRaises(ValueError):
            encode_ordered_draft(scene,process,'Ordered4',phase_x=0,phase_y=0,output_mode='vector-only')

    def test_all_production_dither_modes_still_stop_before_encoder(self):
        for method in ('Ordered4','Ordered8','FloydSteinberg','Jarvis','Stucki'):
            ticket=payload(DitherBitmaps=True,Dither=method)
            settings=decode_settings(carriers(parse(ticket)),ticket)
            self.assertIn('DitherBitmaps',settings['held_features'])
            with patch('aurora_jobserver.print_pipeline._encode') as encoder:
                with self.assertRaisesRegex(ValueError,'Print held:'):encode_print(None,settings,'Held')
                encoder.assert_not_called()

    def test_review_refuses_existing_evidence_or_changed_references(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);existing=root/'existing';existing.mkdir()
            sentinel=existing/'verification.json';sentinel.write_text('immutable')
            with self.assertRaisesRegex(ValueError,'fresh directory'):build(root,existing)
            self.assertEqual(sentinel.read_text(),'immutable')
            baseline=root/'grayscale-probe/gray-baseline/Default.jbs'
            baseline.parent.mkdir(parents=True);baseline.write_bytes(b'changed reference')
            destination=root/'new'
            with self.assertRaisesRegex(ValueError,'Reference hash changed'):build(root,destination)
            self.assertFalse(destination.exists())


ROOT=Path(__file__).resolve().parents[1]
XP=ROOT/'runtime/xp-mcp-tests-20261020'
REFERENCE_FILES=(XP/'grayscale-probe/gray-baseline/Default.jbs',XP/'bitmap-reference/Default.jbs')


@unittest.skipUnless(all(path.is_file() for path in REFERENCE_FILES),'Private XP ordered references required')
class XpOrderedDitherTests(unittest.TestCase):
    def test_entire_raw_and_compressed_jobs_match_two_independent_artworks(self):
        for baseline_path,folder,prefix in [(REFERENCE_FILES[0],XP/'grayscale-probe','gray-'),
                                             (REFERENCE_FILES[1],XP,'dither-')]:
            job=decode(baseline_path.read_bytes());r=job['rasters'][0]
            x,y=(int(v/6) for v in r['origin_units'])
            scene=Scene({'dpi':167,'raster_grid':COREL_GRID},
                {'exposure':{'width':r['width'],'height':r['height'],'x_pixels':x,'y_pixels':y}},r['pixels'],())
            for method,size in [('Ordered4',4),('Ordered8',8)]:
                expected_path=folder/(prefix+method.lower())/'Default.jbs'
                if not expected_path.is_file():self.skipTest('Private XP dither reference missing')
                expected=expected_path.read_bytes()
                with self.subTest(artwork=baseline_path.parent.name,method=method):
                    raw,cg=encode_ordered_draft(scene,ProcessSettings.parse(PROCESS),method,
                        phase_x=(x-169)%size,phase_y=(y-171)%size,
                        title=job['title'],output_mode='raster-only')
                    self.assertEqual(raw.replace(DRAFT_MARKER+b'\r',b'',1),expected)
                    a,b=decode(cg),decode(expected)
                    for key in ('pixels','width','height','origin_units','origin_label','resolution_dpi','settings'):
                        self.assertEqual(a['rasters'][0][key],b['rasters'][0][key],key)
                    self.assertEqual(a['commands'],b['commands'])
                    self.assertTrue(a['draft']);self.assertFalse(a['autostart'])


if __name__=='__main__':unittest.main()
