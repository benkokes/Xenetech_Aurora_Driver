"""Full-snapshot offline color review; no default-printer or equipment access."""
import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from xml.dom import minidom
import xml.etree.ElementTree as ET
import zipfile

from aurora_jobserver.classic_settings import ensure_supported
from aurora_jobserver.jbs import DRAFT_MARKER, prepare
from aurora_jobserver.printer_settings import PRIVATE, PSF, settings_from_xps
from tools.build_color_raster_review import reference_palette
from tools.compare_preference_jobs import decode
from tools.review_color_job import encode_native_review, native_paths, review_job, review_settings
from tests.test_classic_settings import REFERENCE, ticket
from tests.test_semantic_color_layers import NATIVE, VECTOR_NATIVE, XP, CASES


ROOT = Path(__file__).resolve().parents[1]
INTAKE = ROOT / 'build/frontend-semantic-color-20261019/Aurora.XpsIntake.exe'
MIXED_NATIVE = ROOT / 'runtime/semantic-color-layers-20261019/host-mixed-intake'


def synthetic_snapshot(source, *, table=None, **changes):
    """Repackage saved artwork with a SYNTHETIC ticket, not a new host/XP print."""
    preferences = ET.fromstring(REFERENCE.read_bytes())
    for key, value in ({'UseColors':True} | changes).items():
        preferences.find(key).text = str(value).lower() if isinstance(value, bool) else str(value)
    for node, record in zip(preferences.find('Colors'), table or reference_palette()):
        for key, value in record.items():
            node.find(key).text = str(value).lower() if isinstance(value, bool) else str(value)
    payload = base64.b64encode(ET.tostring(preferences, encoding='utf-8')).decode('ascii')
    properties = minidom.parseString(ticket(payload))
    result = io.BytesIO()
    with zipfile.ZipFile(source) as package, zipfile.ZipFile(result, 'w') as output:
        for entry in package.infolist():
            data = package.read(entry.filename)
            if entry.filename == 'Metadata/Job_PT.xml':
                doc = minidom.parseString(data)
                doc.documentElement.setAttribute('xmlns:aur', PRIVATE)
                doc.documentElement.setAttribute('xmlns:psf', PSF)
                for element in list(doc.documentElement.childNodes):
                    if (element.nodeType == element.ELEMENT_NODE and element.namespaceURI == PSF
                            and element.localName in ('Feature', 'ParameterInit')
                            and element.getAttribute('name').split(':')[-1].startswith(('JobAurora', 'PageDevmodeSnapshot'))):
                        doc.documentElement.removeChild(element)
                for element in list(properties.documentElement.childNodes):
                    doc.documentElement.appendChild(doc.importNode(element, True))
                data = doc.toxml(encoding='utf-8')
            output.writestr(entry, data)
    return result.getvalue()


def native_with_snapshot(source_native, destination, **changes):
    """Synthetic fixture changes only ticket bytes/hash, never a renderer claim."""
    shutil.copytree(source_native, destination)
    snapshot = destination / 'source.bin'
    snapshot.write_bytes(synthetic_snapshot(snapshot, **changes))
    manifest = json.loads((destination / 'document.json').read_text())
    manifest['source_sha256'] = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    (destination / 'document.json').write_text(json.dumps(manifest))
    return settings_from_xps(snapshot)


