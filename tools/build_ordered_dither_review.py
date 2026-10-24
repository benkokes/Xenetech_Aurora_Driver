"""Build marked offline ordered-dither reviews from immutable saved references.

No printing, renderer launch, device API, ticket edit or live-enabling option.
The phase candidate relates each raster origin to the captured reference origin;
this remains an explicitly recorded hypothesis, not automatic print support.
"""
import argparse
import hashlib
import json
from pathlib import Path

from aurora_jobserver.artwork import ProcessSettings, Scene, load_scene
from aurora_jobserver.corel_layout import COREL_GRID
from aurora_jobserver.jbs import DRAFT_MARKER, MAX_JOB_BYTES
from aurora_jobserver.ordered_dither import encode_ordered_draft
from aurora_jobserver.wire import raster_plan
from tools.compare_preference_jobs import decode, png_gray, summary


REFERENCE_ORIGIN_PIXELS = (169, 171)
REFERENCES = {
    'grayscale': {
        'baseline': ('grayscale-probe/gray-baseline/Default.jbs', '3ae52ff9eef953d9f783ea4b345fdc1d08915916d3441fbb20978b90035cae52'),
        'Ordered4': ('grayscale-probe/gray-ordered4/Default.jbs', 'eeebb6553abfa382282a6304351202bb73247a60bef3b1209b99ddc95484eb75'),
        'Ordered8': ('grayscale-probe/gray-ordered8/Default.jbs', 'f273e21c5c7dbf565db1a320a89091df0d69197baaaa4041806f54dde4524bdc'),
    },
    'asymmetric': {
        'baseline': ('bitmap-reference/Default.jbs', 'f2407eb8860a8af234a19af28a2d27a03f2f900aaf2ebe115c415a37c6714eea'),
        'Ordered4': ('dither-ordered4/Default.jbs', '51abc45e2b1be18809cffe6548ebe71906425baf86aa9c8063a44467b637bf97'),
        'Ordered8': ('dither-ordered8/Default.jbs', '51abc45e2b1be18809cffe6548ebe71906425baf86aa9c8063a44467b637bf97'),
    },
}
FIELDS = ('pixels', 'width', 'height', 'origin_units', 'origin_label', 'resolution_dpi', 'settings')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def phase(scene, size):
    r = scene.page['exposure']
    return tuple((r[key]-origin) % size for key, origin in zip(('x_pixels','y_pixels'), REFERENCE_ORIGIN_PIXELS))


def process_from_reference(raster):
    settings = raster['settings']
    return ProcessSettings.parse({'schema_version':1, 'units':'driver-native',
        'raster_speed_native':int(settings['speed']), 'raster_power_percent':settings['power'],
        'vector_speed_native':1000, 'vector_power_percent':15, 'vector_ppi':1000})


def scene_from_reference(job):
    if job['autostart'] or job['draft'] or len(job['rasters']) != 1 or job['vector_paths']:
        raise ValueError('Expected a single offline Raster Only reference')
    raster = job['rasters'][0]
    x, y = raster['origin_units']
    if raster['resolution_dpi'] != [167,167] or x % 6 or y % 6 or raster['origin_label'] != 'UL':
        raise ValueError('Unexpected reference grid or scan direction')
    return Scene({'dpi':167,'raster_grid':COREL_GRID}, {'exposure':{
        'width':raster['width'], 'height':raster['height'], 'x_pixels':int(x/6), 'y_pixels':int(y/6)}},
        raster['pixels'], ())


def save_draft(destination, label, raw, cg):
    decoded = decode(cg)
    if not decoded['draft'] or decoded['autostart']:
        raise ValueError('Only marked non-autostart drafts may be written')
    for data in (raw, cg):
        try:
            raster_plan(data, r'c:\xfiles\jbs\Convert\Default.jbs')
        except ValueError as error:
            if 'uncalibrated draft' not in str(error):
                raise
        else:
            raise ValueError('Draft unexpectedly accepted by ordinary wire planning')
    (destination/(label+'.raw.jbs.draft')).write_bytes(raw)
    (destination/(label+'.cg.jbs.draft')).write_bytes(cg)
    raster = decoded['rasters'][0]
    image = bytes(255-value for value in raster['pixels'])
    (destination/(label+'.png')).write_bytes(png_gray(raster['width'],raster['height'],image))
    return {'raw_draft_sha256':digest(raw), 'cg_draft_sha256':digest(cg), 'decoded':summary(decoded),
            'ordinary_wire_plan_rejected':True}


