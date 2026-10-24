"""Complete XP-style preferences carried by an immutable per-print snapshot.

Parsing and carrier checks happen before rendering. Features without a verified
encoder remain explicit holds, never silently ignored before laser delivery.
"""
import base64
import binascii
from decimal import Decimal, InvalidOperation
import hashlib
import re

from .artwork import ProcessSettings

PARAMETER = 'JobAuroraPreferences'
MAX_PAYLOAD = 20000
ENUMS = {
    'Output': ('RasterOnly', 'VectorOnly', 'RasterAndVector'),
    'Focus': ('None', 'Manual', 'Thickness', 'Autofocus'),
    'BitmapMode': ('ClipArt', 'Photo', 'Custom'),
    'Dither': ('Ordered4', 'Ordered8', 'FloydSteinberg', 'Jarvis', 'Stucki'),
    'Orientation': ('Normal', 'Left90', 'Right90', 'UpsideDown'),
}
BOOLS = set('UseColors SortColors PauseColors InvertRaster BottomUp Autostart BeamConstantlyOn Cylindrical CenterHorizontal CenterVertical DitherBitmaps ManualContrast Mirror RubberStamp DefaultFilename AppendDateTime'.split())
DECIMALS = {
    'RasterPower': (0, 100, 2), 'VectorPower': (0, 100, 2),
    'RasterSpeed': ('.001', 150, 3), 'VectorSpeed': ('.001', 15, 3),
    'TravelSpeed': ('.001', 250, 3),
    'ThicknessInches': (0, 18, 6), 'PlateWidthInches': ('.001', 30, 6),
    'PlateHeightInches': ('.001', 18, 6),
    'OffsetXInches': (-30, 30, 6), 'OffsetYInches': (-18, 18, 6),
}
INTS = {'Version': (1, 2), 'VectorPpi': (5, 1000), 'Resolution': (50, 1200),
        'ContrastLow': (0, 254), 'ContrastHigh': (1, 255), 'ContrastColors': (2, 256)}
STRINGS = {'StampProfile': 64, 'OutputDirectory': 512, 'LaserModel': 64, 'ColorProfile': 64}
NAMES = ('Black Red Navy Magenta Maroon Lime Olive Aqua Gray Blue Purple Silver Green Yellow Teal White').split()
RGB = (0x000000,0xff0000,0x000080,0xff00ff,0x800000,0x00ff00,0x808000,0x00ffff,0x808080,0x0000ff,0x800080,0xc0c0c0,0x008000,0xffff00,0x008080,0xffffff)
RESOLUTIONS = (50, 100, 167, 200, 250, 333, 500, 1000, 1200)


def fields(node, required):
    result = {}
    if (node.text or '').strip():
        raise ValueError('Unexpected text in Aurora settings')
    for child in node:
        if child.tag not in required or child.tag in result or child.attrib or (child.tail or '').strip():
            raise ValueError('Unknown, attributed or duplicate Aurora settings field')
        result[child.tag] = child
    if set(result) != set(required):
        raise ValueError('Incomplete Aurora settings snapshot')
    return result


def text(node):
    if len(node):
        raise ValueError('Nested value in Aurora settings')
    return node.text or ''


def boolean(node):
    value = text(node)
    if value not in ('true', 'false'):
        raise ValueError('Invalid Aurora boolean')
    return value == 'true'


def integer(node, low, high):
    value = text(node)
    if not re.fullmatch(r'-?\d{1,8}', value) or not low <= int(value) <= high:
        raise ValueError('Invalid Aurora integer')
    return int(value)


def decimal(node, low, high, digits):
    value = text(node)
    if not re.fullmatch(r'-?\d{1,8}(?:\.\d{1,12})?', value):
        raise ValueError('Invalid Aurora decimal')
    try:
        number = Decimal(value)
        if not Decimal(str(low)) <= number <= Decimal(str(high)) or number != number.quantize(Decimal(1).scaleb(-digits)):
            raise ValueError('Aurora decimal is outside its range or precision')
    except InvalidOperation as error:
        raise ValueError('Invalid Aurora decimal') from error
    return format(number.normalize(), 'f')


