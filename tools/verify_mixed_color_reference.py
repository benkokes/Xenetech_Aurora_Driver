"""Verify one independent XP mixed-color capture, without any device I/O."""
import argparse
import hashlib
import json
from pathlib import Path

from aurora_jobserver.color_rasters import plan_color_rasters,encode_raster_draft
from aurora_jobserver.color_vectors import plan_vectors
from aurora_jobserver.jbs import DRAFT_MARKER,prepare
from tools.build_color_raster_review import reference_palette,reference_surface
from tools.compare_preference_jobs import decode,summary


ROOT=Path(__file__).resolve().parents[1]
REFERENCE=ROOT/'captures/xp-color-mixed-preferences-20261022/inbox/Default.jbs'
EXPECTED='e2aeadb8e62baaa4d988c6fd4da19abbee2f118e01b968a64bb34cde2d61aa5e'
BASE=ROOT/'captures/xp-color-preferences-20261019/color-global-2505-1735/inbox/Default.jbs'


def verify(destination):
    destination=Path(destination)
    if destination.exists():raise ValueError('Choose a fresh evidence directory')
    source=REFERENCE.read_bytes()
    if hashlib.sha256(source).hexdigest()!=EXPECTED:raise ValueError('Independent XP reference changed')
    baseline=BASE.read_bytes()
    if hashlib.sha256(baseline).hexdigest()!='e63a9df9789326f320e4b5fb9c8bc3b0cd4d20acd5ca9220c5667c628e1d6d27':
        raise ValueError('Independent previous vector geometry changed')
    # The independently saved mixed CDR moved only the five outlines down .5in.
    geometry=ROOT/'runtime/xp-color-mixed-preferences-20261020/package/corel11-document-verification.json'
    if hashlib.sha256(geometry.read_bytes()).hexdigest()!='b3081bab3ef6c1fc1b21bf79487bc76c1eabe7bb6114a0d3780f06b081dfb545':
        raise ValueError('Prepared Corel 11 geometry evidence changed')
    paths=tuple(tuple((p[0],p[1]+504) for p in path['points']) for path in decode(baseline)['vector_paths'])
    colors=(0x0000ff,0xff0000,0x0000ff,0xff0000,0xff8000)
    table=reference_palette()
    # This actual capture omits Blue in both raster and vector output. Record
    # the observed case rather than claiming the requested all-enabled case ran.
    table[9]['Enabled']=False
    raster=plan_color_rasters(reference_surface(),table)
    vector=plan_vectors(paths,colors,table,sort_colors=True)
    raw,_=encode_raster_draft(raster,'Default.jbs')
    footer=b'PU\r0. 0. V\rEND_PLOT\r'
    assert raw.endswith(footer)
    raw=raw[:-len(footer)]+vector.commands+b'0. 0. V\rEND_PLOT\r'
    if raw.replace(DRAFT_MARKER+b'\r',b'',1)!=source:
        a,b=decode(raw),decode(source)
        raise ValueError('XP mixed raw output differs: '+str({'candidate':a['commands'],'xp':b['commands']}))
    cg=prepare(raw,allow_draft=True).data
    actual,expected=decode(cg),decode(source)
    assert actual['commands']==expected['commands']
    assert actual['vector_paths']==expected['vector_paths']
    for a,b in zip(actual['rasters'],expected['rasters']):
        for field in ('pixels','width','height','origin_units','origin_label','resolution_dpi','settings'):
            assert a[field]==b[field],field
    destination.mkdir(parents=True)
    (destination/'job.raw.jbs.draft').write_bytes(raw)
    (destination/'job.cg.jbs.draft').write_bytes(cg)
    report={'state':'independent_xp_mixed_boundary_matches','reference_sha256':EXPECTED,
        'actual_xp_capture':True,'complete_raw_matches_except_draft_marker':True,
        'raw_bytes':len(source),'raster_regions':len(actual['rasters']),'vector_paths':len(actual['vector_paths']),
        'cg_commands_geometry_and_pixels_preserved':True,'physical_device_io':False,
        'observed_case':'Blue omitted; Black/Red raster and Red/unmatched vector paths',
        'requested_all_enabled_case':False,
        'note':'Legacy White fallback speed 100 ips is identification evidence only, not permitted by production vector limits.',
        'decoded':summary(actual)}
    (destination/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('destination',type=Path)
    result=verify(p.parse_args().destination)
    print(json.dumps({k:v for k,v in result.items() if k!='decoded'}))