@unittest.skipUnless((NATIVE/'document.json').is_file() and (VECTOR_NATIVE/'document.json').is_file(), 'Private real-host fixtures required')
class ColorJobReviewTests(unittest.TestCase):
    def test_only_complete_supported_color_snapshot_proceeds_to_review(self):
        changes = ({'UseColors':False}, {'Autostart':True}, {'Resolution':100}, {'InvertRaster':True},
            {'BottomUp':True}, {'Mirror':True}, {'Focus':'Autofocus'}, {'Output':'VectorOnly'},
            {'RasterSpeed':100}, {'DitherBitmaps':True}, {'Orientation':'Left90'})
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            source = folder/'source.oxps'
            for index, change in enumerate(changes):
                source.write_bytes(synthetic_snapshot(NATIVE/'source.bin', **change))
                with self.subTest(change=change), patch('tools.review_color_job.subprocess.run') as native, patch('socket.socket') as network:
                    report = review_job(source, folder/f'held-{index}', INTAKE)
                    self.assertEqual(report['state'], 'held_offline_color_review')
                    self.assertFalse((folder/f'held-{index}/job.cg.jbs.draft').exists())
                    native.assert_not_called(); network.assert_not_called()
            report = review_job(NATIVE/'source.bin', folder/'legacy', INTAKE)
            self.assertIn('complete job-attached', report['hold_reason'])
            with self.assertRaisesRegex(ValueError, 'fresh review directory'):
                review_job(source, folder/'legacy', INTAKE)

    def test_immutable_tickets_control_masks_processes_order_and_pauses(self):
        with tempfile.TemporaryDirectory() as temp, patch('socket.socket') as network:
            root = Path(temp)
            settings = native_with_snapshot(NATIVE, root/'one', SortColors=True)
            with self.assertRaisesRegex(ValueError, 'UseColors'): ensure_supported(settings,allow_color_rasters=False)
            raw, cg, report = encode_native_review(root/'one', settings)
            self.assertEqual(report['selected_raster_regions'], 3)
            self.assertEqual(report['unmatched_raster_samples'], 462)
            self.assertEqual(report['appearance']['max_channel_error'], 0)
            self.assertEqual([r['settings']['power'] for r in decode(cg)['rasters']], [45, 11, 22])
            table = reference_palette(); table[1]['PowerPercent']='13'; table[9]['Enabled']=False
            other = native_with_snapshot(NATIVE, root/'two', table=table)
            raw2, cg2, _ = encode_native_review(root/'two', other)
            self.assertEqual([r['settings']['power'] for r in decode(cg2)['rasters']], [45, 13])
            self.assertEqual([r['settings']['power'] for r in decode(cg)['rasters']], [45, 11, 22])
            self.assertNotEqual(settings['preferences_sha256'], other['preferences_sha256'])
            with self.assertRaisesRegex(ValueError, 'preferences disagree'):
                encode_native_review(root/'one', other)
            paused = native_with_snapshot(NATIVE, root/'pause', PauseColors=True)
            _, paused_cg, _ = encode_native_review(root/'pause', paused)
            self.assertEqual(decode(paused_cg)['commands'].count('PAUSE'), 2)
            network.assert_not_called()

    def test_actual_host_mixed_geometry_matches_all_four_xp_color_commands(self):
        with tempfile.TemporaryDirectory() as temp, patch('socket.socket') as network:
            root = Path(temp)
            for case, folder in CASES.items():
                table = reference_palette()
                if case=='disabled-blue': table[9]['Enabled']=False
                settings = native_with_snapshot(VECTOR_NATIVE, root/case, table=table,
                    SortColors=case!='unsorted', PauseColors=case=='paused')
                raw, cg, result = encode_native_review(root/case, settings)
                actual, expected = decode(raw), decode((XP/folder/'inbox/Default.jbs').read_bytes())
                self.assertEqual(actual['commands'], expected['commands'])
                self.assertEqual(actual['vector_paths'], expected['vector_paths'])
                self.assertEqual(sum(a!=b for a,b in zip(actual['rasters'][0]['pixels'],expected['rasters'][0]['pixels'])), 41)
                self.assertEqual(result['selected_vector_paths'], 3 if case=='disabled-blue' else 5)
                for data in (raw, cg):
                    self.assertTrue(data.startswith(b'!ZX\r'+DRAFT_MARKER+b'\r'))
                    with self.assertRaisesRegex(ValueError, 'uncalibrated draft'): prepare(data)
            network.assert_not_called()

    def test_native_geometry_tampering_does_not_pass_the_review_profile(self):
        doc = json.loads((VECTOR_NATIVE/'document.json').read_text())
        changes = (lambda d:d.update(render_dpi=100), lambda d:d.update(tiled_raster=True),
            lambda d:d.update(max_cut_width_mm=.5), lambda d:d['pages'][0].update(pixel_width=5010),
            lambda d:d['pages'][0].update(width_mm=float('nan')),
            lambda d:d['pages'][0]['cuts'][0].update(color='#800000FF'),
            lambda d:d['pages'][0]['cuts'][0].update(closed=1),
            lambda d:d['pages'][0]['cuts'][0].update(width_mm=.3),
            lambda d:d['pages'][0]['cuts'][0].update(points_mm=[[0,0],[0,0]]),
            lambda d:d['pages'][0]['cuts'][0]['points_mm'][0].__setitem__(0, float('nan')))
        for change in changes:
            other=copy.deepcopy(doc); change(other)
            with self.subTest(change=change), self.assertRaises(ValueError): native_paths(other)

    def test_native_failure_and_timeout_are_preserved_as_holds(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); source=root/'source.oxps'
            source.write_bytes(synthetic_snapshot(NATIVE/'source.bin'))
            import subprocess
            with patch('tools.review_color_job.subprocess.run', side_effect=subprocess.TimeoutExpired('reader',45)):
                report=review_job(source,root/'timeout',INTAKE)
                self.assertEqual(report['state'],'held_offline_color_review')
                self.assertIn('timed out',report['hold_reason'])
            with patch('tools.review_color_job.subprocess.run',return_value=subprocess.CompletedProcess('reader',1,b'output',b'failure')):
                report=review_job(source,root/'failed',INTAKE)
                self.assertEqual(report['state'],'held_offline_color_review')
                self.assertEqual((root/'failed/native.stderr.log').read_bytes(),b'failure')
            source.write_bytes(b'not an XPS package')
            with patch('tools.review_color_job.subprocess.run') as native:
                report=review_job(source,root/'bad-package',INTAKE)
                self.assertEqual(report['state'],'held_offline_color_review')
                native.assert_not_called()

    def test_unverified_combinations_are_held_after_native_inspection(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            settings=native_with_snapshot(NATIVE,root/'mixed')
            doc=json.loads((root/'mixed/document.json').read_text())
            vector=json.loads((VECTOR_NATIVE/'document.json').read_text())
            doc['pages'][0]['cuts']=vector['pages'][0]['cuts']
            (root/'mixed/document.json').write_text(json.dumps(doc))
            _,_,mixed_report=encode_native_review(root/'mixed',settings)
            self.assertEqual(mixed_report['selected_raster_regions'],3)
            self.assertEqual(mixed_report['selected_vector_paths'],5)
            # Raster Only deliberately omits the separately extracted vectors.
            settings=native_with_snapshot(NATIVE,root/'raster-only',Output='RasterOnly')
            doc['source_sha256']=hashlib.sha256((root/'raster-only/source.bin').read_bytes()).hexdigest()
            (root/'raster-only/document.json').write_text(json.dumps(doc))
            _,_,report=encode_native_review(root/'raster-only',settings)
            self.assertEqual(report['native_vector_paths'],5)
            self.assertEqual(report['selected_vector_paths'],0)
            table=reference_palette();table[1]['PowerPercent']='11.25'
            source=root/'fractional.oxps';source.write_bytes(synthetic_snapshot(NATIVE/'source.bin',table=table))
            with patch('tools.review_color_job.subprocess.run') as native:
                result=review_job(source,root/'fractional',INTAKE)
                self.assertIn('Fractional color power',result['hold_reason'])
                native.assert_not_called()


@unittest.skipUnless(INTAKE.is_file() and (NATIVE/'source.bin').is_file(), 'Experimental native reader required')
class ColorJobReviewIntegrationTests(unittest.TestCase):
    def test_full_snapshot_native_render_and_marked_drafts_end_to_end(self):
        with tempfile.TemporaryDirectory() as temp, patch('socket.socket') as network:
            root=Path(temp); source=root/'synthetic-full-ticket.oxps'
            source.write_bytes(synthetic_snapshot(NATIVE/'source.bin', PauseColors=True))
            report=review_job(source,root/'review',INTAKE)
            self.assertEqual(report['state'],'prepared_offline_color_review',report.get('hold_reason'))
            self.assertEqual(report['selected_raster_regions'],3)
            self.assertEqual(report['appearance']['max_channel_error'],0)
            self.assertFalse(report['actual_xp_capture'])
            self.assertTrue(report['production_use_colors_enabled'])
            self.assertFalse(report['physical_device_io'])
            self.assertEqual(report['decoded']['commands'].count('PAUSE'),2)
            self.assertEqual(json.loads((root/'review/review.json').read_text()),json.loads(json.dumps(report)))
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),report['source_sha256'])
            network.assert_not_called()

    @unittest.skipUnless((MIXED_NATIVE/'source.bin').is_file(),'Private actual-host mixed-color capture required')
    def test_actual_combined_corel_artwork_uses_verified_unpaused_boundary(self):
        from tools.build_semantic_color_review import load_native_layers,reconstruct_rgb
        a,layers,surface=load_native_layers(MIXED_NATIVE)
        _,reference_layers,reference_surface=load_native_layers(NATIVE)
        self.assertEqual(layers,reference_layers)
        self.assertEqual(surface,reference_surface)
        self.assertEqual(reconstruct_rgb(layers,surface)[0],surface.rgb)
        self.assertEqual(len(native_paths(a)[0]),5)
        with tempfile.TemporaryDirectory() as temp,patch('socket.socket') as network:
            root=Path(temp);source=root/'synthetic-mixed-full-ticket.oxps'
            source.write_bytes(synthetic_snapshot(MIXED_NATIVE/'source.bin'))
            report=review_job(source,root/'mixed-ready',INTAKE)
            self.assertEqual(report['state'],'prepared_offline_color_review',report.get('hold_reason'))
            self.assertEqual(report['selected_raster_regions'],3)
            self.assertEqual(report['selected_vector_paths'],5)
            source.write_bytes(synthetic_snapshot(MIXED_NATIVE/'source.bin',Output='RasterOnly'))
            report=review_job(source,root/'mixed-raster-only',INTAKE)
            self.assertEqual(report['state'],'prepared_offline_color_review',report.get('hold_reason'))
            self.assertEqual(report['native_vector_paths'],5)
            self.assertEqual(report['selected_vector_paths'],0)
            self.assertEqual(report['selected_raster_regions'],3)
            network.assert_not_called()


if __name__=='__main__': unittest.main()
