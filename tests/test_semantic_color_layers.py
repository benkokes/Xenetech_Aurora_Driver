"""Semantic edge coverage, independent XP composition, and real host regression."""
import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from aurora_jobserver.artwork import load_scene
from aurora_jobserver.color_drafts import encode_color_draft
from aurora_jobserver.color_rasters import (CoverageLayer,ExposureSurface,plan_color_layers,
    encode_raster_draft,plan_color_rasters)
from aurora_jobserver.jbs import DRAFT_MARKER,prepare
from aurora_jobserver.wire import raster_plan
from tools.build_semantic_color_review import build,load_native_layers,reconstruct_rgb
from tools.build_color_raster_review import reference_palette,reference_surface
from tools.compare_preference_jobs import decode


ROOT=Path(__file__).resolve().parents[1]
NATIVE=ROOT/'runtime/semantic-color-layers-20261019/host-filled-intake'
VECTOR_NATIVE=ROOT/'runtime/semantic-color-layers-20261019/host-vector-intake'
XP=ROOT/'captures/xp-color-preferences-20261019'
CASES={'unsorted':'color-unsorted-26428-17920','sorted':'color-sorted-22009-23343',
       'paused':'color-paused-15968-17857','disabled-blue':'color-disabled-blue-16495-29410'}


class SemanticCoverageTests(unittest.TestCase):
    def test_fractional_samples_are_explicit_semantic_coverage_and_survive_cg(self):
        pixels=bytes((0,64,128,255))
        layers=(CoverageLayer(0xff0000,ExposureSurface(10,20,4,1,pixels)),)
        original=copy.deepcopy(layers)
        plan=plan_color_layers(layers,reference_palette())
        self.assertEqual(plan.mask_encoding,'semantic-coverage-u8-review')
        for data in encode_raster_draft(plan):
            self.assertEqual(decode(data)['rasters'][0]['pixels'],pixels)
            self.assertFalse(prepare(data,allow_draft=True).auto_start)
            with self.assertRaisesRegex(ValueError,'uncalibrated draft'):prepare(data)
            with self.assertRaisesRegex(ValueError,'uncalibrated draft'):raster_plan(data,r'c:\xfiles\jbs\Convert\Default.jbs')
        self.assertEqual(layers,original)
        with self.assertRaisesRegex(ValueError,'binary'):
            encode_raster_draft(replace(plan,mask_encoding='binary-u8'))

    def test_unknown_layer_omission_and_disabled_pause_holds(self):
        image=ExposureSurface(0,0,2,1,b'\xff\x80')
        layers=(CoverageLayer(0xff8000,image),CoverageLayer(0x0000ff,image),CoverageLayer(0xff0000,image))
        plan=plan_color_layers(layers,reference_palette(),pause_colors=True)
        self.assertEqual([r.color_index for r in plan.regions],[1,9])
        self.assertEqual(plan.unmatched_pixels,2)
        table=reference_palette();table[9]['Enabled']=False
        self.assertEqual([r.color_index for r in plan_color_layers(layers,table).regions],[1])
        with self.assertRaisesRegex(ValueError,'independent XP evidence'):
            plan_color_layers(layers,table,pause_colors=True)

    def test_semantic_input_rejects_ambiguous_white_duplicates_empty_and_vertical_gaps(self):
        image=ExposureSurface(0,0,1,1,b'\xff');layer=CoverageLayer(0,image)
        cases=((CoverageLayer(0xffffff,image),),(layer,layer),
               (CoverageLayer(True,image),),(CoverageLayer(0,replace(image,pixels=b'\0')),),
               (CoverageLayer(0,ExposureSurface(0,0,1,3,b'\xff\0\xff')),))
        for layers in cases:
            with self.subTest(layers=layers),self.assertRaises(ValueError):plan_color_layers(layers,reference_palette())
        with self.assertRaises(ValueError):plan_color_layers((layer,),reference_palette(),pause_colors=1)

    def test_mixed_review_holds_unknown_boundaries_and_preserves_draft_marker(self):
        table=reference_palette()
        layers=(CoverageLayer(0,ExposureSurface(0,0,1,1,b'\x80')),)
        plan=plan_color_layers(layers,table)
        raw,cg=encode_color_draft(plan,(((0,0),(6,6)),),(0xff0000,),table)
        for data in (raw,cg):
            self.assertTrue(data.startswith(b'!ZX\r'+DRAFT_MARKER+b'\r'))
            self.assertEqual(decode(data)['rasters'][0]['pixels'],b'\x80')
            with self.assertRaisesRegex(ValueError,'uncalibrated draft'):prepare(data)
        with self.assertRaisesRegex(ValueError,'preferences disagree'):
            encode_color_draft(plan,(),(),table,pause_colors=True)
        other=reference_palette();other[0]['PowerPercent']='46'
        with self.assertRaisesRegex(ValueError,'processes disagree'):
            encode_color_draft(plan,(),(),other)
        multi=plan_color_rasters(reference_surface(),table)
        _,combined=encode_color_draft(multi,(((0,0),(6,6)),),(0xff0000,),table)
        self.assertEqual(len(decode(combined)['rasters']),3)
        paused=replace(multi,pause_colors=True)
        with self.assertRaisesRegex(ValueError,'Paused mixed'):
            encode_color_draft(paused,(((0,0),(6,6)),),(0xff0000,),table,pause_colors=True)


