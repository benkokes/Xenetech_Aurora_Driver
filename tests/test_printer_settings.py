from pathlib import Path
import tempfile
import unittest
import zipfile

from aurora_jobserver.printer_settings import (FEATURES, PRIVATE, PSF, TICKET_TYPE,
    default_selection, decode, make_ticket, ticket_selection, settings_from_xps)
from tools.build_printer_package import build, gpd


class PrinterSettingsTests(unittest.TestCase):
    def test_default_values_match_the_accepted_physical_test(self):
        result = decode(ticket_selection(make_ticket(default_selection())))
        self.assertEqual(result['process_settings'], {'schema_version':1, 'units':'driver-native',
            'raster_speed_native':30000, 'raster_power_percent':45,
            'vector_speed_native':1000, 'vector_power_percent':15, 'vector_ppi':1000})
        self.assertEqual(result['laser_dpi'],167)
        self.assertFalse(result['autostart'])
        self.assertEqual(result['page_mm'],[762,457.2])

    def test_every_advertised_option_round_trips_and_decodes(self):
        for feature in FEATURES:
            for option, _ in feature.options:
                selected = default_selection() | {feature.key:option}
                self.assertEqual(ticket_selection(make_ticket(selected)),selected)
                decode(selected)

    def test_prefix_changes_and_utf16_do_not_change_meaning(self):
        data = make_ticket(default_selection()).decode().replace('aur:', 'laser:').replace('xmlns:aur=', 'xmlns:laser=')
        self.assertEqual(ticket_selection(data.encode()),default_selection())
        self.assertEqual(ticket_selection(data.replace("encoding='utf-8'", "encoding='utf-16'").encode('utf-16')),default_selection())

    def test_missing_unknown_duplicate_nested_or_wrong_namespace_rejected(self):
        good = make_ticket(default_selection()).decode()
        fragment = '<psf:Feature name="aur:JobAuroraAutostart"><psf:Option name="aur:On" /></psf:Feature>'
        cases = [good.replace('aur:JobAuroraFocus','aur:Unsupported'),
                 good.replace('aur:JobAuroraFocus','aur:AuroraFocus'),
                 good.replace(PRIVATE,PRIVATE+'-wrong'),
                 good.replace('aur:Off','psf:Off'),
                 good.replace('aur:Off','aur:Unknown'),
                 good.replace('</psf:PrintTicket>',fragment+'</psf:PrintTicket>'),
                 good.replace('name="aur:JobAuroraFocus"','name="aur:Parent"'),
                 good.replace('version="1"','version="2"')]
        for data in cases:
            with self.subTest(data=data[-150:]), self.assertRaises(ValueError):
                ticket_selection(data.encode())
        missing = default_selection(); missing.pop('AuroraRasterPower')
        with self.assertRaises(ValueError):
            decode(missing)
        nested = good.replace('<psf:Feature name="aur:JobAuroraFocus">','<psf:Feature name="psf:Outer"><psf:Feature name="aur:JobAuroraFocus">').replace('</psf:PrintTicket>','</psf:Feature></psf:PrintTicket>')
        with self.assertRaises(ValueError):
            ticket_selection(nested.encode())

    def test_dtd_entities_and_excessive_xml_rejected(self):
        for data in (b'<!DOCTYPE x [<!ENTITY y "z">]><x>&y;</x>',
                     '<!DOCTYPE x><x/>'.encode('utf-16'), b'x'*(1024*1024+1)):
            with self.assertRaises(ValueError):
                ticket_selection(data)

    def test_windows_generated_default_ticket_uses_job_scoped_features(self):
        # Captured from the installed v4 driver's native PrintConfig provider;
        # only the machine-specific binary DEVMODE snapshot was removed.
        path = Path(__file__).parent / 'fixtures' / 'aurora-v4-default-printticket.xml'
        self.assertEqual(ticket_selection(path.read_bytes()), default_selection())

    def package(self, path, *, job=None, page=None, orphan=False, external=False):
        ns = 'http://schemas.openxmlformats.org/package/2006/relationships'
        with zipfile.ZipFile(path,'w') as z:
            z.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="'+TICKET_TYPE+'"/></Types>')
            z.writestr('_rels/.rels','<Relationships xmlns="'+ns+'"><Relationship Id="R0" Type="http://schemas.openxps.org/oxps/v1.0/fixedrepresentation" Target="Fixed.fdseq"/></Relationships>')
            z.writestr('Fixed.fdseq','sequence stub: only settings reader uses this fixture')
            target = 'https://example.invalid/settings' if external else ('Job.xml' if not orphan else 'Empty.xml')
            mode = ' TargetMode="External"' if external else ''
            z.writestr('_rels/Fixed.fdseq.rels','<Relationships xmlns="'+ns+'"><Relationship Id="R0" Type="http://schemas.openxps.org/oxps/v1.0/printticket" Target="'+target+'"'+mode+'/></Relationships>')
            z.writestr('Job.xml',make_ticket(default_selection()) if job is None else job)
            if orphan:
                z.writestr('Empty.xml','<psf:PrintTicket xmlns:psf="'+PSF+'" version="1"/>')
            if page is not None:
                z.writestr('Page.xml',page)

    def test_attached_job_properties_are_immutable_and_conflicts_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)/'document.oxps'
            self.package(source)
            self.assertEqual(settings_from_xps(source),decode(default_selection()))
            changed = default_selection() | {'AuroraRasterPower':'Percent30'}
            self.package(source,page=make_ticket(changed))
            with self.assertRaisesRegex(ValueError,'Conflicting'):
                settings_from_xps(source)
            self.package(source,orphan=True)
            with self.assertRaisesRegex(ValueError,'missing explicit'):
                settings_from_xps(source)
            self.package(source,external=True)
            with self.assertRaisesRegex(ValueError,'External'):
                settings_from_xps(source)

    def test_generated_gpd_options_and_package_are_consistent(self):
        text = gpd()
        self.assertIn('*MasterUnits: PAIR(600, 600)',text)
        self.assertIn('*PageDimensions: PAIR(18000, 10800)',text)
        # Windows queue creation requires these, even for XPS passthrough.
        # The first package omitted InputBin and failed Add-Printer with 1003.
        for required in ('InputBin','PaperSize','Resolution'):
            self.assertIn('*Feature: '+required+'\n',text)
        self.assertIn('*DefaultOption: FORMSOURCE',text)
        self.assertIn('*Command: CmdSelect\n',text)
        for feature in FEATURES:
            self.assertIn('*Feature: '+feature.key,text)
            self.assertIn('*DefaultOption: '+feature.default,text)
            for option, _ in feature.options:
                self.assertIn('*Option: '+option+'\n',text)
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp)/'driver'
            result = build(destination)
            self.assertEqual(result['state'],'unsigned_source_package_not_installed')
            self.assertEqual(result['default_settings'],decode(default_selection()))
            self.assertEqual(len(result['files']),4)
            self.assertFalse((destination/'Aurora.cat').exists())
            with self.assertRaises(FileExistsError):
                build(destination)

    def test_lossless_image_policy_has_a_public_quality_option(self):
        # A manifest-only PNG rule was ignored by real X7 GDI prints because
        # the provider did not advertise PageOutputQuality at all.
        import configparser
        import re
        text = gpd()
        quality = re.search(r'\*Feature: OutputQuality\s*\{(.*?)\n\}', text, re.S).group(1)
        self.assertIn('*PrintSchemaKeywordMap: "PageOutputQuality"', quality)
        self.assertIn('*ConcealFromUI?: TRUE', quality)
        self.assertIn('*DefaultOption: High', quality)
        self.assertEqual(re.findall(r'\*Option: (\w+)', quality), ['High'])
        self.assertIn('*PrintSchemaKeywordMap: "High"', quality)
        with tempfile.TemporaryDirectory() as temp:
            build(Path(temp) / 'driver')
            manifest = configparser.ConfigParser()
            manifest.read(Path(temp) / 'driver' / 'Aurora-manifest.ini')
            self.assertEqual(manifest['DriverRender']['PageOutputQuality.High'], 'MxdcImageType.PNG')


if __name__ == '__main__':
    unittest.main()
