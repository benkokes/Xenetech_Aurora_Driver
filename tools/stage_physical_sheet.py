"""Stage one fixed, supervised Aurora test sheet offline; never connect/send.

This creates new calibration artwork. It cannot release arbitrary draft files
or enable any production print preference. Operator readiness is a separate step.
Pillow and the installed Arial font are needed only by this development tool.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from aurora_jobserver.artwork import GRID, ProcessSettings, Scene, _encode
from aurora_jobserver.jbs import DRAFT_MARKER, prepare
from aurora_jobserver.ordered_dither import ordered_exposure
from aurora_jobserver.wire import raster_plan
from tools.compare_preference_jobs import decode


WIDTH, HEIGHT = 668, 501
ORIGIN = (167, 167)
SETTINGS = {'schema_version':1, 'units':'inches-per-second',
    'raster_speed_ips':30, 'raster_power_percent':45,
    'vector_speed_ips':1, 'vector_power_percent':15, 'vector_ppi':1000}
PANEL_X = (16, 240, 464)
PANEL_Y, PANEL_WIDTH, PANEL_HEIGHT = 94, 176, 134
PHASE_ANCHOR = (169, 171)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def stage(destination, *, raster_power_percent=45):
    if type(raster_power_percent) is not int or raster_power_percent not in (45,54):
        raise ValueError('Only the reviewed 45% sheet and requested 20% increase to 54% are supported')
    destination=Path(destination)
    if destination.exists():
        raise ValueError('Choose a fresh directory; existing evidence is preserved')
    title='AuroraSheet167P'+str(raster_power_percent)
    settings=dict(SETTINGS,raster_power_percent=raster_power_percent)
    font_path=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Fonts/arial.ttf'
    font=ImageFont.truetype(str(font_path),18)
    small=ImageFont.truetype(str(font_path),15)
    heading=ImageFont.truetype(str(font_path),24)
    # Exposure polarity: black on this in-memory image is blank, white burns.
    image=Image.new('L',(WIDTH,HEIGHT),0)
    draw=ImageDraw.Draw(image)
    draw.text((16,4),'AURORA REAL-WORLD SHEET',font=heading,fill=255)
    draw.text((16,35),f'167 DPI   Raster 30 ips / {raster_power_percent}%   Vector 1 ips / 15% / 1000 PPI',font=small,fill=255)
    for left,label in zip(PANEL_X,('GRAYSCALE','ORDERED 4x4','ORDERED 8x8')):
        draw.text((left,67),label,font=font,fill=255)
        for x in range(PANEL_WIDTH):
            exposure=round(x*255/(PANEL_WIDTH-1))
            draw.line((left+x,96,left+x,156),fill=exposure)
        for index,level in enumerate((0,64,128,192,255)):
            x0=left+index*PANEL_WIDTH//5
            x1=left+(index+1)*PANEL_WIDTH//5-1
            draw.rectangle((x0,176,x1,221),fill=level)
        draw.text((left,234),'ABC 123 abc',font=font,fill=255)
        draw.text((left,261),'Fine lines: 1 / 2 / 3 px',font=small,fill=255)
        for n,thickness in enumerate((1,2,3)):
            for y in range(288,304,2*thickness):
                draw.rectangle((left+n*58,y,left+n*58+49,min(303,y+thickness-1)),fill=255)
    draw.text((216,342),'1-inch vector square',font=font,fill=255)
    draw.text((216,369),'Measure width + height',font=small,fill=255)
    draw.text((448,322),'0.5-inch circle',font=small,fill=255)
    draw.text((216,437),'Compare darkness, grain,',font=small,fill=255)
    draw.text((216,458),'text, lines and complete paths.',font=small,fill=255)
    # Four small corner registration marks establish the complete raster extent.
    for x,y,sx,sy in ((0,0,1,1),(WIDTH-1,0,-1,1),(0,HEIGHT-1,1,-1),(WIDTH-1,HEIGHT-1,-1,-1)):
        draw.line((x,y,x+sx*9,y),fill=255)
        draw.line((x,y,x,y+sy*9),fill=255)
    source=image.tobytes()
    output=bytearray(source)
    panels=[]
    for left,method in zip(PANEL_X[1:],('Ordered4','Ordered8')):
        size=4 if method=='Ordered4' else 8
        original=b''.join(source[y*WIDTH+left:y*WIDTH+left+PANEL_WIDTH]
                          for y in range(PANEL_Y,PANEL_Y+PANEL_HEIGHT))
        phase=((ORIGIN[0]+left-PHASE_ANCHOR[0])%size,
               (ORIGIN[1]+PANEL_Y-PHASE_ANCHOR[1])%size)
        processed=ordered_exposure(original,PANEL_WIDTH,PANEL_HEIGHT,method,
            phase_x=phase[0],phase_y=phase[1])
        for row in range(PANEL_HEIGHT):
            start=(PANEL_Y+row)*WIDTH+left
            output[start:start+PANEL_WIDTH]=processed[row*PANEL_WIDTH:(row+1)*PANEL_WIDTH]
        panels.append({'method':method,'rectangle_pixels':[left,PANEL_Y,PANEL_WIDTH,PANEL_HEIGHT],
            'phase':list(phase),'input_sha256':sha(original),'output_sha256':sha(processed)})
    exposure=bytes(output)
    # Square follows the same 167-sample, six-unit convention as the accepted
    # one-inch calibration square. The circle is a 64-segment 500-unit path.
    x,y=(ORIGIN[0]+16)*6,(ORIGIN[1]+318)*6
    square=((x,y),(x+1002,y),(x+1002,y+1002),(x,y+1002),(x,y))
    cx,cy=(ORIGIN[0]+548)*6,(ORIGIN[1]+400)*6
    circle=tuple((round(cx+250*math.cos(2*math.pi*i/64),1),
                  round(cy+250*math.sin(2*math.pi*i/64),1)) for i in range(64))
    circle=circle+(circle[0],)
    scene=Scene({'dpi':167,'raster_grid':GRID,'source_kind':'fixed native-grid physical test fixture'},
        {'exposure':{'width':WIDTH,'height':HEIGHT,'x_pixels':ORIGIN[0],'y_pixels':ORIGIN[1]}},
        exposure,(square,circle))
    raw,cg=_encode(scene,ProcessSettings.parse(settings),title,draft=False,autostart=False)
    a,b=decode(raw),decode(cg)
    assert not a['draft'] and not a['autostart'] and len(a['rasters'])==1 and len(a['vector_paths'])==2
    assert DRAFT_MARKER not in raw[:128] and prepare(cg).auto_start is False
    for key in ('pixels','width','height','origin_units','origin_label','resolution_dpi','settings'):
        assert a['rasters'][0][key]==b['rasters'][0][key],key
    assert a['rasters'][0]['pixels']==exposure and a['vector_paths']==b['vector_paths']
    plan=raster_plan(cg,r'c:\xfiles\jbs\Convert\Default.jbs')
    preview=Image.frombytes('L',(WIDTH,HEIGHT),bytes(255-v for v in exposure)).convert('RGB')
    overlay=ImageDraw.Draw(preview)
    for path in (square,circle):
        points=[((px/6)-ORIGIN[0],(py/6)-ORIGIN[1]) for px,py in path]
        overlay.line(points,fill=(220,0,0),width=1)
    result={'schema_version':1,'state':'staged_offline_awaiting_operator_readiness',
        'purpose':'one supervised combined physical evaluation; not a production feature release',
        'title':title,'source_kind':'programmatically constructed native-grid fixture; no new Corel print in this staging step',
        'physical_device_io':False,'auto_start':False,'focus':'No Focus at Start; operator prepares focus and material',
        'process_settings':settings,'source_font_sha256':sha(font_path.read_bytes()),
        'power_feedback_basis':None if raster_power_percent==45 else 'Owner reports appearance good; requests about 20% darker. Candidate power is 45*1.2=54%, not a guarantee of proportional darkness.',
        'source_exposure_sha256':sha(source),'processed_exposure_sha256':sha(exposure),
        'raster_pixels':[WIDTH,HEIGHT],'raster_origin_units':[1002,1002],
        'content_bounds_units':[1002,1002,5010,4008],
        'approximate_content_bounds_inches':[1.002,1.002,5.010,4.008],
        'recommended_material_coverage_inches':[0.9,0.9,5.3,4.3],
        'vector_square_units':[1002,1002],'vector_circle_diameter_units':500,
        'panels':panels,'phase_rule_status':'explicit candidate for supervised real-world evaluation; production DitherBitmaps remains held',
        'known_original_warning':"Token 'set_xyup_feed' not found.",
        'wire_plan_steps':len(plan),
        'files':{'sheet.raw.jbs':{'bytes':len(raw),'sha256':sha(raw)},
                 'sheet.cg.jbs':{'bytes':len(cg),'sha256':sha(cg)}}}
    destination.mkdir(parents=True,exist_ok=False)
    (destination/'source-exposure.bin').write_bytes(source)
    (destination/'processed-exposure.bin').write_bytes(exposure)
    (destination/'sheet.raw.jbs').write_bytes(raw)
    (destination/'sheet.cg.jbs').write_bytes(cg)
    preview.save(destination/'preview.png')
    (destination/'physical-sheet-plan.json').write_text(json.dumps(result,indent=2)+'\n')
    measurements={'job_sha256':sha(cg),'completed':None,'material_and_focus':None,
        'square_width':None,'square_height':None,'measurement_units':None,
        'circle_diameter':None,'grayscale_vs_ordered4_vs_ordered8':None,
        'text_and_fine_lines':None,'missing_or_unexpected_marks':None,'operator_notes':None}
    (destination/'measurements-template.json').write_text(json.dumps(measurements,indent=2)+'\n')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path)
    parser.add_argument('--raster-power-percent',type=int,choices=(45,54),default=45)
    args=parser.parse_args()
    result=stage(args.destination,raster_power_percent=args.raster_power_percent)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