@unittest.skipUnless((NATIVE/'document.json').is_file(),'Private real-host semantic rendering required')
class NativeSemanticTests(unittest.TestCase):
    def test_real_host_layers_reconstruct_every_rgb_channel_and_recover_edges(self):
        with patch('socket.socket') as network,tempfile.TemporaryDirectory() as temp:
            doc,layers,surface=load_native_layers(NATIVE)
            reconstructed,report=reconstruct_rgb(layers,surface)
            self.assertEqual(reconstructed,surface.rgb)
            self.assertEqual(report['max_channel_error'],0)
            self.assertEqual(report['channel_count'],111825)
            self.assertEqual(hashlib.sha256(surface.rgb).hexdigest(),'37ef2bb22e3af757258fd0283f26961242f1af7447f993e871d5ab0eb7af37ec')
            result=build(NATIVE,Path(temp)/'review',reference_palette())
            self.assertEqual(result['matched_edge_pixels_recovered'],333)
            self.assertEqual(result['old_matched_pixels'],2000)
            self.assertEqual(result['semantic_matched_pixels'],2333)
            self.assertEqual([c['raster_count'] for c in result['cases']],[2,3,3,2])
            self.assertTrue(all(c['cg_preserves_native_samples'] for c in result['cases']))
            with self.assertRaises(ValueError):build(NATIVE,Path(temp)/'review',reference_palette())
            with self.assertRaises(ValueError):load_scene(NATIVE)
            network.assert_not_called()

    def test_native_snapshot_metadata_and_blob_tampering_fail(self):
        mutations=(lambda d:d.update(schema_version=2),
                   lambda d:d.update(source_sha256='0'*64),
                   lambda d:d['pages'][0]['review_reasons'].append('clip issue'),
                   lambda d:d['pages'][0]['color_layers'].update(status='unsupported_flat_color_layers'),
                   lambda d:d['pages'][0]['color_layers']['layers'][0].update(palette_index=8),
                   lambda d:d['pages'][0]['color_layers']['layers'][0]['coverage'].update(file='../outside'),
                   lambda d:d['pages'][0]['color_layers']['layers'][0]['coverage'].update(sha256='0'*64))
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/'native';shutil.copytree(NATIVE,folder)
            original=json.loads((folder/'document.json').read_text())
            for index,mutate in enumerate(mutations):
                doc=copy.deepcopy(original);mutate(doc)
                (folder/'document.json').write_text(json.dumps(doc))
                with self.subTest(case=index),self.assertRaises(ValueError):load_native_layers(folder)
            (folder/'document.json').write_text(json.dumps(original))
            file=folder/original['pages'][0]['color_layers']['layers'][0]['coverage']['file']
            file.write_bytes(b'\0'*file.stat().st_size)
            with self.assertRaisesRegex(ValueError,'hash changed'):load_native_layers(folder)


@unittest.skipUnless(all((XP/folder/'inbox/Default.jbs').is_file() for folder in CASES.values()),'Private XP color captures required')
class XpMixedColorTests(unittest.TestCase):
    def test_compositor_matches_four_complete_independent_xp_files(self):
        baseline=decode((XP/'color-global-2505-1735/inbox/Default.jbs').read_bytes())
        r=baseline['rasters'][0]
        layer=CoverageLayer(0,ExposureSurface(161,163,r['width'],r['height'],r['pixels']))
        paths=tuple(tuple(tuple(point) for point in p['points']) for p in baseline['vector_paths'])
        colors=(0xff,0xff0000,0xff,0xff0000,0xff8000)
        with patch('socket.socket') as network:
            for case,folder in CASES.items():
                table=reference_palette()
                if case=='disabled-blue':table[9]['Enabled']=False
                plan=plan_color_layers((layer,),table,pause_colors=case=='paused')
                raw,cg=encode_color_draft(plan,paths,colors,table,sort_colors=case!='unsorted',pause_colors=case=='paused',title='Default.jbs')
                self.assertEqual(raw.replace(DRAFT_MARKER+b'\r',b'',1),(XP/folder/'inbox/Default.jbs').read_bytes())
                self.assertEqual(decode(raw)['vector_paths'],decode(cg)['vector_paths'])
            network.assert_not_called()
