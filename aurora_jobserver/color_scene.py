"""Validate native opaque-brush color coverage and all-color hairline paths."""
from array import array
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

from .artwork import Scene, local_file, number, read_json
from .classic_settings import RGB
from .color_rasters import CoverageLayer, ExposureSurface
from .corel_layout import COREL_GRID, COREL_HAIRLINE_MAX_MM, from_manifest


NATIVE_REVIEW_WARNING='Experimental color review: nonwhite coverage cannot distinguish white artwork; per-color output remains held.'


@dataclass(frozen=True)
class ColorScene:
    manifest: dict
    page: dict
    layers: tuple
    vector_scene: Scene
    appearance_error: int

    @property
    def paths(self):return self.vector_scene.paths


def _shape(record):
    if not isinstance(record,dict):raise ValueError('Missing native color bounds')
    x,y,w,h=(record.get(k) for k in ('x_pixels','y_pixels','width','height'))
    if (any(type(v) is not int for v in (x,y,w,h)) or not 0<=x<5000 or not 0<=y<3000
            or not 1<=w<=5000-x or not 1<=h<=3000-y):
        raise ValueError('Invalid native color bounds')
    return x,y,w,h


def _blob(root,name,digest,size):
    path=local_file(root,name)
    if path.stat().st_size!=size:raise ValueError('Native color snapshot length changed')
    data=path.read_bytes()
    if not isinstance(digest,str) or hashlib.sha256(data).hexdigest()!=digest:
        raise ValueError('Native color snapshot hash changed')
    return data


def _coverage(root,record):
    x,y,w,h=_shape(record)
    if (record.get('encoding')!='exposure-u8-row-major' or record.get('colored_pixels')!=0
            or type(record.get('colored_pixels')) is not int):
        raise ValueError('Expected neutral brush coverage')
    pixels=_blob(root,record.get('file'),record.get('sha256'),w*h)
    if not any(pixels):raise ValueError('Empty brush coverage')
    return ExposureSurface(x,y,w,h,pixels)


