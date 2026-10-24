"""Predict archived stamp lookup tables offline; never emit an engraving job.

This maps two bounded arithmetic helpers, not the full two-dimensional stamp
filter. It does not execute vendor code or establish independent XP parity.
"""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import struct
import sys

from tools.inspect_stamp_defaults import inspect as inspect_defaults

CONVERTER_SHA256 = '1a851b834b1ad4ed3f339093fed57659a8ac3e5f5a8c69d9eaccd6254ffd2238'


def binary32(value):
    """Round a small exact rational to binary32, nearest with ties to even.

    Returning a Fraction avoids an intermediate host binary64 rounding. The
    model only needs small normal values and zero, not arbitrary IEEE inputs.
    """
    value = Fraction(value)
    if not value:
        return value
    sign = -1 if value < 0 else 1
    value = abs(value)
    exponent = value.numerator.bit_length() - value.denominator.bit_length()
    power = lambda n: Fraction(2**n) if n >= 0 else Fraction(1, 2**-n)
    if value < power(exponent):
        exponent -= 1
    if not -126 <= exponent <= 127:
        raise ValueError('Lookup model requires a normal binary32 value or zero')
    step = power(exponent-23)
    scaled = value/step
    integer, remainder = divmod(scaled.numerator, scaled.denominator)
    if remainder*2 > scaled.denominator or (remainder*2 == scaled.denominator and integer % 2):
        integer += 1
    return sign*integer*step


def parameters(base, split, power):
    if (any(type(v) is not int for v in (base, split, power))
            or not 1 <= base <= 64 or not 0 <= split <= base or not 0 <= power <= 100):
        raise ValueError('Use bounded BasePixels 1..64, SplitPixel 0..Base, SplitPower 0..100')


def inverse_rounded(value):
    # The helper adds .5, calls MSVCRT _ftol, masks to a byte, then subtracts
    # from 255. Rounding uses the pre-store x87 value, not the binary32 copy.
    return 255-(int(value+Fraction(1, 2)) & 255)


def edge_table(base, split, power):
    parameters(base, split, power)
    split_level = binary32(Fraction(power*255, 100))
    target = binary32(255-split_level)
    current = Fraction(255)
    result = []
    if split:
        increment = binary32((current-target)/split)
        for _ in range(split-1):
            extended = current-increment
            current = binary32(extended)
            result.append(inverse_rounded(extended))
        result.append(inverse_rounded(target))
        current = binary32(target+Fraction(1, 2))
    increment = binary32(current/(base-split+1))
    for _ in range(split, base):
        extended = current-increment
        current = binary32(extended)
        result.append(inverse_rounded(extended))
    return result


def narrow_gap_table(base, split, power, width):
    parameters(base, split, power)
    if type(width) is not int or not 1 <= width < 2*split:
        raise ValueError('This helper models only positive gaps narrower than twice SplitPixel')
    # At these bounded integer widths the archived double .6 constant gives
    # floor(width/2+.6), equal to ceil(width/2), never a tie.
    half = (width+1)//2
    target = binary32(255-binary32(Fraction(power*255, 100)))
    current = Fraction(255)
    increment = binary32((current-target)/half)
    result = []
    for _ in range(half):
        extended = current-increment
        current = binary32(extended)
        result.append(inverse_rounded(extended))
    if width % 2 == 0:
        result.append(inverse_rounded(current))
    while len(result) < width:
        extended = current+increment
        current = binary32(extended)
        result.append(inverse_rounded(extended))
    return result


def gray_edge_table(base, split, power, value):
    if type(value) is not int or not 0 <= value <= 255:
        raise ValueError('Grayscale sample must be a byte')
    table = edge_table(base,split,power)
    # 1000ccfc returns the cached base table for zero, NULL for white, and
    # otherwise builds a shorter table keeping only entries strictly > sample.
    if value == 255:
        return None
    return table if value == 0 else [sample for sample in table if sample > value]


def inspect(converter, registry):
    data = Path(converter).read_bytes()
    if hashlib.sha256(data).hexdigest() != CONVERTER_SHA256:
        raise ValueError('Lookup address map requires the inspected archived BmpPict2.dll')
    defaults = inspect_defaults(registry)
    sys.path.insert(0, str(Path(__file__).resolve().parent/'python'))
    import pefile
    import capstone
    pe = pefile.PE(data=data)
    snippets = {}
    try:
        base = pe.OPTIONAL_HEADER.ImageBase
        for address, encoding, expected in ((0x1001341c,'f',.5),(0x10013420,'f',255),
                                            (0x10013428,'d',.6),(0x10013430,'d',100),
                                            (0x10013438,'d',255)):
            if struct.unpack('<'+encoding,pe.get_data(address-base,struct.calcsize(encoding)))[0] != expected:
                raise ValueError('Archived lookup constant differs')
        engine = capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32)
        for start,end in ((0x1000cecc,0x1000cee1), (0x1000d08b,0x1000d198),
                          (0x1000cb66,0x1000cc7f), (0x1000cd42,0x1000cd5a),
                          (0x1000ce02,0x1000ce52)):
            snippets[hex(start)] = [dict(va=hex(i.address),bytes=i.bytes.hex(),
                                        instruction=i.mnemonic+' '+i.op_str)
                                    for i in engine.disasm(pe.get_data(start-base,end-start),start)]
    finally:
        pe.close()
    tables = []
    for profile in defaults['profiles']:
        for prediction in profile['predictions']:
            base,split,power = prediction['arguments']
            tables.append(dict(quick_pick=profile['built_in_quick_pick'],
                nominal_dpi=prediction['nominal_dpi'], parameters=prediction['arguments'],
                edge_samples=edge_table(base,split,power),
                gray_sources=[dict(value=v,samples=gray_edge_table(base,split,power,v))
                              for v in (0,1,32,64,128,192,254,255)],
                narrow_gaps=[dict(width=w,samples=narrow_gap_table(base,split,power,w))
                             for w in range(1,2*split)]))
    return dict(state='static_lookup_predictions_not_independent_XP_output',
        converter_sha256=CONVERTER_SHA256, profiles=tables, source_instructions=snippets,
        vendor_code_executed=False, physical_device_io=False,
        full_stamp_filter_implemented=False, production_feature_hold_removed=False,
        limitations=['Archived source versions and registry overrides are unverified in installed XP.',
                     'No full image scan, row ordering, crop, coordinates or action handling is implemented.',
                     'Models bounded rational arithmetic and binary32 stores, not arbitrary x87 environments.',
                     'Lookup samples need an independent XP-converter comparison.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('converter',type=Path)
    parser.add_argument('registry',type=Path)
    parser.add_argument('output_json',type=Path)
    args=parser.parse_args()
    report=inspect(args.converter,args.registry)
    with args.output_json.open('x',encoding='utf-8') as stream:
        json.dump(report,stream,indent=2)
    print(json.dumps(dict(state=report['state'],edge_tables=len(report['profiles']),
        narrow_gap_tables=sum(len(p['narrow_gaps']) for p in report['profiles']))))


if __name__=='__main__':main()
