"""Review one immutable full-preferences print as MARKED offline color drafts.

This standalone tool is deliberately absent from the JobServer/print service.
It has no equipment endpoint, spool submission, live switch or unmarked output.
Legacy scalar-only captures require the separate explicit-fixture review tool.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

from aurora_jobserver.artwork import ProcessSettings, number
from aurora_jobserver.classic_settings import ensure_supported
from aurora_jobserver.color_drafts import encode_color_draft
from aurora_jobserver.color_rasters import plan_color_layers, encode_raster_draft
from aurora_jobserver.color_settings import parse_palette
from aurora_jobserver.corel_layout import from_manifest
from aurora_jobserver.jbs import DRAFT_MARKER, MAX_JOB_BYTES, prepare
from aurora_jobserver.printer_settings import settings_from_xps
from tools.build_semantic_color_review import load_native_layers, reconstruct_rgb
from tools.compare_preference_jobs import decode, summary, png_gray


def review_settings(source):
    """Bound this marked review to the measured 167-DPI color combinations."""
    settings = settings_from_xps(source)
    preferences = settings.get('classic_preferences')
    if settings.get('schema_version') != 2 or not isinstance(preferences, dict):
        raise ValueError('A complete job-attached preferences snapshot is required; scalar-only capture is insufficient')
    if (preferences['UseColors'] is not True or any(reason not in ('UseColors','ColorRasterPauseColors') for reason in settings['held_features'])
            or settings['laser_dpi'] != 167 or settings['autostart'] is not False
            or preferences['InvertRaster'] or preferences['BottomUp']
            or settings['output_mode'] not in ('raster-only', 'raster-and-vector')):
        raise ValueError('Offline color review requires 167 DPI, UseColors only, Autostart Off and no unverified combinations')
    # A held production job otherwise skips its scalar process validation.
    ProcessSettings.parse(settings['process_settings'])
    parse_palette(preferences['Colors'])
    return settings


def native_paths(doc):
    """Validate native thin-vector extraction and map it using the reference fit."""
    page = doc['pages'][0]
    width = number(page.get('width_mm'), 'page width', .001, 762)
    height = number(page.get('height_mm'), 'page height', .001, 457.2)
    if (doc.get('render_dpi') != 167 or doc.get('tiled_raster') is not False
            or doc.get('cut_color') is not None or doc.get('max_cut_width_mm') != .2
            or doc.get('flatten_tolerance_mm') != .01
            or page.get('has_visible_artwork') is not True
            or type(page.get('pixel_width')) is not int or page['pixel_width'] != 5000
            or type(page.get('pixel_height')) is not int or page['pixel_height'] != 3000):
        raise ValueError('Native color scene differs from the bounded Corel review profile')
    layout = from_manifest(doc, page)
    cuts = page.get('cuts')
    if not isinstance(cuts, list) or len(cuts) > 100000:
        raise ValueError('Expected bounded native cutting paths')
    paths, colors, total = [], [], 0
    for cut in cuts:
        if (not isinstance(cut, dict) or type(cut.get('closed')) is not bool
                or not isinstance(cut.get('color'), str)
                or not re.fullmatch(r'#FF[0-9A-F]{6}', cut['color'])):
            raise ValueError('Native cutting identity is invalid')
        number(cut.get('width_mm'), 'cut width', .0000001, .2)
        points = cut.get('points_mm')
        if not isinstance(points, list) or len(points) < 2:
            raise ValueError('Invalid native cutting path')
        total += len(points)
        if total > 2000000:
            raise ValueError('Too many native cutting points')
        path = []
        for point in points:
            if not isinstance(point, list) or len(point) != 2:
                raise ValueError('Invalid native cutting point')
            x = number(point[0], 'cut X', 0, width)
            y = number(point[1], 'cut Y', 0, height)
            path.append((layout.point(x, 0), layout.point(y, 1)))
        if cut['closed'] and path[-1] != path[0]:
            path.append(path[0])
        if len(set(path)) < 2:
            raise ValueError('Native cut collapses after coordinate rounding')
        paths.append(tuple(path))
        colors.append(int(cut['color'][3:], 16))
    return tuple(paths), tuple(colors)


def encode_native_review(directory, settings):
    """Use only that native source's attached colors, never current defaults."""
    directory = Path(directory).resolve()
    doc, layers, surface = load_native_layers(directory)
    actual = review_settings(directory / doc['source_file'])
    if settings != actual:
        raise ValueError('Rendered source and requested job preferences disagree')
    _, appearance = reconstruct_rgb(layers, surface)
    if appearance['max_channel_error'] > 2:
        raise ValueError('Semantic layers do not preserve the native RGB appearance')
    paths, colors = native_paths(doc)
    preferences = settings['classic_preferences']
    table = preferences['Colors']
    plan = plan_color_layers(layers, table, pause_colors=preferences['PauseColors'])
    if settings['output_mode'] == 'raster-only':
        raw, cg = encode_raster_draft(plan, 'OfflineColorReview')
    else:
        raw, cg = encode_color_draft(plan, paths, colors, table,
            sort_colors=preferences['SortColors'], pause_colors=preferences['PauseColors'],
            title='OfflineColorReview')
    a, b = decode(raw), decode(cg)
    if (a['commands'] != b['commands'] or a['vector_paths'] != b['vector_paths']
            or len(a['rasters']) != len(b['rasters'])):
        raise ValueError('CG conversion changed color commands or geometry')
    for first, second, region in zip(a['rasters'], b['rasters'], plan.regions):
        for key in ('pixels', 'origin_units', 'resolution_dpi', 'settings', 'width', 'height'):
            if first[key] != second[key]:
                raise ValueError('CG conversion changed a native color raster')
        if second['pixels'] != region.image.pixels:
            raise ValueError('CG conversion changed semantic edge samples')
    for data in (raw, cg):
        if not data.startswith(b'!ZX\r' + DRAFT_MARKER + b'\r') or prepare(data, allow_draft=True).auto_start:
            raise ValueError('Offline review marker/Autostart guard failed')
        try:
            prepare(data)
        except ValueError:
            pass
        else:
            raise ValueError('Offline color draft unexpectedly passed ordinary preparation')
    return raw, cg, dict(source_sha256=doc['source_sha256'], appearance=appearance,
        native_vector_paths=len(paths), selected_vector_paths=len(b['vector_paths']),
        selected_raster_regions=len(plan.regions), unmatched_raster_samples=plan.unmatched_pixels,
        white_paint_excluded=doc['pages'][0]['color_layers']['white_paint_excluded'],
        decoded=summary(b))