def build(reference_root, destination, *, x7_intake=None):
    reference_root, destination = Path(reference_root), Path(destination)
    if destination.exists():
        raise ValueError('Choose a fresh directory; previous evidence is preserved')
    # Read and hash all independent references before creating any output.
    jobs = {}
    for artwork, records in REFERENCES.items():
        jobs[artwork] = {}
        for mode, (name, expected) in records.items():
            with (reference_root/name).open('rb') as stream:
                data = stream.read(MAX_JOB_BYTES+1)
            if digest(data) != expected:
                raise ValueError('Reference hash changed: '+name)
            jobs[artwork][mode] = data
    x7 = load_scene(x7_intake) if x7_intake is not None else None
    destination.mkdir(parents=True, exist_ok=False)
    report = {'state':'offline_ordered_drafts_match_xp', 'marked_drafts_only':True,
        'physical_device_io':False, 'production_dither_enabled':False,
        'phase_rule':'CANDIDATE: raster-origin difference from (169,171) on the 167-DPI grid; arbitrary-origin validation pending',
        'xp_reference_cases':[], 'x7_review_cases':[]}
    for artwork, records in jobs.items():
        baseline = decode(records['baseline'])
        scene = scene_from_reference(baseline)
        process = process_from_reference(baseline['rasters'][0])
        for mode, size in [('Ordered4',4),('Ordered8',8)]:
            px, py = phase(scene,size)
            raw, cg = encode_ordered_draft(scene,process,mode,phase_x=px,phase_y=py,
                title=baseline['title'],output_mode='raster-only')
            # The unmarked comparison exists in memory only, never as an artifact.
            if raw.replace(DRAFT_MARKER+b'\r',b'',1) != records[mode]:
                raise ValueError('Complete raw output differs from XP: '+artwork+' '+mode)
            expected, actual = decode(records[mode]), decode(cg)
            if actual['commands'] != expected['commands']:
                raise ValueError('Compressed commands differ from XP')
            for field in FIELDS:
                if actual['rasters'][0][field] != expected['rasters'][0][field]:
                    raise ValueError('Compressed XP field changed: '+field)
            result = save_draft(destination,artwork+'-'+mode,raw,cg)
            result.update(artwork=artwork,method=mode,phase=[px,py],
                complete_raw_matches_xp_except_draft_marker=True,reference_sha256=digest(records[mode]))
            report['xp_reference_cases'].append(result)
    if x7 is not None:
        # Keep all X7 source samples. Do not replace them with XP-rendered pixels.
        process = process_from_reference(decode(jobs['grayscale']['baseline'])['rasters'][0])
        raster = x7.page['exposure']
        for mode, size in [('Ordered4',4),('Ordered8',8)]:
            px, py = phase(x7,size)
            raw, cg = encode_ordered_draft(x7,process,mode,phase_x=px,phase_y=py,title='X7'+mode)
            actual = decode(cg)
            if len(actual['vector_paths']) != len(x7.paths):
                raise ValueError('X7 vector paths changed')
            for a,b in zip(actual['vector_paths'], x7.paths):
                if a['points'] != [[float(x),float(y)] for x,y in b]:
                    raise ValueError('X7 vector coordinates changed')
            r = actual['rasters'][0]
            if (r['width'],r['height'],r['origin_units']) != (raster['width'],raster['height'],
                    [raster['x_pixels']*6,raster['y_pixels']*6]):
                raise ValueError('X7 exposure rectangle changed')
            result = save_draft(destination,'x7-'+mode,raw,cg)
            result.update(method=mode,phase=[px,py],source_exposure_sha256=digest(x7.exposure),
                source_document_sha256=x7.manifest['source_sha256'],vector_coordinates_unchanged=True,
                validation='X7-source preview; not pixel-equivalence to XP rendering or physical validation')
            report['x7_review_cases'].append(result)
    (destination/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference_root',type=Path)
    parser.add_argument('destination',type=Path)
    parser.add_argument('--x7-intake',type=Path)
    args = parser.parse_args()
    report = build(args.reference_root,args.destination,x7_intake=args.x7_intake)
    print(json.dumps({key:len(report[key]) for key in ('xp_reference_cases','x7_review_cases')}))


if __name__=='__main__':main()
