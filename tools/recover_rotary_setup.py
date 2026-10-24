"""Read matched XP binaries and retain rotary-setup evidence; never execute them."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'python'))
import capstone
import pefile


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    'graphics': ('analysis/extracted/laser-driver/XP_Files/xtlasergr.dll',
                 '6aad6387df4d5e83008f17badeb8d284a9031d63d4ff61699c148a5913bc2c0d'),
    'ui': ('analysis/extracted/laser-driver/XP_Files/xtlaserui.dll',
           'b6fc2764110be158356cb5ca1a6e5f9f4e6765bc5f0d1b97309cad161899a942'),
}


def recover(root=ROOT):
    result = {'state':'static_model_not_xp_capture_or_hardware_validation',
              'physical_device_io':False, 'sources':{}, 'snippets':{}, 'constants':{}}
    machine = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    for kind, (relative, expected) in SOURCES.items():
        path = root / relative
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != expected:
            raise ValueError('Rotary static source does not match the inspected XP binary: '+kind)
        result['sources'][kind] = {'path':relative, 'sha256':digest}
        pe = pefile.PE(str(path))
        try:
            base = pe.OPTIONAL_HEADER.ImageBase
            def block(start, end):
                data = pe.get_data(start-base, end-start)
                return {'start_va':hex(start), 'end_va_exclusive':hex(end), 'bytes':data.hex(),
                        'instructions':[f'{i.address:08x}: {i.mnemonic} {i.op_str}'
                                        for i in machine.disasm(data, start)]}
            if kind == 'graphics':
                result['snippets']['graphics_ebx_is_one'] = block(0x407530,0x40753a)
                result['snippets']['graphics_rotary_branch'] = block(0x407663,0x4076d7)
                for label, address in (('pi',0x403200),('tenth_mm_to_inches',0x403208)):
                    data = pe.get_data(address-base, 8)
                    result['constants'][label] = {'va':hex(address), 'bytes':data.hex(),
                                                  'double':struct.unpack('<d',data)[0]}
            else:
                result['snippets']['ui_cylindrical_flag'] = block(0x407c46,0x407caa)
        finally:
            pe.close()
    result['interpretation'] = {
        'flag':'0x4 at private DEVMODE+0xdc, copied to graphics PDEV+0x11c',
        'orientation_0_or_2':'select signed dmPaperLength at graphics PDEV+0x90',
        'orientation_1_or_3':'select signed dmPaperWidth at graphics PDEV+0x92',
        'positive_dimension_formula':'pi / (selected_tenth_mm * 0.003937007874015748)',
        'output':'1 set_rotary\\r<scale to five decimal places> zset_axis\\r',
        'not_established':['UI cylinder dimension conversion', 'rotary Corel surface/placement',
                           'physical rotary calibration and direction'],
    }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path, help='New evidence directory, never overwritten')
    args = parser.parse_args()
    report = recover()
    args.destination.mkdir(parents=True, exist_ok=False)
    (args.destination/'static-evidence.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'state':report['state'], 'physical_device_io':False}))


if __name__ == '__main__':
    main()
