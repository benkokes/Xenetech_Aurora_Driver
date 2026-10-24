import copy
from dataclasses import replace
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from xml.dom import minidom
import zipfile

from aurora_jobserver.artwork import Scene, ProcessSettings, encode
from aurora_jobserver.classic_settings import carriers, decode as decode_classic, parse
from aurora_jobserver.corel_layout import COREL_GRID
from aurora_jobserver.jbs import DRAFT_MARKER, prepare
from aurora_jobserver.print_pipeline import encode_print
from aurora_jobserver.print_pipeline import prepare_capture
from aurora_jobserver.print_service import PrintService
from aurora_jobserver.printer_settings import PRIVATE,PSF
from aurora_jobserver.wire import raster_plan
from tests.test_classic_settings import payload,ticket
from tests.test_print_pipeline import CAPTURE,INTAKE,CHECKED,FAST,capture_document
from tools.controller_simulator import ControllerSimulator
from tools.compare_artwork_jobs import facts


ROOT=Path(__file__).resolve().parents[1]
XP=ROOT/'captures/xp-output-modes-20261018'
CAPTURES={
    'raster-and-vector':XP/'output-both-739-9531/inbox/Default.jbs',
    'raster-only':XP/'output-raster-only-2268-7024/inbox/Default.jbs',
    'vector-only':XP/'output-vector-only-4865-10069/inbox/Default.jbs',
}
PROCESS={'schema_version':1,'units':'driver-native','raster_speed_native':30000,'raster_power_percent':45,
         'vector_speed_native':1000,'vector_power_percent':15,'vector_ppi':1000}


def settings(output):
    encoded=payload(Output=output)
    return decode_classic(carriers(parse(encoded)),encoded)


def settings_for_100_vector():
    encoded=payload(Output='VectorOnly',Resolution=100)
    return decode_classic(carriers(parse(encoded)),encoded)


def sample():
    return Scene({'dpi':167,'raster_grid':COREL_GRID,'text_rendering':'outline-aliased'},
        {'exposure':{'width':3,'height':2,'x_pixels':10,'y_pixels':20}},
        b'\0\x80\xff\x01\x02\x03',(((876,1212),(1878,1212),(1878,2214),(876,2214),(876,1212)),))


class OutputModeTests(unittest.TestCase):
    def test_raster_only_keeps_raster_bytes_and_omits_cut_commands(self):
        scene=sample();original=copy.deepcopy(scene)
        both,_=encode(scene,ProcessSettings.parse(PROCESS),'Mode')
        raster,cg=encode(scene,ProcessSettings.parse(PROCESS),'Mode',output_mode='raster-only')
        self.assertEqual(raster,both[:both.index(b'1000. speed\r')]+b'PU\r0. 0. V\rEND_PLOT\r')
        self.assertNotIn(b'PD\r',raster)
        self.assertNotIn(b'set_vppi',raster)
        self.assertEqual(prepare(cg,allow_draft=True).rasters,1)
        self.assertEqual(scene,original)

    def test_vector_only_draft_keeps_paths_without_raster_or_raster_settings(self):
        raw,cg=encode(sample(),ProcessSettings.parse(PROCESS),'Mode',output_mode='vector-only')
        self.assertNotIn(b'PICT',raw)
        self.assertNotIn(b'30000. speed',raw)
        self.assertIn(b'876.0 1212.0 V\r1 RA\rPD\r1878.0 1212.0 V\r',raw)
        self.assertEqual(raw,cg)
        self.assertEqual(prepare(raw,allow_draft=True).input_format,'vector-only')
        with self.assertRaisesRegex(ValueError,'uncalibrated draft'):
            raster_plan(raw,r'c:\xfiles\jbs\Convert\Default.jbs')

    def test_raster_only_full_settings_encode_on_existing_raster_wire_path(self):
        s=settings('RasterOnly')
        self.assertEqual(s['held_features'],[])
        self.assertEqual(s['output_mode'],'raster-only')
        raw,cg=encode_print(sample(),s,'RasterOnly')
        self.assertNotIn(b'PD\r',raw)
        self.assertEqual(prepare(cg).rasters,1)
        self.assertEqual(len(raster_plan(cg,r'c:\xfiles\jbs\Convert\Default.jbs')),8)

    def test_vector_only_full_settings_encode_with_blank_zero_power_carrier(self):
        s=settings('VectorOnly')
        self.assertEqual(s['output_mode'],'vector-only')
        self.assertEqual(s['held_features'],[])
        scene=sample();scene=replace(scene,manifest=dict(scene.manifest,cut_color='any',
            max_cut_width_mm=s['max_cut_width_mm']))
        raw,cg=encode_print(scene,s,'VectorOnly')
        self.assertIn(b'0.00 power\r',raw)
        self.assertEqual(prepare(cg).rasters,1)
        self.assertIn('VectorOnlyResolution',settings_for_100_vector()['held_features'])
        raw,_=encode(sample(),ProcessSettings.parse(PROCESS),'Mode',output_mode='vector-only')
        raw=raw.replace(DRAFT_MARKER+b'\r',b'',1)
        with self.assertRaisesRegex(ValueError,'CG raster'):
            raster_plan(raw,r'c:\xfiles\jbs\Convert\Default.jbs')

    def test_modes_with_no_selected_content_are_held_and_unknown_modes_rejected(self):
        only_vectors=replace(sample(),page={'exposure':None},exposure=b'')
        with self.assertRaisesRegex(ValueError,'Raster Only contains no raster'):
            encode_print(only_vectors,settings('RasterOnly'),'Empty')
        with self.assertRaisesRegex(ValueError,'no engraving or cutting content'):
            encode(only_vectors,ProcessSettings.parse(PROCESS),output_mode='raster-only')
        with self.assertRaisesRegex(ValueError,'no engraving or cutting content'):
            encode(replace(sample(),paths=()),ProcessSettings.parse(PROCESS),output_mode='vector-only')
        with self.assertRaisesRegex(ValueError,'Unknown laser output mode'):
            encode(sample(),ProcessSettings.parse(PROCESS),output_mode='invalid')


