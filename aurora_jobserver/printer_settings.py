"""Per-job Aurora options shared by the printer definition and PrintTicket reader.

The first printer profile deliberately advertises only the implemented flatbed
controls. Windows' source rendering stays at 600 DPI; laser DPI is separate.
"""
from dataclasses import dataclass
from decimal import Decimal
import io
from pathlib import Path
import posixpath
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
from xml.parsers import expat
import zipfile

from .artwork import ProcessSettings
from .corel_layout import COREL_HAIRLINE_MAX_MM


PRIVATE = 'urn:aurora-jobserver:print-schema:1'
PSF = 'http://schemas.microsoft.com/windows/2003/08/printing/printschemaframework'
TICKET_TYPE = 'application/vnd.ms-printing.printticket+xml'
CONTENT_TYPES = 'http://schemas.openxmlformats.org/package/2006/content-types'
RELATIONSHIPS = 'http://schemas.openxmlformats.org/package/2006/relationships'
XPS_REL = ('http://schemas.microsoft.com/xps/2005/06/', 'http://schemas.openxps.org/oxps/v1.0/')
MAX_XML = 1024 * 1024


@dataclass(frozen=True)
class Feature:
    key: str
    label: str
    default: str
    options: tuple


SPEEDS = ('0.001', '0.01', '0.1', '0.5', '1', '2', '3', '5', '8', '10', '15', '20', '25', '30', '31')
def speed_options():
    return tuple(('Speed' + str(int(Decimal(speed) * 1000)), speed + ' ips') for speed in SPEEDS)


FEATURES = (
    Feature('AuroraRasterPower', 'Raster power (percent)', 'Percent45', tuple(('Percent'+str(n), str(n)+' percent') for n in range(101))),
    Feature('AuroraRasterSpeed', 'Raster speed (ips)', 'Speed30000', speed_options()),
    Feature('AuroraVectorPower', 'Vector power (percent)', 'Percent15', tuple(('Percent'+str(n), str(n)+' percent') for n in range(101))),
    Feature('AuroraVectorSpeed', 'Vector speed (ips)', 'Speed1000', speed_options()),
    Feature('AuroraVectorPPI', 'Vector PPI', 'PPI1000', tuple(('PPI'+str(n), str(n)) for n in (5,10,50,100,200,250,500,750,1000))),
    Feature('AuroraLaserDPI', 'Laser raster resolution', 'DPI167', (('DPI100','100 DPI'),('DPI167','167 DPI'))),
    Feature('AuroraAutostart', 'Autostart engraving', 'Off', (('Off','Wait for machine Start'),('On','Start automatically'))),
    Feature('AuroraOutputMode', 'Laser output mode', 'RasterAndVector', (('RasterAndVector','Raster and vector'),)),
    Feature('AuroraFocus', 'Focus at job start', 'None', (('None','No focus command'),)),
)
BY_KEY = {feature.key: feature for feature in FEATURES}
# Windows prefixes DOC_PROPERTY private GPD features with Job in PrintTicket.
TICKET_KEYS = {'Job' + feature.key: feature.key for feature in FEATURES}


def default_selection():
    return {feature.key: feature.default for feature in FEATURES}


def validate_selection(selection, *, allow_custom=False):
    if not isinstance(selection, dict) or set(selection) != set(BY_KEY):
        raise ValueError('Print is missing explicit Aurora laser properties')
    for key, value in selection.items():
        if value not in dict(BY_KEY[key].options) and not (allow_custom and value == 'Custom' and key != 'AuroraAutostart'):
            raise ValueError('Unsupported printer option: ' + key)
    return dict(selection)


def decode(selection):
    value = validate_selection(selection)
    settings = {'schema_version':1, 'units':'driver-native',
        'raster_speed_native':int(value['AuroraRasterSpeed'][5:]),
        'raster_power_percent':int(value['AuroraRasterPower'][7:]),
        'vector_speed_native':int(value['AuroraVectorSpeed'][5:]),
        'vector_power_percent':int(value['AuroraVectorPower'][7:]),
        'vector_ppi':int(value['AuroraVectorPPI'][3:])}
    ProcessSettings.parse(settings)
    return {'schema_version':1, 'process_settings':settings,
            'laser_dpi':int(value['AuroraLaserDPI'][3:]),
            'autostart':value['AuroraAutostart'] == 'On',
            'output_mode':'raster-and-vector', 'focus':'none',
            'page_mm':[762,457.2], 'offset_mm':[0,0],
            'source_dpi':600, 'cut_color':'any', 'max_cut_width_mm':COREL_HAIRLINE_MAX_MM,
            'selection':value}


