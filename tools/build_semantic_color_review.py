"""Validate semantic native coverage and export marked color-review drafts.

This never prints or sends a job. Only the experimental schema-3 flat-brush
reader is accepted; the production print path continues to hold UseColors.
"""
import argparse
from array import array
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from aurora_jobserver.artwork import local_file, read_json
from aurora_jobserver.classic_settings import RGB
from aurora_jobserver.color_settings import ColorProcess
from aurora_jobserver.color_rasters import (CoverageLayer,ExposureSurface,FlatColorSurface,
    plan_color_layers,plan_color_rasters,plan_global_rasters,encode_raster_draft)
from aurora_jobserver.jbs import DRAFT_MARKER,MAX_JOB_BYTES
from aurora_jobserver.printer_settings import settings_from_xps
from tools.compare_preference_jobs import decode,summary,png_gray


REVIEW_WARNING='Experimental color review: nonwhite coverage cannot distinguish white artwork; per-color output remains held.'


def _shape(record):
    if not isinstance(record,dict):raise ValueError('Expected coverage metadata')
    x,y,w,h=(record.get(k) for k in ('x_pixels','y_pixels','width','height'))
    if (any(type(v) is not int for v in (x,y,w,h)) or not 0<=x<5010 or not 0<=y<3006
            or not 1<=w<=5010-x or not 1<=h<=3006-y):
        raise ValueError('Invalid native layer dimensions')
    return x,y,w,h


def _blob(root,name,digest,size):
    path=local_file(root,name)
    if path.stat().st_size!=size:raise ValueError('Native snapshot length changed')
    data=path.read_bytes()
    if not isinstance(digest,str) or hashlib.sha256(data).hexdigest()!=digest:
        raise ValueError('Native snapshot hash changed')
    return data


def _exposure(root,record,*,require_neutral=True):
    x,y,w,h=_shape(record)
    if (record.get('encoding')!='exposure-u8-row-major'
            or type(record.get('colored_pixels')) is not int or record['colored_pixels']<0
            or (require_neutral and record['colored_pixels']!=0)):
        raise ValueError('Expected neutral semantic coverage')
    return ExposureSurface(x,y,w,h,_blob(root,record.get('file'),record.get('sha256'),w*h))


def load_native_layers(directory):
    root=Path(directory).resolve();doc=read_json(root/'document.json')
    if (doc.get('schema_version')!=3 or doc.get('status')!='offline_color_review_only'
            or doc.get('dpi')!=167 or doc.get('raster_grid')!='coreldraw-xp-draft'
            or doc.get('text_rendering')!='outline-aliased' or len(doc.get('pages',[]))!=1):
        raise ValueError('Expected the experimental single-page 167-DPI Corel color review')
    source=local_file(root,doc.get('source_file'))
    if not 0<source.stat().st_size<=MAX_JOB_BYTES or hashlib.sha256(source.read_bytes()).hexdigest()!=doc.get('source_sha256'):
        raise ValueError('Native source snapshot changed')
    page=doc['pages'][0]
    if page.get('review_reasons')!=[REVIEW_WARNING]:
        raise ValueError('Other unresolved native artwork review reasons remain')
    semantic=page.get('color_layers')
    if (not isinstance(semantic,dict) or semantic.get('status')!='prepared_offline_flat_color_layers'
            or semantic.get('encoding')!='source-brush-coverage-u8-review-only'
            or semantic.get('unsupported_reason') is not None or type(semantic.get('white_paint_excluded')) is not bool):
        raise ValueError('Semantic source content remains unsupported')
    items=semantic.get('layers')
    if not isinstance(items,list) or not 1<=len(items)<=32:raise ValueError('Invalid semantic layer count')
    layers=[];total=0
    for item in items:
        if not isinstance(item,dict) or not re.fullmatch(r'#FF[0-9A-F]{6}',item.get('color','')):
            raise ValueError('Invalid semantic brush identity')
        rgb=int(item['color'][3:],16)
        expected=RGB.index(rgb) if rgb in RGB else -1
        if type(item.get('palette_index')) is not int or item['palette_index']!=expected:
            raise ValueError('Semantic brush and palette index disagree')
        image=_exposure(root,item.get('coverage'));total+=len(image.pixels)
        if total>50_000_000:raise ValueError('Semantic layers exceed the pixel budget')
        layers.append(CoverageLayer(rgb,image))
    native=page.get('color_raster_review');x,y,w,h=_shape(native)
    if native.get('encoding')!='rgb-u8-on-opaque-white-review-only' or native.get('coverage_encoding')!='nonwhite-u8-review-only':
        raise ValueError('Unsupported native RGB snapshot')
    rgb=_blob(root,native.get('file'),native.get('sha256'),w*h*3)
    coverage=_blob(root,native.get('coverage_file'),native.get('coverage_sha256'),w*h)
    if any(coverage[i]!=(0 if rgb[i*3:i*3+3]==b'\xff'*3 else 255) for i in range(w*h)):
        raise ValueError('Nonwhite diagnostic coverage does not match RGB')
    return doc,tuple(layers),FlatColorSurface(x,y,w,h,rgb,coverage)


