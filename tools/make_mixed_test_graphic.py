"""Build diagnostic artwork and a Corel construction spec; never print/send."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont


def build(destination):
    destination=Path(destination).resolve();destination.mkdir(parents=True,exist_ok=False)
    image=Image.new('L',(501,250),255);draw=ImageDraw.Draw(image)
    font=ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf',11)
    for x in range(8,493):
        value=round((x-8)*255/484)
        draw.line((x,8,x,44),fill=value)
    for index in range(8):
        draw.rectangle((8+index*485//8,59,8+(index+1)*485//8-1,94),fill=round(index*255/7))
    for y in range(116,241):
        for x in range(38,226):
            dx=(x-130)/60;dy=(y-178)/60;r2=dx*dx+dy*dy
            if r2<=1:
                z=math.sqrt(1-r2);light=max(0,-.4*dx-.45*dy+.8*z)
                value=round(32+200*min(1,light))
                image.putpixel((x,y),value)
    for index,pitch in enumerate((1,2,3,4)):
        left=250+index*61
        draw.text((left,110),str(pitch)+' px',font=font,fill=0)
        for y in range(128,174):
            for x in range(53):image.putpixel((left+x,y),0 if (x//pitch)%2==0 else 255)
        for y in range(193,240):
            for x in range(53):image.putpixel((left+x,y),0 if ((x//pitch)+(y-193)//pitch)%2==0 else 255)
    draw.text((250,177),'CHECKER DETAIL',font=font,fill=0)
    image.convert('RGB').save(destination/'raster-detail.bmp')
    shapes=[]
    def text(name,x,y,value,size=8,bold=False):
        shapes.append(dict(kind='text',name=name,x=x,y=y,text=value,size=size,bold=bold))
    def shape(kind,name,x,y,**kwargs):shapes.append(dict(kind=kind,name=name,x=x,y=y,**kwargs))
    text('Title',.15,.02,'AURORA MIXED PRINT CHECK',17,True)
    text('Rule',.15,.36,'Filled artwork engraves. Hairline strokes cut, regardless of color.',9)
    text('A heading',.15,.64,'A | BITMAP: GRAYSCALE + DETAIL',10,True)
    shape('bitmap','A grayscale bitmap',.15,.88,width=3,height=250/167,file='raster-detail.bmp')
    text('A legend',.15,2.43,'256-level ramp / 8 steps / shaded sphere / line pairs',7.5)
    text('B heading',3.55,.64,'B | NATIVE TEXT + FILLS',10,True)
    text('14 pt text',3.55,.91,'AaBb 0123 O0B8',14,True)
    text('10 pt text',3.55,1.21,'10 pt - counters and gaps',10)
    text('8 pt text',3.55,1.46,'8 pt - ABC abc 123',8)
    text('6 pt text',3.55,1.66,'6 pt - small native text',6)
    shape('rect','B solid filled square',3.6,1.92,width=.22,height=.22,fill=True)
    shape('ellipse','B solid filled circle',4.0,1.92,width=.22,height=.22,fill=True)
    shape('rect','B thick outlined rectangle',3.6,2.24,width=.62,height=.28,points=1)
    for index,points in enumerate((.5,1,2)):
        y=1.95+.23*index
        text('Thick line label '+str(points),4.42,y-.04,str(points)+' pt',8)
        shape('line','B raster line '+str(points)+' pt',4.95,y,x2=5.85,y2=y,points=points)
    text('C heading',.15,2.73,'C | HAIRLINE CUTS - FIVE PATHS',10,True)
    for name,x,value in [('C1 label',.15,'BLACK: 1 in square'),('C2 label',1.53,'RED: 0.5 in'),
                         ('C3 label',2.65,'BLUE: 0.5 in'),('C4 label',3.68,'BLACK: open arc'),('C5 label',4.94,'BLACK: open line')]:
        text(name,x,3.00,value,7.5)
    shape('rect','C1 black hairline square',.15,3.22,width=1,height=1,hairline=True,color=[0,0,0])
    shape('rect','C2 red hairline square',1.60,3.42,width=.5,height=.5,hairline=True,color=[255,0,0])
    shape('ellipse','C3 blue hairline circle',2.70,3.42,width=.5,height=.5,hairline=True,color=[0,0,255])
    shape('arc','C4 black hairline arc',3.70,3.30,width=.76,height=.76,hairline=True,color=[0,0,0])
    shape('polyline','C5 black hairline open line',4.95,3.42,vertices=[[4.95,3.42],[5.38,3.87],[5.85,3.42]],hairline=True,color=[0,0,0])
    text('Expected result',1.42,4.12,'A + B ENGRAVE  |  C1-C5 CUT',10,True)
    text('Modes',.15,4.39,'Both: A+B+C    Raster Only: A+B    Vector Only: C1-C5',8)
    spec={'title':'Aurora-Mixed-Test','page_inches':[30,18],'origin_inches':[1,1],
          'material_coverage_inches':[.9,.9,7.1,5.7],
          'bitmap_pixels':[501,250],'bitmap_sha256':hashlib.sha256((destination/'raster-detail.bmp').read_bytes()).hexdigest(),
          'expected_cut_paths':5,'shapes':shapes,'print_called':False,'physical_device_io':False}
    (destination/'artwork-spec.json').write_text(json.dumps(spec,indent=2),encoding='utf-8')
    (destination/'READ-ME.txt').write_text('''AURORA MIXED PRINT CHECK

Open Aurora-Mixed-Test.cdr. The PNG is a visual reference; use the CDR to print.
This graphic exercises the currently implemented raster/vector print path.

Use 30 x 18 inch media, 100% / As in document, 167 DPI.
Select Both Raster and Vector for the combined check.
Keep Dither Bitmaps Off and Autostart Off for this comparison.
Confirm material-appropriate power, speed and PPI before enabling laser printing.
Previous comparison settings were raster30ips/54%, vector1ips/15%/1000PPI;
these are comparison values, not a preset for every material.

Expected in Both mode:
A: Bitmap engraves: grayscale ramp, eight steps, smooth sphere, fine stripes/checkers.
B: Native text at14/10/8/6pt, solid fills, thick rectangle and0.5/1/2pt lines engrave.
C: Exactly FIVE hairline paths cut: black1-inch square, red0.5-inch square,
blue0.5-inch circle, black open arc, black open polyline. None should be raster marks.
The arc and polyline are intentionally open; the other three paths are closed.

Raster Only should engrave A+B and omit C. Vector Only should cut C and omit A+B.
These mode choices would be separate deliberate prints, not automatic repetitions.
Global bitmap dithering, color profiles, focus and rotary/stamp settings are not
validated by this artwork. This tests grayscale, bitmap detail, native text/fills,
stroke-width classification, color-independent cuts, open/closed curves, and scale.

The artwork is near1 inch from the bed's left/top. Material coverage:
x0.9-7.1 inches from left, y0.9-5.7 inches from top.
No print or physical laser command was issued while creating this file.
''',encoding='utf-8')
    return destination


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('destination',type=Path)
    print(build(parser.parse_args().destination))
