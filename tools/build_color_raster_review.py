"""Build marked offline raster-model reviews against the four XP captures.

The color fixture uses measured native-grid positions of the prepared drawing.
Global-mode input exposure comes from XP; this does not infer RGB luminance.
"""
import argparse
import hashlib
import json
from pathlib import Path

from aurora_jobserver.classic_settings import NAMES, RGB
from aurora_jobserver.color_settings import ColorProcess
from aurora_jobserver.color_rasters import (ExposureSurface, FlatColorSurface,
    plan_global_rasters, plan_color_rasters, encode_raster_draft)
from aurora_jobserver.jbs import DRAFT_MARKER, prepare
from tools.compare_preference_jobs import decode, summary, png_gray


REFERENCES = {
    'global': ('color-raster-global-13630-23933', '7390114e4b95b3501d78d67c80da322f3cb8ee164380d4e805051b000a1ae30b'),
    'enabled': ('color-raster-enabled-24952-16211', '4bdefd3ee534a5dd278f4ec0b00db549695c7910531119ba2886b1c8a289a2da'),
    'paused': ('color-raster-paused-2195-25550', '8d67cf4a88cc90181df66f3ec136869bbaf0be80227b5c637581740f37787fe7'),
    'disabled-blue': ('color-raster-disabled-blue-20182-29314', 'bc6a3e4985fb4f7e0767197269356bb21ea1018d9fe784afc88b04739103deb1'),
}


def reference_palette():
    # Unused entries retain the original pictured table; only Black/Red/Blue
    # are identified by these raster files. All values are offline fixtures.
    powers = (100,95,90,85,80,75,70,65,60,55,50,45,40,30,20,10)
    palette = [dict(Name=name, R=(rgb>>16)&255, G=(rgb>>8)&255, B=rgb&255,
        Enabled=True, PowerPercent=str(power), SpeedIps='100', Ppi=1000)
        for name,rgb,power in zip(NAMES,RGB,powers)]
    for index,power,speed,ppi in ((0,45,30,1000),(1,11,1,500),(9,22,2,750)):
        palette[index].update(PowerPercent=str(power), SpeedIps=str(speed), Ppi=ppi)
    return palette


def reference_surface():
    """Independent input colors at the measured XP source-grid positions."""
    w,h = 355,104
    pixels = bytearray(b'\xff'*(w*h*3))
    coverage = bytearray(w*h)
    squares = ((161,163,0x000000),(161,246,0x0000ff),(244,246,0xff0000),
               (328,246,0x0000ff),(411,246,0xff0000),(495,246,0xff8000))
    for x,y,rgb in squares:
        color = bytes(((rgb>>16)&255,(rgb>>8)&255,rgb&255))
        for row in range(y-163,y-163+21):
            start=row*w+x-161
            coverage[start:start+21]=b'\xff'*21
            pixels[start*3:(start+21)*3]=color*21
    return FlatColorSurface(161,163,w,h,bytes(pixels),bytes(coverage))


def global_surface(job):
    surface = reference_surface()
    pixels = bytearray(surface.width*surface.height)
    for raster in job['rasters']:
        x,y = raster['origin_units']
        if x%6 or y%6:
            raise ValueError('Reference origin is outside the 6-unit grid')
        x,y = int(x/6)-surface.x_pixels,int(y/6)-surface.y_pixels
        if x<0 or y<0 or x+raster['width']>surface.width or y+raster['height']>surface.height:
            raise ValueError('Reference raster leaves fixture surface')
        for row in range(raster['height']):
            start=(y+row)*surface.width+x
            pixels[start:start+raster['width']]=raster['pixels'][row*raster['width']:(row+1)*raster['width']]
    return ExposureSurface(surface.x_pixels,surface.y_pixels,surface.width,surface.height,bytes(pixels))


