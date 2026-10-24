"""Package a verified mixed-color Corel 11 document and copy-only XP collectors.

Preparation does not print, change settings, connect equipment or claim XP
validation. The three candidate captures are for an owner-present follow-up.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct


INSTRUCTIONS='''PREPARED ONLY: OFFLINE XP MIXED COLOR BOUNDARY REFERENCES

These tests have NOT been run in XP. Run a case only when requested in chat.
Laser OFF; XP network cable disconnected; XP JobServer CLOSED.
Host Aurora JobServer must remain Capture only. Never use these identification
palette values as material settings or send the resulting JBS to equipment.

Open color-mixed-reference-corel11.cdr directly in XP CorelDRAW 11.
Do not import, resize or reposition. It is a 30 x 18 inch page with:
  a black .125-inch fill at 1 inch left/top;
  five .125-inch fills at top 1.5 inches, x 1/1.5/2/2.5/3 inches;
  five .25-inch outline squares at top 2 inches, the same x positions.
Both rows are Blue, Red, Blue, Red, deliberately unmatched Orange.
The fill row and vector row are separated. No text, bitmaps or gradients.

COMMON SETTINGS:
  Both Raster and Vector; 167 DPI; 30 x 18 inches, offsets zero;
  raster 30 ips/45%; vector 1 ips/15%/1000 PPI; No Focus; Autostart OFF;
  Invert OFF; Bottom-Up OFF; normal plate/engraving orientation; Mirror OFF;
  Custom bitmap; Dither OFF; Manual Contrast OFF;
  Corel Layout As in document / 100%, no fit or centering.

Save the ORIGINAL color profile under an unused name before editing it.
Set Use Color Settings ON, Sort Color Vectors ON, all colors enabled, Pause OFF.
Change only Black to 45% / 30 ips / 1000 PPI,
Red to 11% / 1 ips / 500 PPI, Blue (not Navy) to 22% / 2 ips / 750 PPI.
Leave the other original palette entries unchanged.

1. ENABLED: print ONCE, then immediately run
   xp-reference-collect-color-mixed-enabled.cmd. Wait for its file check.
   This establishes the multi-raster-color to vector pen/process boundary.

2. PAUSED: only when requested, change only Pause Between Colors ON.
   Print ONCE, run xp-reference-collect-color-mixed-paused.cmd, then wait.
   This establishes whether a pause occurs at the raster/vector transition.

3. OPTIONAL DISABLED BLUE WITH PAUSE: only if specifically requested, retain
   Pause ON and uncheck Blue. Print ONCE and immediately run
   xp-reference-collect-color-mixed-paused-disabled-blue.cmd.
   This probes the unverified omitted-color/pause combination.

After the requested cases, restore the ORIGINAL saved profile and global
settings: Use Colors OFF, Pause OFF, Both, 167 DPI, raster 30/45,
vector 1/15/1000, Autostart/Invert/Bottom-Up OFF. Do not print again.
Keep XP disconnected, its JobServer closed, host Capture only, and laser OFF.

Collectors COPY the inbox into fresh labeled folders. They do not print,
delete inbox files, change driver settings or access hardware.
'''


def package(source, destination):
    source, destination = Path(source), Path(destination)
    report = json.loads((source/'corel11-document-verification.json').read_text(encoding='utf-8-sig'))
    document = source/'color-mixed-reference-corel11.cdr'
    data = document.read_bytes()
    if (report.get('SavedVersion') != 11 or report.get('GeometryAndColorsPreserved') is not True
            or report.get('SampleKind') != 'mixed-flat-fills-and-thin-vectors'
            or hashlib.sha256(data).hexdigest() != report.get('CdrSha256')
            or data[:4] != b'RIFF' or data[8:12] != b'CDRB'
            or struct.unpack_from('<I',data,4)[0]+8 != len(data)):
        raise ValueError('Expected the verified Corel 11 mixed reference')
    page = report['After']
    if (page['Unit'] != 1 or page['PageWidth'] != 30 or page['PageHeight'] != 18
            or len(page['Shapes']) != 11 or report['Before'] != page):
        raise ValueError('Mixed page/geometry changed')
    shapes = {shape['Name']:shape for shape in page['Shapes']}
    if len(shapes) != 11:raise ValueError('Repeated mixed shape identity')
    black = shapes['RasterBlack']
    def filled(shape, rgb, side):
        return (shape.get('FillRgb') == rgb and shape['FillType'] == 1
            and shape['OutlineWidth'] == 0 and shape['Width'] == shape['Height'] == side)
    if not filled(black,[0,0,0],.125):raise ValueError('Black marker changed')
    expected = [('Blue1',[0,0,255]),('Red1',[255,0,0]),('Blue2',[0,0,255]),
        ('Red2',[255,0,0]),('UnmatchedOrange',[255,128,0])]
    for index,(name,rgb) in enumerate(expected):
        fill,vector = shapes['Fill'+name],shapes['Vector'+name]
        if (not filled(fill,rgb,.125) or vector.get('OutlineRgb') != rgb
                or vector['FillType'] != 0 or vector['OutlineWidth'] != .003
                or vector['Width'] != .25 or vector['Height'] != .25
                or abs(fill['Left']-black['Left']-index*.5)>1e-8
                or abs(vector['Left']-fill['Left'])>1e-8
                or abs(fill['Top']-black['Top']+.5)>1e-8
                or abs(vector['Top']-black['Top']+1)>1e-8):
            raise ValueError('Mixed color/size/position changed: '+name)
    destination.mkdir(parents=True,exist_ok=False)
    for path in (document,source/'corel11-document-verification.json'):
        shutil.copyfile(path,destination/path.name)
    (destination/'MIXED-COLORS-READ-ME.txt').write_text(INSTRUCTIONS.replace('\n','\r\n'),encoding='ascii',newline='')
    template=(Path(__file__).parent/'xp-output-mode-reference/xp-reference-collect-raster-only.cmd').read_text()
    for case in ('enabled','paused','paused-disabled-blue'):
        text=template.replace('output-raster-only-',f'color-mixed-{case}-')
        text=text.replace('requested_output_mode=raster-only',f'requested_mixed_color_case={case}')
        text=text.replace('the raster-only reference',f'the mixed color {case} reference')
        (destination/f'xp-reference-collect-color-mixed-{case}.cmd').write_text(text.replace('\n','\r\n'),encoding='ascii',newline='')
    result=dict(state='prepared_offline_mixed_color_reference_NOT_XP_captured',
        cdr_sha256=report['CdrSha256'],saved_corel_version=11,
        physical_device_io=False,print_submitted=False,printer_settings_changed=False,
        files={path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in destination.iterdir()})
    (destination/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path);parser.add_argument('destination',type=Path)
    args=parser.parse_args();result=package(args.source,args.destination)
    print(json.dumps({key:result[key] for key in ('state','cdr_sha256','physical_device_io')}))


if __name__=='__main__':main()