def xml_document(data):
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_XML:
        raise ValueError('PrintTicket XML exceeds the limit or is empty')
    def reject(*args):
        raise ValueError('DTD and entities are not allowed in print settings')
    parser = expat.ParserCreate()
    parser.StartDoctypeDeclHandler = reject
    parser.EntityDeclHandler = reject
    parser.ExternalEntityRefHandler = reject
    try:
        parser.Parse(data, True)
        scopes, stack, pending, count = {}, [], {}, 0
        iterator = ET.iterparse(io.BytesIO(data), events=('start-ns','start','end'))
        for kind, item in iterator:
            if kind == 'start-ns':
                pending[item[0]] = item[1]
            elif kind == 'start':
                count += 1
                if len(stack) >= 64 or count > 10000:
                    raise ValueError('PrintTicket XML is too complex')
                scope = (dict(stack[-1]) if stack else {}) | pending
                pending = {}
                scopes[id(item)] = scope
                stack.append(scope)
            else:
                stack.pop()
        return iterator.root, scopes
    except (ET.ParseError, expat.ExpatError) as error:
        raise ValueError('Malformed print settings XML') from error


def qname(element, scopes):
    value = element.get('name', '')
    parts = value.split(':')
    if len(parts) == 1:
        return scopes[id(element)].get('', ''), parts[0]
    if len(parts) != 2 or not all(parts):
        raise ValueError('Malformed print schema name')
    namespace = scopes[id(element)].get(parts[0])
    if namespace is None:
        raise ValueError('Unbound print schema prefix')
    return namespace, parts[1]


def ticket_selection(data, *, complete=True, allow_custom=False):
    root, scopes = xml_document(data)
    if root.tag != '{'+PSF+'}PrintTicket' or root.get('version') != '1':
        raise ValueError('Expected version-1 PrintTicket')
    selection = {}
    for feature in root.iter('{'+PSF+'}Feature'):
        namespace, ticket_key = qname(feature, scopes)
        if namespace != PRIVATE:
            continue
        key = TICKET_KEYS.get(ticket_key)
        if feature not in list(root) or key is None or key in selection:
            raise ValueError('Unknown, nested or duplicate Aurora printer feature')
        options = feature.findall('{'+PSF+'}Option')
        if len(options) != 1:
            raise ValueError('Expected one selected Aurora option')
        option_namespace, option = qname(options[0], scopes)
        if option_namespace != PRIVATE or (option not in dict(BY_KEY[key].options) and not (allow_custom and option == 'Custom' and key != 'AuroraAutostart')):
            raise ValueError('Unsupported Aurora option or namespace')
        selection[key] = option
    return validate_selection(selection, allow_custom=allow_custom) if complete else selection


def ticket_payload(data):
    from .classic_settings import PARAMETER, parse
    root, scopes = xml_document(data)
    if root.tag != '{'+PSF+'}PrintTicket' or root.get('version') != '1':
        raise ValueError('Expected version-1 PrintTicket')
    payload = None
    for parameter in root.iter('{'+PSF+'}ParameterInit'):
        namespace, key = qname(parameter, scopes)
        if namespace != PRIVATE:
            continue
        # PrintConfig adds its own opaque binary DEVMODE snapshot in the GPD's
        # private namespace. It is not the authoritative laser preference set.
        if key == 'PageDevmodeSnapshot' and parameter in list(root):
            continue
        if key != PARAMETER or parameter not in list(root) or payload is not None:
            raise ValueError('Unknown, nested or duplicate Aurora preferences parameter')
        values = list(parameter)
        if len(values) != 1 or values[0].tag != '{'+PSF+'}Value' or len(values[0]):
            raise ValueError('Malformed Aurora preferences parameter')
        payload = values[0].text or ''
        if payload:
            parse(payload)
    return payload


