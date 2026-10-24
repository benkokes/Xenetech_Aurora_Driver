from pathlib import Path
import struct
import unittest

from tools.inspect_dialog_resources import parse


def text(value):
    return value.encode('utf-16le')+b'\0\0'


def template(extended, extra=b''):
    if extended:
        data=struct.pack('<HHIIIHhhhh',1,65535,17,0,0x40,1,0,0,200,100)
    else:
        data=struct.pack('<IIHhhhh',0x40,0,1,0,0,200,100)
    data+=b'\0\0'*2+text('Fixture')+struct.pack('<H',9)
    if extended: data+=struct.pack('<HBB',400,0,1)
    data+=text('Segoe UI')
    data+=bytes((-len(data))%4)
    if extended: data+=struct.pack('<IIIhhhhI',23,0,0x50000003,12,24,50,14,0x12345678)
    else: data+=struct.pack('<IIhhhhH',0x50000003,0,12,24,50,14,0x1234)
    data+=struct.pack('<HH',65535,0x80)+text('Check ✓')
    data+=struct.pack('<H',len(extra)+(0 if extended or not extra else 2))+extra
    return data


class DialogResourceTests(unittest.TestCase):
    def test_standard_and_extended_alignment_unicode_font_ids_and_extra_data(self):
        for extended in (False,True):
            for extra in (b'',b'abc'):
                with self.subTest(extended=extended,extra=extra):
                    data=template(extended,extra);r=parse(data)
                    self.assertEqual(r['title'],'Fixture')
                    self.assertEqual(r['font']['typeface'],'Segoe UI')
                    c=r['controls'][0]
                    self.assertEqual(c['id'],0x12345678 if extended else 0x1234)
                    self.assertEqual(c['text'],'Check ✓')
                    self.assertEqual(c['class'],'Button')
                    self.assertEqual(c['creation_data_hex'],extra.hex())
                    self.assertEqual(r['parsed_bytes'],len(data))

    def test_truncation_unknown_version_and_nonzero_remainder_fail(self):
        good=template(True)
        for bad in (good[:17],good[:-1],b'\x02\0'+good[2:],good+b'x'):
            with self.subTest(length=len(bad)),self.assertRaises(ValueError): parse(bad)

    @unittest.skipUnless(Path('analysis/extracted/laser-driver/XP_Files/xtlaserui.dll').is_file(),'Private original driver required')
    def test_actual_original_resource_labels_confirm_invert_and_bottom_up_ids(self):
        from tools.inspect_dialog_resources import inspect
        result=inspect('analysis/extracted/laser-driver/XP_Files/xtlaserui.dll')
        controls=[c for d in result['dialogs'] for c in d['controls']]
        self.assertTrue(any(c['id']==0x47a and 'Invert' in c['text'] for c in controls))
        self.assertTrue(any(c['id']==0x47c and 'Bottom' in c['text'] for c in controls))
        self.assertFalse(result['vendor_code_executed'])


if __name__=='__main__':unittest.main()