def parse(payload):
    from .printer_settings import xml_document
    if not isinstance(payload, str) or not 0 < len(payload) <= MAX_PAYLOAD:
        raise ValueError('Aurora settings payload exceeds its limit or is empty')
    try:
        raw = base64.b64decode(payload, validate=True)
        document = raw.decode('utf-8', errors='strict')
    except (UnicodeError, ValueError, binascii.Error) as error:
        raise ValueError('Invalid Aurora settings encoding') from error
    if len(document) > 15000 or len(raw) > 15000:
        raise ValueError('Aurora settings document exceeds its limit')
    root, _ = xml_document(raw)
    if root.tag != 'AuroraPreferences' or root.attrib:
        raise ValueError('Unknown Aurora settings document')
    nodes = fields(root, set(ENUMS) | BOOLS | set(DECIMALS) | set(INTS) | set(STRINGS) | {'Colors'})
    result = {}
    for key, choices in ENUMS.items():
        value = text(nodes[key])
        if value not in choices:
            raise ValueError('Unknown Aurora settings mode: ' + key)
        result[key] = value
    result.update((key, boolean(nodes[key])) for key in BOOLS)
    result.update((key, decimal(nodes[key], *limits)) for key, limits in DECIMALS.items())
    result.update((key, integer(nodes[key], *limits)) for key, limits in INTS.items())
    for key, limit in STRINGS.items():
        value = text(nodes[key])
        if len(value) > limit:
            raise ValueError('Oversized Aurora text preference')
        result[key] = value
    if (result['Resolution'] not in RESOLUTIONS or result['ContrastLow'] >= result['ContrastHigh']
            or result['StampProfile'] != 'Factory Default 1' or result['LaserModel'] != 'Aurora'):
        raise ValueError('Invalid resolution, contrast, stamp profile or laser model')
    colors = nodes['Colors']
    if (colors.text or '').strip() or len(colors) != 16:
        raise ValueError('Expected the original 16-color palette')
    result['Colors'] = []
    for index, item in enumerate(colors):
        if item.tag != 'ClassicColor' or item.attrib or (item.tail or '').strip():
            raise ValueError('Unknown Aurora color record')
        color = fields(item, {'Name','R','G','B','Enabled','PowerPercent','SpeedIps','Ppi'})
        rgb = [integer(color[key], 0, 255) for key in ('R','G','B')]
        expected = [(RGB[index] >> shift) & 255 for shift in (16,8,0)]
        if text(color['Name']) != NAMES[index] or rgb != expected:
            raise ValueError('Aurora palette identity changed')
        result['Colors'].append({'Name':NAMES[index], 'R':rgb[0], 'G':rgb[1], 'B':rgb[2],
            'Enabled':boolean(color['Enabled']), 'PowerPercent':decimal(color['PowerPercent'],0,100,2),
            'SpeedIps':decimal(color['SpeedIps'],'.001',150,3), 'Ppi':integer(color['Ppi'],5,1000)})
    return result


def carriers(settings):
    from .printer_settings import FEATURES, BY_KEY
    number = lambda prefix, value, scale=1: prefix + str(int(Decimal(value) * scale)) if (Decimal(value)*scale) == (Decimal(value)*scale).to_integral_value() else 'Custom'
    values = {
        'AuroraRasterPower': number('Percent', settings['RasterPower']),
        'AuroraVectorPower': number('Percent', settings['VectorPower']),
        'AuroraRasterSpeed': number('Speed', settings['RasterSpeed'],1000),
        'AuroraVectorSpeed': number('Speed', settings['VectorSpeed'],1000),
        'AuroraVectorPPI': 'PPI'+str(settings['VectorPpi']),
        'AuroraLaserDPI': 'DPI'+str(settings['Resolution']),
        'AuroraAutostart': 'On' if settings['Autostart'] else 'Off',
        'AuroraOutputMode': 'RasterAndVector' if settings['Output']=='RasterAndVector' else 'Custom',
        'AuroraFocus': 'None' if settings['Focus']=='None' else 'Custom',
    }
    return {feature.key:values[feature.key] if values[feature.key] in dict(BY_KEY[feature.key].options) else 'Custom' for feature in FEATURES}