def build(reference_root, destination):
    reference_root,destination = Path(reference_root),Path(destination)
    if destination.exists():
        raise ValueError('Choose a fresh review directory; existing evidence is preserved')
    jobs = {}
    for case,(folder,digest) in REFERENCES.items():
        data=(reference_root/folder/'inbox/Default.jbs').read_bytes()
        if hashlib.sha256(data).hexdigest()!=digest:
            raise ValueError('Reference hash changed: '+case)
        jobs[case]=data
    color_surface = reference_surface()
    exposure = global_surface(decode(jobs['global']))
    outputs,report = {},[]
    for case in REFERENCES:
        palette = reference_palette()
        if case=='disabled-blue':
            palette[9]['Enabled']=False
        plan = (plan_global_rasters(exposure,ColorProcess(30000,45,1000)) if case=='global'
                else plan_color_rasters(color_surface,palette,pause_colors=case=='paused'))
        raw,cg=encode_raster_draft(plan,'Default.jbs')
        # This comparison never becomes an unmarked output artifact.
        if raw.replace(DRAFT_MARKER+b'\r',b'',1)!=jobs[case]:
            raise ValueError('Complete raw output differs from XP: '+case)
        if prepare(raw,allow_draft=True).auto_start or not cg.startswith(b'!ZX\r'+DRAFT_MARKER+b'\r'):
            raise ValueError('Draft marker/Autostart invariant failed')
        decoded=decode(cg)
        expected=decode(jobs[case])
        if decoded['commands']!=expected['commands'] or len(decoded['rasters'])!=len(expected['rasters']):
            raise ValueError('CG commands/region count changed: '+case)
        for a,b in zip(decoded['rasters'],expected['rasters']):
            for field in ('pixels','width','height','origin_units','origin_label','resolution_dpi','settings'):
                if a[field]!=b[field]:
                    raise ValueError('CG field changed: '+case+' '+field)
        outputs[case]=(raw,cg,decoded)
        report.append(dict(case=case,reference_sha256=hashlib.sha256(jobs[case]).hexdigest(),
            raw_draft_sha256=hashlib.sha256(raw).hexdigest(),cg_draft_sha256=hashlib.sha256(cg).hexdigest(),
            complete_raw_matches_xp_except_draft_marker=True,cg_decode_preserved=True,
            raster_count=len(plan.regions),unmatched_pixels=plan.unmatched_pixels))
    destination.mkdir(parents=True,exist_ok=False)
    (destination/'input.rgb').write_bytes(color_surface.rgb)
    (destination/'input.coverage').write_bytes(color_surface.coverage)
    (destination/'captured-global.exposure').write_bytes(exposure.pixels)
    (destination/'input.json').write_text(json.dumps(dict(x_pixels=161,y_pixels=163,width=355,height=104,
        color_source='known flat RGB fills at measured XP grid positions',
        global_exposure_source='independent XP global capture; no RGB formula inferred',
        palette=reference_palette()),indent=2)+'\n')
    for case,(raw,cg,decoded) in outputs.items():
        (destination/(case+'.raw.jbs.draft')).write_bytes(raw)
        (destination/(case+'.cg.jbs.draft')).write_bytes(cg)
        (destination/(case+'.decoded.json')).write_text(json.dumps(summary(decoded),indent=2)+'\n')
        for i,raster in enumerate(decoded['rasters'],1):
            pixels=raster['pixels'].translate(bytes(255-x for x in range(256)))
            (destination/f'{case}-{i:02d}.png').write_bytes(png_gray(raster['width'],raster['height'],pixels))
    result=dict(state='offline_models_match_four_xp_files',cases=report,marked_drafts_only=True,
        physical_device_io=False,production_use_colors_enabled=False)
    (destination/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference_root',type=Path)
    parser.add_argument('destination',type=Path)
    args=parser.parse_args()
    result=build(args.reference_root,args.destination)
    print(json.dumps(dict(state=result['state'],cases=len(result['cases']),marked_drafts_only=True)))


if __name__=='__main__':
    main()
