"""Package a verified Corel 11 color sample and copy-only XP collectors."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct


INSTRUCTIONS='''OFFLINE XP COLOR SETTINGS COMPARISON — NO LASER DELIVERY

Keep the laser OFF, XP network cable disconnected and XP JobServer closed.
Keep host Aurora JobServer in Capture only. These values identify file output;
they are NOT material settings or permission to engrave.

Open color-reference-corel11.cdr in XP CorelDRAW 11. This is already a
30 x 18 inch document. Do not import/resize/reposition the shapes. It contains
a small black filled raster marker and five .25-inch outline squares: blue,
red, blue, red, and orange. The orange is deliberately not in the 16-color
palette. There is no text or bitmap to import. Creation order is recorded in
corel11-document-verification.json; actual XP output order is to be measured.

COMMON SETTINGS (keep these unchanged):
  Both Raster and Vector; 167 DPI; plate 30 x 18 inches, zero offsets;
  raster speed 30 ips / power 45%; vector speed 1 ips / power 15% / 1000 PPI;
  No Focus; Autostart OFF; Invert OFF; Bottom-Up OFF;
  normal plate/engraving orientation; Custom bitmap, Dither OFF, Contrast OFF;
  Corel Print Layout: As in document / 100%, no fit or centering.

DO THE CASE REQUESTED IN CHAT ONLY, then run its collector immediately.
Every collector copies files to a fresh labeled folder and leaves originals.
If a print/copy fails, stop and report it instead of printing a duplicate.

1. GLOBAL BASELINE — Use Color Settings OFF, Pause Between Colors OFF.
   Leave the palette unchanged. Print ONCE, then run
   xp-reference-collect-color-global.cmd. Wait for the file check in chat.

2. UNSORTED COLORS — First save a copy of the existing color profile under an
   unused name such as BeforeColorTest-20261019 so it can be restored later.
   Select Use Color Settings ON, Sort Color Vectors OFF, Pause Between Colors
   OFF. In Color Settings, change ONLY these entries (leave all enabled):
     Black: power 45%, speed 30.000 ips, PPI 1000 (filled raster marker)
     Red:   power 11%, speed  1.000 ips, PPI  500
     Blue:  power 22%, speed  2.000 ips, PPI  750 (Blue, not Navy)
   Print ONCE, then run xp-reference-collect-color-unsorted.cmd.

3. SORTED COLORS — Change only Sort Color Vectors to ON. Print ONCE, then run
   xp-reference-collect-color-sorted.cmd.

4. PAUSE BETWEEN COLORS — Keep Sort ON, change only Pause Between Colors ON.
   Print ONCE, then run xp-reference-collect-color-paused.cmd.

5. DISABLED BLUE — Turn Pause OFF, keep Sort ON, and uncheck Blue's enabled
   checkbox in the Color Settings table. Print ONCE, then run
   xp-reference-collect-color-disabled-blue.cmd.

WHEN THE REQUESTED CASES ARE FINISHED:
  Restore the saved original color profile. Restore Use Color Settings OFF,
  Pause OFF, Invert OFF, Bottom-Up OFF, Both Raster and Vector, 167 DPI,
  raster 30/45, vector 1/15/1000, Autostart OFF. Do not print again.
  Keep XP disconnected and JobServer closed; keep the laser OFF.

No new host color behavior is enabled by preparing or collecting these files.
'''


RASTER_INSTRUCTIONS='''OFFLINE XP COLORED RASTER COMPARISON — NO LASER DELIVERY

Keep the laser OFF, XP disconnected and XP JobServer closed.
Keep host Aurora JobServer in Capture only. Identification values are NOT
material settings or permission to engrave.

Open color-raster-reference-corel11.cdr directly in XP CorelDRAW 11.
Do not import, resize or reposition. It contains six .125-inch filled squares:
one black marker and blue, red, blue, red, unmatched orange. All have NO outline.
This isolates raster processing; no vector path is expected.

COMMON: Both Raster and Vector; 167 DPI; 30 x 18 inches; zero offsets;
raster 30 ips/45%; vector 1 ips/15%/1000 PPI; No Focus; Autostart OFF;
Invert and Bottom-Up OFF; normal orientation; Mirror OFF;
Custom bitmap, Dither OFF, Manual Contrast OFF;
Corel As in document/100%, no fit or centering.

DO ONLY THE CASE REQUESTED IN CHAT, then collect immediately and wait.

1. GLOBAL: Use Color Settings OFF, Pause OFF, original color table restored.
   Print ONCE; run xp-reference-collect-color-raster-global.cmd.

2. ENABLED (only after global is verified): save the original color profile
   under a new name before edits. Use Color Settings ON, Sort ON, Pause OFF.
   Set Black 45%/30.000 ips/1000, Red 11%/1.000 ips/500,
   Blue (not Navy) 22%/2.000 ips/750; all enabled. Other entries unchanged.
   Print ONCE; run xp-reference-collect-color-raster-enabled.cmd.
   Leave these settings until checked in chat.

3. PAUSED (only when requested): change ONLY Pause Between Colors ON.
   Keep Use Colors ON, Sort ON, all enabled and the same table/drawing.
   Print ONCE; run xp-reference-collect-color-raster-paused.cmd.

4. DISABLED BLUE (only when requested): Pause OFF; keep Use Colors/Sort ON.
   Uncheck Blue (not Navy), leaving all other settings unchanged.
   Print ONCE; run xp-reference-collect-color-raster-disabled-blue.cmd.

Restore the saved original profile and accepted global settings when asked;
do not print after restoration. Keep XP offline and the laser OFF.
These files are PREPARED tests until actual XP captures are verified.
'''


def create(source,destination,*,raster_fills=False):
    source,destination=Path(source),Path(destination)
    document=source/('color-raster-reference-corel11.cdr' if raster_fills else 'color-reference-corel11.cdr')
    report=json.loads((source/'corel11-document-verification.json').read_text(encoding='utf-8-sig'))
    data=document.read_bytes()
    if (report['SavedVersion']!=11 or not report['GeometryAndColorsPreserved']
            or hashlib.sha256(data).hexdigest()!=report['CdrSha256']
            or data[:4]!=b'RIFF' or data[8:12]!=b'CDRB' or struct.unpack_from('<I',data,4)[0]+8!=len(data)):
        raise ValueError('Expected the verified CorelDRAW 11 document')
    page=report['After']
    if raster_fills and report.get('SampleKind')!='filled-raster-colors':
        raise ValueError('Expected the filled-raster reference report')
    if (page['Unit']!=1 or page['PageWidth']!=30 or page['PageHeight']!=18 or len(page['Shapes'])!=6):
        raise ValueError('Unexpected reference page')
    by_name={s['Name']:s for s in page['Shapes']}
    expected={'Blue1':[0,0,255],'Red1':[255,0,0],'Blue2':[0,0,255],
              'Red2':[255,0,0],'UnmatchedOrange':[255,128,0]}
    for name,rgb in expected.items():
        shape=by_name[name]
        valid=(shape.get('FillRgb')==rgb and shape['FillType']==1 and shape['OutlineWidth']==0
               and shape['Width']==.125 and shape['Height']==.125) if raster_fills else (
               shape.get('OutlineRgb')==rgb and shape['FillType']==0 and shape['OutlineWidth']==.003
               and shape['Width']==.25 and shape['Height']==.25)
        if not valid:
            raise ValueError('Color or geometry changed: '+name)
    black=by_name['RasterBlack']
    if (black['FillRgb']!=[0,0,0] or black['OutlineWidth']!=0 or black['FillType']!=1
            or black['Width']!=.125 or black['Height']!=.125):
        raise ValueError('Raster marker changed')
    destination.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(document,destination/document.name)
    shutil.copyfile(source/'corel11-document-verification.json',destination/'corel11-document-verification.json')
    instructions=RASTER_INSTRUCTIONS if raster_fills else INSTRUCTIONS
    (destination/'COLOR-PREFERENCES-READ-ME.txt').write_text(instructions.replace('\n','\r\n'),encoding='utf-8',newline='')
    template=(Path(__file__).parent/'xp-output-mode-reference/xp-reference-collect-raster-only.cmd').read_text()
    cases=('global','enabled','paused','disabled-blue') if raster_fills else ('global','unsorted','sorted','paused','disabled-blue')
    prefix='color-raster' if raster_fills else 'color'
    for case in cases:
        text=template.replace('output-raster-only-',f'{prefix}-{case}-')
        text=text.replace('requested_output_mode=raster-only',f'requested_color_case={case}')
        text=text.replace('the raster-only reference',f'the color {case} reference')
        (destination/f'xp-reference-collect-{prefix}-{case}.cmd').write_text(text.replace('\n','\r\n'),encoding='ascii',newline='')
    manifest=dict(state='prepared_offline_color_reference_not_XP_captured',
                  saved_corel_version=11,cdr_sha256=report['CdrSha256'],
                  sample_kind='filled-raster-colors' if raster_fills else 'vector-colors-with-black-raster-marker',
                  physical_device_io=False,printer_settings_changed=False,
                  files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in destination.iterdir() if p.is_file()})
    (destination/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('destination',type=Path)
    parser.add_argument('--raster-fills',action='store_true')
    args=parser.parse_args()
    result=create(args.source,args.destination,raster_fills=args.raster_fills)
    print(json.dumps(dict(state=result['state'],files=len(result['files']),cdr_sha256=result['cdr_sha256'])))


if __name__=='__main__':main()
