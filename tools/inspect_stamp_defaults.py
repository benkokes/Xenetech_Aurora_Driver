"""Recover built-in stamp fallbacks and predict their command offline.

The PE is parsed as data. No vendor module is loaded, no registry is read, and
no complete laser job is emitted. Predictions still need independent XP capture.
"""
import argparse
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import struct
import sys


REGISTRY_SHA256 = '85beed95637d0372e6fdf3e91e5cbf3d14708d4df574a009ac8539d9ac31e7b8'
ADAPTER_SHA256 = '7a5a98e96c6284bbeaac2abbf6d989a2ca6c7c379774ef9ef4b31b5aa81e66f4'
GRAPHICS_SHA256 = '6aad6387df4d5e83008f17badeb8d284a9031d63d4ff61699c148a5913bc2c0d'
RESOLUTIONS = (50, 100, 167, 200, 250, 333, 500, 1000, 1200)
# Instruction addresses holding the original built-in fallback float bits.
VALUES = {
    'Scale': ((0x1000442c, 0x3cf5c28f), (0x10004472, 0x3d800000)),
    'Base': ((0x1000497c, 0x3c449ba6), (0x100049c2, 0x3ca3d70a)),
    'Shoulder': ((0x10004ecc, 0x3b83126f), (0x10004f12, 0x3c23d70a)),
    'Gradient': ((0x1000541c, 0x3f19999a), (0x10005435, 0x3e99999a),
                 (0x1000544e, 0x3f000000), (0x10005467, 0x3f333333), (0x10005480, 0x3f666666)),
}


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def builder_dpi(nominal_dpi):
    if type(nominal_dpi) is not int or nominal_dpi not in RESOLUTIONS:
        raise ValueError('Choose an original nominal DPI')
    scaled = {167:166667, 333:333333}.get(nominal_dpi, nominal_dpi*1000)
    # Drv helper 406dea -> NewWorld 100038e5..f6. The adapter multiplies
    # by a binary32 .001 constant and stores the actual argument as binary32.
    return f32(scaled*f32(.001))


def predict(profile, dpi):
    if type(dpi) is not int or dpi not in RESOLUTIONS:
        raise ValueError('Choose an original nominal DPI')
    if set(profile) != set(VALUES) or any(type(v) is not float or not 0 <= v <= 1 for v in profile.values()):
        raise ValueError('Expected the four decoded bounded binary32 fallback values')
    # Explicit binary32 stores in the builder: 1/DPI and Gradient*100.
    # This mathematical prediction does not emulate an arbitrary x87 environment.
    with localcontext() as context:
        context.prec = 80
        effective_dpi = builder_dpi(dpi)
        pitch = Decimal.from_float(f32(1 / effective_dpi))
        base, shoulder = (Decimal.from_float(profile[k]) for k in ('Base', 'Shoulder'))
        rounded = lambda value: int(value + Decimal('.5'))
        total_pixels = rounded((base + shoulder) / pitch)
        shoulder_pixels = max(1, rounded(shoulder / pitch))
        gradient_percent = rounded(Decimal.from_float(f32(profile['Gradient'] * 100)))
    return {'nominal_dpi': dpi, 'builder_dpi_argument_binary32': effective_dpi,
            'arguments': [total_pixels, shoulder_pixels, gradient_percent],
            'predicted_command': f'{total_pixels} {shoulder_pixels} {gradient_percent} set_stamp_mode',
            'validation': 'static_prediction_not_xp_capture_or_delivery_authorization'}