def review_job(source, destination, intake_executable):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination.exists():
        raise ValueError('Choose a fresh review directory; earlier evidence is preserved')
    with source.open('rb') as stream:
        data = stream.read(MAX_JOB_BYTES + 1)
    if not 0 < len(data) <= MAX_JOB_BYTES:
        raise ValueError('Unsupported color print length')
    destination.mkdir(parents=True, exist_ok=False)
    snapshot = destination / 'source.oxps'
    snapshot.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    report = dict(schema_version=1, state='held_offline_color_review', source_sha256=digest,
        production_use_colors_enabled=True, physical_device_io=False,
        actual_xp_capture=False, settings_origin='immutable_job_PrintTicket',
        limitations=['Flat opaque source brushes only; White paint classification unverified',
            'Paused mixed multiple-raster-color/vector boundary unverified',
            'This review artifact is a marked offline draft, not a delivery authorization'])
    try:
        settings = review_settings(snapshot)
        report['printer_settings'] = settings
        reader = Path(intake_executable).resolve()
        if not reader.is_file():
            raise ValueError('Experimental native reader is unavailable')
        report['native_reader_sha256'] = hashlib.sha256(reader.read_bytes()).hexdigest()
        command = [str(reader), str(snapshot), str(destination / 'intake'), '--dpi', '167',
            '--raster-grid', 'coreldraw-xp-draft', '--text-rendering', 'outline-aliased',
            '--max-cut-width-mm', '0.2', '--color-review', 'on']
        conversion = subprocess.run(command, shell=False, capture_output=True, timeout=45)
        (destination / 'native.stdout.log').write_bytes(conversion.stdout)
        (destination / 'native.stderr.log').write_bytes(conversion.stderr)
        if conversion.returncode:
            raise ValueError('Experimental native conversion failed; see preserved logs')
        raw, cg, details = encode_native_review(destination / 'intake', settings)
        if details['source_sha256'] != digest or hashlib.sha256(snapshot.read_bytes()).hexdigest() != digest:
            raise ValueError('Rendered source differs from the immutable review snapshot')
        report.update(details)
        (destination / 'job.raw.jbs.draft').write_bytes(raw)
        (destination / 'job.cg.jbs.draft').write_bytes(cg)
        for index, raster in enumerate(decode(cg)['rasters']):
            preview = raster['pixels'].translate(bytes(255-x for x in range(256)))
            (destination / f'layer-{index:02d}.png').write_bytes(png_gray(raster['width'], raster['height'], preview))
        report.update(state='prepared_offline_color_review',
            raw_sha256=hashlib.sha256(raw).hexdigest(), cg_sha256=hashlib.sha256(cg).hexdigest())
    except (ValueError, OSError, KeyError, zipfile.BadZipFile, subprocess.TimeoutExpired) as error:
        report['hold_reason'] = str(error)
    (destination / 'review.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--intake-executable', required=True, type=Path)
    args = parser.parse_args()
    report = review_job(args.source, args.destination, args.intake_executable)
    print(json.dumps({key:report[key] for key in ('state', 'source_sha256', 'physical_device_io')}
        | ({'hold_reason':report['hold_reason']} if 'hold_reason' in report else {})))
    return 0 if report['state'] == 'prepared_offline_color_review' else 2


if __name__ == '__main__':
    raise SystemExit(main())