def _appearance(root,layers,record):
    if not layers:
        if record is not None:raise ValueError('Visible raster without semantic color coverage')
        return 0
    x,y,w,h=_shape(record)
    if (record.get('encoding')!='rgb-u8-on-opaque-white-review-only'
            or record.get('coverage_encoding')!='nonwhite-u8-review-only'):
        raise ValueError('Unknown native RGB snapshot encoding')
    rgb=_blob(root,record.get('file'),record.get('sha256'),w*h*3)
    covered=_blob(root,record.get('coverage_file'),record.get('coverage_sha256'),w*h)
    if any(covered[i]!=(0 if rgb[i*3:i*3+3]==b'\xff'*3 else 255) for i in range(w*h)):
        raise ValueError('Native RGB diagnostic coverage changed')
    loss=array('I',[0])*(w*h*3)
    for layer in layers:
        channels=[(layer.rgb>>shift)&255 for shift in (16,8,0)]
        for pos,weight in enumerate(layer.image.pixels):
            if not weight:continue
            yy,xx=divmod(pos,layer.image.width)
            xx+=layer.image.x_pixels-x;yy+=layer.image.y_pixels-y
            if not 0<=xx<w or not 0<=yy<h:
                raise ValueError('Semantic color coverage leaves the native RGB bounds')
            p=(yy*w+xx)*3
            for channel,value in enumerate(channels):loss[p+channel]+=(255-value)*weight
    error=max(abs(actual-max(0,min(255,255-(value+127)//255))) for actual,value in zip(rgb,loss))
    if error>2:raise ValueError('Color coverage does not preserve the native X7 appearance')
    return error


def load_color_scene(directory):
    root=Path(directory).resolve()
    doc=read_json(root/'document.json')
    if (doc.get('schema_version')!=3 or doc.get('status')!='offline_color_review_only'
            or doc.get('dpi')!=167 or doc.get('render_dpi')!=167
            or doc.get('raster_grid')!=COREL_GRID or doc.get('text_rendering')!='outline-aliased'
            or doc.get('tiled_raster') is not False or doc.get('cut_color') is not None
            or doc.get('max_cut_width_mm')!=COREL_HAIRLINE_MAX_MM
            or doc.get('flatten_tolerance_mm')!=.01 or len(doc.get('pages',[]))!=1):
        raise ValueError('Expected the bounded 167-DPI all-color hairline/semantic reader profile')
    source=local_file(root,doc.get('source_file'))
    if not 0<source.stat().st_size<=64*1024*1024 or hashlib.sha256(source.read_bytes()).hexdigest()!=doc.get('source_sha256'):
        raise ValueError('Native color source integrity check failed')
    page=doc['pages'][0]
    if page.get('review_reasons')!=[NATIVE_REVIEW_WARNING]:
        raise ValueError('Unresolved color artwork: '+str(page.get('review_reasons')))
    width=number(page.get('width_mm'),'color page width',.001,762)
    height=number(page.get('height_mm'),'color page height',.001,457.2)
    layout=from_manifest(doc,page)
    if (page.get('pixel_width'),page.get('pixel_height'))!=layout.surface:
        raise ValueError('Color page surface differs from the Corel profile')
    semantic=page.get('color_layers')
    if (not isinstance(semantic,dict) or semantic.get('status')!='prepared_offline_flat_color_layers'
            or semantic.get('encoding')!='source-brush-coverage-u8-review-only'
            or semantic.get('unsupported_reason') is not None
            or type(semantic.get('white_paint_excluded')) is not bool):
        raise ValueError('Per-color raster requires opaque solid fills/text; bitmap, gradient or transparency is unsupported')
    records=semantic.get('layers')
    if not isinstance(records,list) or len(records)>32:raise ValueError('Invalid native color layer count')
    layers=[];seen=set();total=0
    for record in records:
        if not isinstance(record,dict) or not re.fullmatch(r'#FF[0-9A-F]{6}',record.get('color','')):
            raise ValueError('Invalid native brush identity')
        rgb=int(record['color'][3:],16)
        if rgb==0xffffff or rgb in seen:raise ValueError('Duplicate or unclassified white brush layer')
        seen.add(rgb)
        index=RGB.index(rgb) if rgb in RGB else -1
        if type(record.get('palette_index')) is not int or record['palette_index']!=index:
            raise ValueError('Native brush/palette identity mismatch')
        image=_coverage(root,record.get('coverage'));total+=len(image.pixels)
        if total>50_000_000:raise ValueError('Color coverage exceeds the pixel budget')
        layers.append(CoverageLayer(rgb,image))
    appearance=_appearance(root,layers,page.get('color_raster_review'))
    cuts=page.get('cuts')
    if not isinstance(cuts,list) or len(cuts)>100000:raise ValueError('Invalid native color cutting paths')
    paths=[];point_count=0
    for cut in cuts:
        if (not isinstance(cut,dict) or type(cut.get('closed')) is not bool
                or not re.fullmatch(r'#FF[0-9A-F]{6}',cut.get('color',''))):
            raise ValueError('Invalid native hairline identity')
        number(cut.get('width_mm'),'color hairline width',.0000001,COREL_HAIRLINE_MAX_MM)
        points=cut.get('points_mm')
        if not isinstance(points,list) or len(points)<2:raise ValueError('Invalid native color path')
        point_count+=len(points)
        if point_count>2_000_000:raise ValueError('Color paths exceed the point budget')
        path=[]
        for point in points:
            if not isinstance(point,list) or len(point)!=2:raise ValueError('Invalid native color point')
            x=number(point[0],'color cut X',0,width);y=number(point[1],'color cut Y',0,height)
            path.append((layout.point(x,0),layout.point(y,1)))
        if cut['closed'] and path[-1]!=path[0]:path.append(path[0])
        if len(set(path))<2:raise ValueError('Collapsed native color path')
        paths.append(tuple(path))
    vector_scene=Scene(dict(doc,cut_color='any'),dict(page,exposure=None),b'',tuple(paths))
    return ColorScene(doc,page,tuple(layers),vector_scene,appearance)