def holds(s):
    reasons = []
    expected = {'Focus':'None','UseColors':False,
        'BeamConstantlyOn':True,'PlateWidthInches':'30','PlateHeightInches':'18','OffsetXInches':'0','OffsetYInches':'0',
        'Cylindrical':False,'CenterHorizontal':False,'CenterVertical':False,
        # Version 1's supported value was the native command 100, mislabeled
        # in the UI. Version 2 explicitly stores inches per second. Preserve
        # old queued snapshots and keep every other travel value held.
        'TravelSpeed':'100' if s['Version']==1 else '0.1',
        'BitmapMode':'Custom','DitherBitmaps':False,'ManualContrast':False,'Orientation':'Normal','Mirror':False,
        'RubberStamp':False,'OutputDirectory':'JobServer archive','DefaultFilename':True,'AppendDateTime':False}
    for key, default in expected.items():
        # Vector Only was physically accepted October 22; the three-raster /
        # two-vector mixed sheet was accepted October 23. Keep all at 167 DPI.
        if key == 'UseColors' and s['Resolution'] == 167:
            continue
        if s[key] != default:
            reasons.append(key)
    if s['Output']=='VectorOnly' and s['Resolution']!=167:
        reasons.append('VectorOnlyResolution')
    if s['Resolution'] not in (100,167):
        reasons.append('Resolution')
    if s['Resolution'] != 167:
        reasons.extend(key for key in ('InvertRaster','BottomUp') if s[key])
    if s['UseColors'] and s['Output']!='VectorOnly':
        reasons.extend('ColorRaster'+key for key in ('PauseColors','BottomUp','InvertRaster') if s[key])
    if Decimal(s['RasterSpeed']) > 31:
        reasons.append('RasterSpeed')
    return reasons


def decode(selection, payload):
    from .printer_settings import decode as legacy_decode, default_selection
    s = parse(payload)
    if carriers(s) != selection:
        raise ValueError('Conflicting complete and legacy Aurora laser settings')
    result = legacy_decode(default_selection())
    process = {'schema_version':1, 'units':'driver-native',
        'raster_speed_native':int(Decimal(s['RasterSpeed'])*1000),
        'raster_power_percent':float(s['RasterPower']),
        'vector_speed_native':int(Decimal(s['VectorSpeed'])*1000),
        'vector_power_percent':float(s['VectorPower']), 'vector_ppi':s['VectorPpi']}
    reasons = holds(s)
    if not reasons:
        ProcessSettings.parse(process)
    result.update(schema_version=2, process_settings=process, laser_dpi=s['Resolution'], autostart=s['Autostart'],
        output_mode={'RasterAndVector':'raster-and-vector','RasterOnly':'raster-only','VectorOnly':'vector-only'}[s['Output']],
        selection=selection, classic_preferences=s, preferences_sha256=hashlib.sha256(payload.encode('ascii')).hexdigest(),
        held_features=reasons)
    return result


def ensure_supported(settings, *, allow_color_vectors=True, allow_color_rasters=True):
    if type(allow_color_vectors) is not bool:
        raise ValueError('Color-vector validation permission must be an explicit boolean')
    if type(allow_color_rasters) is not bool:
        raise ValueError('Color-raster validation permission must be an explicit boolean')
    reasons = list(settings.get('held_features', []))
    prefs=settings.get('classic_preferences',{})
    if (allow_color_rasters and prefs.get('UseColors') is True and settings.get('laser_dpi')==167
            and settings.get('output_mode') in ('raster-only','raster-and-vector')):
        reasons=[reason for reason in reasons if reason!='UseColors']
        reasons.extend('ColorRaster'+key for key in ('PauseColors','BottomUp','InvertRaster')
                       if prefs.get(key) and 'ColorRaster'+key not in reasons)
    # An explicit opt-out also applies to cached conversions. Never exempt
    # unrelated holds or reinterpret an old, already-held prepared result.
    if (not allow_color_vectors and prefs.get('UseColors') is True and settings.get('output_mode')!='raster-only'
            and 'UseColors' not in reasons):
        reasons.append('UseColors')
    if (not allow_color_rasters and prefs.get('UseColors') is True
            and settings.get('output_mode') in ('raster-only','raster-and-vector') and 'UseColors' not in reasons):
        reasons.append('UseColors')
    if reasons:
        raise ValueError('Print held: these preferences need additional output/transfer verification before use: ' + ', '.join(reasons))
