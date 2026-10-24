import base64
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from aurora_jobserver import classic_settings as classic
from aurora_jobserver.printer_settings import (PRIVATE, PSF, default_selection,
    make_ticket, settings_from_xps, ticket_payload)
from aurora_jobserver.print_pipeline import encode_print, prepare_capture
from tests import test_printer_settings as fixture_helpers
from tests.test_print_pipeline import capture_document


REFERENCE = Path(__file__).parent / 'fixtures' / 'classic-preferences-default.xml'


def payload(**changes):
    root = ET.fromstring(REFERENCE.read_bytes())
    for key, value in changes.items():
        root.find(key).text = str(value).lower() if isinstance(value,bool) else str(value)
    return base64.b64encode(ET.tostring(root,encoding='utf-8')).decode('ascii')


def ticket(value, *, selection=None):
    expected = classic.carriers(classic.parse(value)) if selection is None else selection
    root = ET.fromstring(make_ticket(default_selection()))
    root.set('xmlns:aur',PRIVATE)
    for feature in root.findall('{'+PSF+'}Feature'):
        key = feature.get('name').split(':')[1][3:]
        feature.find('{'+PSF+'}Option').set('name','aur:'+expected[key])
    parameter = ET.SubElement(root,'{'+PSF+'}ParameterInit',{'name':'aur:'+classic.PARAMETER})
    ET.SubElement(parameter,'{'+PSF+'}Value').text=value
    return ET.tostring(root,encoding='utf-8')