def make_ticket(selection):
    selection = validate_selection(selection)
    ET.register_namespace('psf', PSF)
    root = ET.Element('{'+PSF+'}PrintTicket', {'version':'1', 'xmlns:aur':PRIVATE})
    for feature in FEATURES:
        node = ET.SubElement(root, '{'+PSF+'}Feature', {'name':'aur:Job'+feature.key})
        ET.SubElement(node, '{'+PSF+'}Option', {'name':'aur:'+selection[feature.key]})
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def settings_from_xps(source):
    """Read job-attached properties, never a mutable current-defaults file.

    For this single-page profile, conflicting properties across ticket scopes
    are rejected rather than guessed. Missing Aurora properties fail closed.
    """
    source = Path(source)
    if not 0 < source.stat().st_size <= 64*1024*1024:
        raise ValueError('Unsupported print document length')
    with zipfile.ZipFile(source) as package:
        entries = package.infolist()
        if len(entries) > 2000 or len({entry.filename for entry in entries}) != len(entries):
            raise ValueError('Duplicate or excessive print package entries')
        def read(name):
            info = package.getinfo(name)
            if not 0 < info.file_size <= MAX_XML:
                raise ValueError('Oversized print package XML')
            return package.read(info)
        types, _ = xml_document(read('[Content_Types].xml'))
        if types.tag != '{'+CONTENT_TYPES+'}Types':
            raise ValueError('Invalid print package content types')
        names = set()
        defaults = {}
        for item in types:
            if item.tag == '{'+CONTENT_TYPES+'}Default':
                extension = item.get('Extension', '')
                if extension in defaults:
                    raise ValueError('Duplicate package content type')
                defaults[extension] = item.get('ContentType')
            elif item.tag == '{'+CONTENT_TYPES+'}Override' and item.get('ContentType') == TICKET_TYPE:
                name = item.get('PartName', '')
                if not name.startswith('/') or '..' in name.split('/') or '\\' in name:
                    raise ValueError('Invalid PrintTicket part name')
                names.add(name[1:])
        names.update(entry.filename for entry in entries
                     if entry.filename != '[Content_Types].xml'
                     and defaults.get(entry.filename.rsplit('.',1)[-1]) == TICKET_TYPE)
        if len(names) > 100:
            raise ValueError('Excessive PrintTicket parts')
        def relationships(part, suffix):
            rels_name = (posixpath.join(posixpath.dirname(part),'_rels',posixpath.basename(part)+'.rels')
                         if part else '_rels/.rels')
            rels, _ = xml_document(read(rels_name))
            if rels.tag != '{'+RELATIONSHIPS+'}Relationships':
                raise ValueError('Invalid package relationships')
            targets = []
            for rel in rels:
                if rel.tag != '{'+RELATIONSHIPS+'}Relationship' or rel.get('Type') not in tuple(ns+suffix for ns in XPS_REL):
                    continue
                uri = urlsplit(rel.get('Target',''))
                target = unquote(uri.path)
                if (rel.get('TargetMode','Internal') != 'Internal' or uri.scheme or uri.netloc
                        or uri.query or uri.fragment or not target or '\\' in target):
                    raise ValueError('External or invalid print settings relationship')
                name = posixpath.normpath(posixpath.join(posixpath.dirname(part),target)) if not target.startswith('/') else posixpath.normpath(target)[1:]
                if name == '..' or name.startswith('../'):
                    raise ValueError('Print relationship leaves the package')
                targets.append(name)
            if len(targets) != 1:
                raise ValueError('Expected exactly one '+suffix+' relationship')
            return targets[0]
        sequence = relationships('', 'fixedrepresentation')
        if sequence not in package.namelist():
            raise ValueError('Missing fixed document sequence')
        job_ticket = relationships(sequence, 'printticket')
        if job_ticket not in names:
            raise ValueError('Job settings relationship is not a PrintTicket part')
        # Require a complete ticket attached to the actual job. Orphaned ticket
        # parts or a mutable defaults file cannot supply missing laser settings.
        selection = ticket_selection(read(job_ticket), allow_custom=True)
        payload = ticket_payload(read(job_ticket))
        for name in sorted(names):
            for key, value in ticket_selection(read(name), complete=False, allow_custom=True).items():
                if selection[key] != value:
                    raise ValueError('Conflicting laser settings across PrintTickets')
            scoped_payload = ticket_payload(read(name))
            if scoped_payload is not None and scoped_payload != payload:
                raise ValueError('Conflicting full laser preferences across PrintTickets')
    if payload:
        from .classic_settings import decode as decode_classic
        return decode_classic(selection,payload)
    return decode(selection)