def inspect(path):
    sys.path.insert(0, str(Path(__file__).resolve().parent/'python'))
    import pefile
    import capstone
    from capstone.x86 import X86_OP_IMM
    path = Path(path)
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != REGISTRY_SHA256:
        raise ValueError('This address map requires the inspected archived XGWRegistry.dll')
    adapter_path = path.parent/'NewWorld.dll'
    graphics_path = path.parent.parent/'XP_Files/xtlasergr.dll'
    adapter_bytes, graphics_bytes = adapter_path.read_bytes(), graphics_path.read_bytes()
    if (hashlib.sha256(adapter_bytes).hexdigest() != ADAPTER_SHA256
            or hashlib.sha256(graphics_bytes).hexdigest() != GRAPHICS_SHA256):
        raise ValueError('The DPI adapter map requires the inspected NewWorld and XP graphics binaries')
    pe = pefile.PE(data=data)
    adapter, graphics = pefile.PE(data=adapter_bytes), pefile.PE(data=graphics_bytes)
    engine = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    engine.detail = True
    base = pe.OPTIONAL_HEADER.ImageBase
    records, decoded = {}, {}
    try:
        if struct.unpack('<f',adapter.get_data(0x10005848-adapter.OPTIONAL_HEADER.ImageBase,4))[0] != f32(.001):
            raise ValueError('Original DPI adapter multiplier differs')
        for name, choices in VALUES.items():
            records[name] = []; decoded[name] = []
            for address, expected in choices:
                instruction = next(engine.disasm(pe.get_data(address-base, 16), address))
                if (instruction.mnemonic != 'mov' or len(instruction.operands) != 2
                        or instruction.operands[1].type != X86_OP_IMM
                        or instruction.operands[1].imm != expected
                        or not instruction.op_str.startswith('dword ptr [esp + 0x10],')):
                    raise ValueError('Original fallback instruction differs from the inspected map')
                value = struct.unpack('<f', struct.pack('<I', expected))[0]
                decoded[name].append(value)
                records[name].append({'va': hex(address), 'instruction_bytes': instruction.bytes.hex(),
                    'instruction': instruction.mnemonic+' '+instruction.op_str,
                    'float32_bits': f'{expected:08x}', 'float32_value': value})
        exports = {base+s.address: s.name.decode() for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name}
        vtable = {}
        for offset, expected in ((0x40,'Gradient'), (0x48,'Shoulder'), (0x50,'Base'), (0x58,'Scale')):
            target, = struct.unpack('<I', pe.get_data(0x100071c0-base+offset, 4))
            name = exports.get(target, '')
            if not name.startswith('?GetDlgRubberStamp'+expected+'@'):
                raise ValueError('Original virtual getter order differs')
            vtable[hex(offset)] = {'target': hex(target), 'export': name}
        for address, expected in ((0x10007350,.5), (0x10007354,100.0), (0x10007358,1.0)):
            if struct.unpack('<f',pe.get_data(address-base,4))[0] != expected:
                raise ValueError('Original command-builder numeric constant differs')
        if pe.get_data(0x100097f0-base, 16).split(b'\0')[0] != b' set_stamp_mode':
            raise ValueError('Original stamp command suffix differs')
        profiles = []
        for index in range(5):
            values = {name: (items[index] if name == 'Gradient' else items[0 if index==0 else 1])
                      for name, items in decoded.items()}
            profiles.append({'built_in_quick_pick': index+1, 'fallback_values': values,
                             'predictions': [predict(values,dpi) for dpi in RESOLUTIONS]})
        snippets = {}
        for address, length in ((0x1000605a,0xbb), (0x10006115,0xd9)):
            snippets[hex(address)] = [{'va':hex(i.address), 'bytes':i.bytes.hex(),
                                     'instruction':i.mnemonic+' '+i.op_str}
                                    for i in engine.disasm(pe.get_data(address-base,length),address)]
        adapter_snippets = [{'va':hex(i.address),'bytes':i.bytes.hex(),'instruction':i.mnemonic+' '+i.op_str}
                            for i in engine.disasm(adapter.get_data(0x38e5,0x1a),0x100038e5)]
        graphics_snippets = [{'va':hex(i.address),'bytes':i.bytes.hex(),'instruction':i.mnemonic+' '+i.op_str}
                             for i in engine.disasm(graphics.get_data(0x6dea,0x29),0x406dea)]
    finally:
        pe.close();adapter.close();graphics.close()
    return {'state':'static_built_in_stamp_fallbacks_recovered', 'source':str(path), 'source_sha256':digest,
            'fallback_instructions':records, 'virtual_getter_table':vtable, 'command_builder_snippets':snippets,
            'dpi_adapter':{'source':str(adapter_path),'sha256':ADAPTER_SHA256,'instructions':adapter_snippets},
            'graphics_dpi_helper':{'source':str(graphics_path),'sha256':GRAPHICS_SHA256,'instructions':graphics_snippets},
            'serialized_argument_order':['round((Base+Shoulder)/float32(1/DPI))',
                                         'max(1,round(Shoulder/float32(1/DPI)))',
                                         'round(float32(Gradient*100))'],
            'scale_read_by_this_command_builder':False, 'profiles':profiles,
            'serializer_stack_trace':[
                {'call_va':'0x1000611d','argument_source':'eax','meaning':'rounded total Base+Shoulder sample count'},
                {'call_va':'0x1000617f','argument_source':'[esp+0x28] after buffer push; entry-relative stack -116',
                 'meaning':'rounded Shoulder sample count, clamped to at least one'},
                {'call_va':'0x100061e2','argument_source':'[esp+0x38] after buffer push; entry-relative stack -112',
                 'meaning':'rounded Gradient times 100'}],
            'limitations':['Built-in fallbacks may differ from current XP registry profiles.',
                           'Scale/Depth raster processing is not reproduced by this command prediction.',
                           'UI field units and exact saved-profile mapping need independent confirmation.',
                           'DPI adapter mapping is established statically; complete command output still requires an XP reference.',
                           'Archived helper DLL versions have not been independently matched to the running XP installation.',
                           'No stamp backend feature hold is removed.'],
            'vendor_module_loaded_or_executed':False, 'registry_access_performed':False,
            'physical_device_io_performed':False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('registry_dll',type=Path)
    parser.add_argument('output_json',type=Path)
    args=parser.parse_args()
    report=inspect(args.registry_dll)
    with args.output_json.open('x',encoding='utf-8') as stream: json.dump(report,stream,indent=2)
    print(json.dumps({'state':report['state'], 'profiles':len(report['profiles']),
                     'predictions':sum(len(p['predictions']) for p in report['profiles'])}))


if __name__=='__main__':main()