@unittest.skipUnless(all(path.is_file() for path in CAPTURES.values()),'Private XP output-mode reference captures required')
class XpOutputModeReferenceTests(unittest.TestCase):
    def test_all_three_modes_match_the_independent_xp_job_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            reference,pixels=facts(CAPTURES['raster-and-vector'],Path(temp)/'both')
        raster=reference['raster']
        scene=Scene({'dpi':167},{'exposure':{'width':raster['width'],'height':raster['height'],
            'x_pixels':int(raster['origin_units'][0]/6),'y_pixels':int(raster['origin_units'][1]/6)}},
            bytes(pixels),tuple(tuple(tuple(point) for point in path) for path in reference['vector_paths']))
        for mode,path in CAPTURES.items():
            with self.subTest(mode=mode):
                raw,cg=encode(scene,ProcessSettings.parse(PROCESS),'Default.jbs',output_mode=mode)
                self.assertEqual(raw.replace(DRAFT_MARKER+b'\r',b'',1),path.read_bytes())
                self.assertEqual(prepare(cg,allow_draft=True).rasters,0 if mode=='vector-only' else 1)


def full_document(output, **changes):
    result=io.BytesIO()
    properties=minidom.parseString(ticket(payload(Output=output,**changes)))
    with zipfile.ZipFile(CAPTURE) as source,zipfile.ZipFile(result,'w') as package:
        for entry in source.infolist():
            data=source.read(entry.filename)
            if entry.filename=='Metadata/Job_PT.xml':
                xml=minidom.parseString(data)
                xml.documentElement.setAttribute('xmlns:aur',PRIVATE)
                xml.documentElement.setAttribute('xmlns:psf',PSF)
                for feature in list(properties.documentElement.childNodes):
                    xml.documentElement.appendChild(xml.importNode(feature,True))
                data=xml.toxml(encoding='utf-8')
            package.writestr(entry,data)
    return result.getvalue()


@unittest.skipUnless(CAPTURE.is_file() and INTAKE.is_file() and CHECKED.is_dir(),'Native frontend and private Corel reference required')
class OutputModePipelineTests(unittest.TestCase):
    def test_raster_only_full_ticket_converts_and_dispatches_once_to_loopback(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            capture=capture_document(root/'service/captures',full_document('RasterOnly'))
            from aurora_jobserver.artwork import _encode,load_scene
            _,expected=_encode(load_scene(CHECKED),ProcessSettings.parse(PROCESS),'Print_'+capture.name[:8],draft=False,output_mode='raster-only')
            with ControllerSimulator(expected,echo=False,fragment=True,warning=True) as sim:
                service=PrintService(root/'service',sim.endpoint,INTAKE,timing=FAST,locks=root/'locks')
                service.poll_once()
                self.assertTrue(sim.upload_received.is_set())
                jobs=service.store.list();self.assertEqual(len(jobs),1)
                job=service.store.get(jobs[0]['id'])
                self.assertEqual(job['state'],'completed_with_warning')
                self.assertEqual(job['settings']['printer_settings']['output_mode'],'raster-only')
                self.assertEqual((service.store.directory(job['id'])/'prepared.jbs').read_bytes(),expected)
                self.assertEqual(sum(event['kind']=='uploaded' for event in service.store.history(job['id'])),1)
                service.poll_once()
                self.assertEqual(sum(event['kind']=='uploaded' for event in service.store.history(job['id'])),1)

    def test_vector_only_full_ticket_converts_without_any_socket(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            capture=capture_document(root/'captures',full_document('VectorOnly'))
            with patch('socket.create_connection') as connect:
                result=prepare_capture(capture,root/'prepared',INTAKE)
                connect.assert_not_called()
            self.assertEqual(result['state'],'encoded_for_direct_print')
            self.assertTrue((root/'prepared/job.cg.jbs').exists())


if __name__=='__main__':unittest.main()