def reconstruct_rgb(layers,surface):
    """Independently recompose visible semantic color weights onto white."""
    loss=array('I',[0])*(surface.width*surface.height*3)
    for layer in layers:
        channels=[(layer.rgb>>shift)&255 for shift in (16,8,0)]
        image=layer.image
        for pos,weight in enumerate(image.pixels):
            if not weight:continue
            y,x=divmod(pos,image.width)
            x+=image.x_pixels-surface.x_pixels;y+=image.y_pixels-surface.y_pixels
            if not 0<=x<surface.width or not 0<=y<surface.height:
                raise ValueError('Visible semantic coverage leaves the native RGB bounds')
            target=(y*surface.width+x)*3
            for channel,value in enumerate(channels):loss[target+channel]+=(255-value)*weight
    rgb=bytes(max(0,min(255,255-(value+127)//255)) for value in loss)
    errors=Counter(abs(a-b) for a,b in zip(rgb,surface.rgb))
    return rgb,dict(max_channel_error=max(errors),differing_channels=sum(n for v,n in errors.items() if v),
        channel_count=len(rgb),error_histogram=dict(errors))


def build(directory,destination,palette):
    root=Path(directory).resolve();destination=Path(destination)
    if destination.exists():raise ValueError('Choose a fresh semantic review directory')
    doc,layers,surface=load_native_layers(root)
    reconstructed,appearance=reconstruct_rgb(layers,surface)
    if appearance['max_channel_error']>2:
        raise ValueError('Semantic layers do not reproduce the native RGB appearance')
    enabled=plan_color_layers(layers,palette)
    old=plan_color_rasters(surface,palette)
    old_count=sum(sum(v!=0 for v in region.image.pixels) for region in old.regions)
    new_count=sum(sum(v!=0 for v in region.image.pixels) for region in enabled.regions)
    # Palette fixture is explicit. The original global capture options are only
    # used for the ordinary grayscale comparison, never changed in the spooler.
    settings=settings_from_xps(local_file(root,doc['source_file']))
    process=settings['process_settings']
    global_plan=plan_global_rasters(_exposure(root,doc['pages'][0]['exposure'],require_neutral=False),
        ColorProcess(process['raster_speed_native'],process['raster_power_percent'],process['vector_ppi']))
    plans={'global':global_plan,'enabled':enabled,'paused':plan_color_layers(layers,palette,pause_colors=True)}
    disabled=[dict(item) for item in palette];disabled[9]['Enabled']=False
    plans['disabled-blue']=plan_color_layers(layers,disabled)
    outputs={};results=[]
    for case,plan in plans.items():
        raw,cg=encode_raster_draft(plan,'SemanticColorReview')
        a,b=decode(raw),decode(cg)
        if a['commands']!=b['commands'] or len(a['rasters'])!=len(b['rasters']):
            raise ValueError('CG color commands/region count changed')
        for source,actual,region in zip(a['rasters'],b['rasters'],plan.regions):
            for field in ('pixels','origin_units','origin_label','resolution_dpi','settings','width','height'):
                if source[field]!=actual[field]:raise ValueError('CG color coverage changed')
            if actual['pixels']!=region.image.pixels:raise ValueError('Native edge coverage changed')
        if not raw.startswith(b'!ZX\r'+DRAFT_MARKER+b'\r') or a['autostart']:
            raise ValueError('Semantic draft guard failed')
        outputs[case]=(raw,cg,b)
        results.append(dict(case=case,mask_encoding=plan.mask_encoding,raster_count=len(plan.regions),
            unmatched_pixels=plan.unmatched_pixels,cg_preserves_native_samples=True,
            raw_draft_sha256=hashlib.sha256(raw).hexdigest(),cg_draft_sha256=hashlib.sha256(cg).hexdigest()))
    destination.mkdir(parents=True,exist_ok=False)
    for case,(raw,cg,decoded) in outputs.items():
        (destination/(case+'.raw.jbs.draft')).write_bytes(raw)
        (destination/(case+'.cg.jbs.draft')).write_bytes(cg)
        (destination/(case+'.decoded.json')).write_text(json.dumps(summary(decoded),indent=2)+'\n')
        for index,raster in enumerate(decoded['rasters']):
            preview=raster['pixels'].translate(bytes(255-x for x in range(256)))
            (destination/f'{case}-layer-{index:02d}.png').write_bytes(png_gray(raster['width'],raster['height'],preview))
    (destination/'reconstructed.rgb').write_bytes(reconstructed)
    (destination/'palette.json').write_text(json.dumps(palette,indent=2)+'\n')
    result=dict(state='semantic_color_coverage_preserves_native_appearance',source_sha256=doc['source_sha256'],
        appearance=appearance,old_matched_pixels=old_count,semantic_matched_pixels=new_count,
        matched_edge_pixels_recovered=new_count-old_count,cases=results,
        explicit_offline_palette_fixture=True,production_use_colors_enabled=False,physical_device_io=False,
        limitations=['White paint excluded','Bitmap/gradient/transparency processing unsupported',
            'Semantic X7 edge exposures are review drafts; no new physical result'])
    (destination/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('intake',type=Path);parser.add_argument('destination',type=Path)
    parser.add_argument('--palette',required=True,type=Path)
    args=parser.parse_args();palette=read_json(args.palette)
    if isinstance(palette,dict):palette=palette['palette']
    result=build(args.intake,args.destination,palette)
    print(json.dumps({k:result[k] for k in ('state','appearance','matched_edge_pixels_recovered')}))


if __name__=='__main__':main()