class ClassicSettingsTests(unittest.TestCase):
    def test_versioned_travel_baseline_preserves_the_exact_working_output(self):
        from tests.test_output_modes import sample
        from tools.compare_preference_jobs import decode
        old=payload()
        new=payload(Version=2,TravelSpeed='0.100')
        legacy=classic.decode(classic.carriers(classic.parse(old)),old)
        current=classic.decode(classic.carriers(classic.parse(new)),new)
        self.assertEqual(legacy['held_features'],[])
        self.assertEqual(current['held_features'],[])
        with patch('socket.socket') as network:
            before=encode_print(sample(),legacy,'TravelBaseline')
            after=encode_print(sample(),current,'TravelBaseline')
        network.assert_not_called()
        self.assertEqual(before,after)
        self.assertIn('100. set_xyup_feed',decode(after[0])['commands'])
        self.assertEqual(current['classic_preferences']['Version'],2)
        self.assertEqual(current['classic_preferences']['TravelSpeed'],'0.1')

    def test_legacy_ambiguous_and_new_nonbaseline_travel_stay_held_before_encoding(self):
        for version,values in ((1,('0.001','0.1','1','90','250')),(2,('0.001','1','90','100','250'))):
            for value in values:
                with self.subTest(version=version,value=value):
                    snapshot=payload(Version=version,TravelSpeed=value)
                    selected=classic.carriers(classic.parse(snapshot))
                    settings=classic.decode(selected,snapshot)
                    self.assertIn('TravelSpeed',settings['held_features'])
                    with patch('aurora_jobserver.print_pipeline._encode') as encoder:
                        with self.assertRaisesRegex(ValueError,'TravelSpeed'):
                            encode_print(None,settings,'HeldTravel')
                        encoder.assert_not_called()
        for version in (0,3):
            with self.assertRaises(ValueError):classic.parse(payload(Version=version))

    def test_csharp_default_snapshot_preserves_the_accepted_flatbed_profile(self):
        value=payload()
        settings=classic.parse(value)
        self.assertEqual(classic.carriers(settings),default_selection())
        self.assertEqual(classic.holds(settings),[])
        decoded=classic.decode(default_selection(),value)
        self.assertEqual(decoded['process_settings']['raster_power_percent'],45)
        self.assertEqual(decoded['laser_dpi'],167)
        self.assertEqual(len(decoded['classic_preferences']['Colors']),16)

    def test_arbitrary_numeric_controls_are_exact_and_conflicting_carriers_fail(self):
        value=payload(RasterPower='45.25',RasterSpeed='12.345',VectorPpi=777)
        selected=classic.carriers(classic.parse(value))
        self.assertEqual([selected[key] for key in ('AuroraRasterPower','AuroraRasterSpeed','AuroraVectorPPI')],['Custom']*3)
        decoded=classic.decode(selected,value)
        self.assertEqual(decoded['process_settings']['raster_speed_native'],12345)
        self.assertEqual(decoded['process_settings']['raster_power_percent'],45.25)
        self.assertEqual(decoded['process_settings']['vector_ppi'],777)
        with self.assertRaisesRegex(ValueError,'Conflicting'):
            classic.decode(default_selection(),value)

    def test_each_unverified_active_feature_holds_before_encoding(self):
        changes={'Focus':'Autofocus',
            'BeamConstantlyOn':False,'PlateWidthInches':12,'PlateHeightInches':10,'OffsetXInches':1,'OffsetYInches':1,
            'Cylindrical':True,'CenterHorizontal':True,'CenterVertical':True,'TravelSpeed':90,'BitmapMode':'Photo',
            'DitherBitmaps':True,'ManualContrast':True,'Orientation':'Right90','Mirror':True,'RubberStamp':True,
            'OutputDirectory':'C:\\jobs','DefaultFilename':False,'AppendDateTime':True,'Resolution':500,'RasterSpeed':100}
        for key,value in changes.items():
            with self.subTest(feature=key):
                encoded=payload(**{key:value});selected=classic.carriers(classic.parse(encoded));settings=classic.decode(selected,encoded)
                self.assertIn(key,settings['held_features'])
                with self.assertRaisesRegex(ValueError,'Print held:'):
                    encode_print(None,settings,'must_not_encode')

    def test_inactive_color_and_thickness_settings_are_preserved_without_changing_output(self):
        value=payload(ThicknessInches='0.125',Dither='Jarvis',SortColors=False,PauseColors=True)
        settings=classic.parse(value)
        self.assertEqual(settings['ThicknessInches'],'0.125')
        self.assertEqual(classic.holds(settings),[])

    def test_incomplete_hostile_duplicate_precision_and_palette_changes_rejected(self):
        good=REFERENCE.read_text()
        cases=[good.replace('<Version>1</Version>',''),good.replace('<Version>1</Version>','<Version>1</Version><Version>1</Version>'),
            good.replace('<RasterPower>45</RasterPower>','<RasterPower>45.123</RasterPower>'),
            good.replace('<Name>Silver</Name>','<Name>Other</Name>'),
            '<!DOCTYPE AuroraPreferences [<!ENTITY x SYSTEM "file:///missing">]>'+good]
        for xml in cases:
            with self.subTest(xml=xml[:70]),self.assertRaises(ValueError):
                classic.parse(base64.b64encode(xml.encode()).decode())
        for bad in ('!','A'*20004,base64.b64encode(b'\xff').decode()):
            with self.assertRaises(ValueError):classic.parse(bad)

    def test_job_snapshot_survives_xps_read_and_queued_jobs_are_independent(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'job.oxps';fixtures=fixture_helpers.PrinterSettingsTests()
            first=payload();second=payload(RasterPower=46,VectorPower=16)
            fixtures.package(path,job=ticket(first));before=settings_from_xps(path)
            fixtures.package(path,job=ticket(second));after=settings_from_xps(path)
            self.assertEqual(before['process_settings']['raster_power_percent'],45)
            self.assertEqual(after['process_settings']['raster_power_percent'],46)
            self.assertNotEqual(before['preferences_sha256'],after['preferences_sha256'])

    def test_windows_opaque_devmode_parameter_does_not_replace_laser_settings(self):
        value=payload(RasterPower=46)
        root=ET.fromstring(ticket(value));root.set('xmlns:aur',PRIVATE)
        opaque=ET.SubElement(root,'{'+PSF+'}ParameterInit',{'name':'aur:PageDevmodeSnapshot'})
        ET.SubElement(opaque,'{'+PSF+'}Value').text='AA=='
        self.assertEqual(ticket_payload(ET.tostring(root)),value)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'job.oxps';fixture_helpers.PrinterSettingsTests().package(path,job=ET.tostring(root))
            self.assertEqual(settings_from_xps(path)['process_settings']['raster_power_percent'],46)

    def test_full_preferences_conflicts_duplicates_and_missing_snapshot_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'job.oxps';fixtures=fixture_helpers.PrinterSettingsTests()
            fixtures.package(path,job=ticket(payload()),page=ticket(payload(RasterPower=46)))
            with self.assertRaisesRegex(ValueError,'Conflicting'):settings_from_xps(path)
            data=ticket(payload());root=ET.fromstring(data);root.set('xmlns:aur',PRIVATE)
            root.append(ET.fromstring(ET.tostring(root.find('{'+PSF+'}ParameterInit'))))
            with self.assertRaisesRegex(ValueError,'duplicate'):ticket_payload(ET.tostring(root))
            root=ET.fromstring(ticket(payload(RasterPower='45.25')));root.set('xmlns:aur',PRIVATE);root.remove(root.find('{'+PSF+'}ParameterInit'))
            fixtures.package(path,job=ET.tostring(root))
            with self.assertRaisesRegex(ValueError,'Unsupported printer option'):settings_from_xps(path)

    def test_unverified_job_is_held_before_the_renderer_runs(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path=root/'job.oxps';fixture_helpers.PrinterSettingsTests().package(path,job=ticket(payload(Focus='Autofocus')))
            capture=capture_document(root/'captures',path.read_bytes())
            with patch('aurora_jobserver.print_pipeline.subprocess.run') as render:
                with self.assertRaisesRegex(ValueError,'Focus'):prepare_capture(capture,root/'prepared','unused-renderer.exe')
                render.assert_not_called()


if __name__=='__main__':unittest.main()
