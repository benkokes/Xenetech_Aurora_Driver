"""Read legacy Windows dialog resources without loading/executing their DLL.

Layout references: Microsoft DLGTEMPLATE, DLGTEMPLATEEX, DLGITEMTEMPLATE and
DLGITEMTEMPLATEEX documentation. Coordinates are dialog units, not screen pixels.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys


CLASSES = {0x80:'Button', 0x81:'Edit', 0x82:'Static', 0x83:'ListBox', 0x84:'ScrollBar', 0x85:'ComboBox'}


class Reader:
    def __init__(self, data):
        self.data, self.cursor = data, 0

    def take(self, count):
        if count < 0 or self.cursor + count > len(self.data):
            raise ValueError('Truncated dialog resource')
        result = self.data[self.cursor:self.cursor+count]
        self.cursor += count
        return result

    def unpack(self, fmt):
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))

    def word(self):
        return self.unpack('<H')[0]

    def variable(self):
        value = self.word()
        if value == 0xffff:
            return {'ordinal': self.word()}
        units = []
        while value:
            if len(units) >= 4096:
                raise ValueError('Dialog string exceeds its limit')
            units.append(value)
            value = self.word()
        try:
            return struct.pack('<'+'H'*len(units), *units).decode('utf-16le')
        except UnicodeError as error:
            raise ValueError('Invalid dialog Unicode') from error

    def align(self):
        self.take((-self.cursor) % 4)


def parse(data):
    if not isinstance(data, bytes) or not 18 <= len(data) <= 1024*1024:
        raise ValueError('Invalid dialog resource size')
    reader = Reader(data)
    extended = data[2:4] == b'\xff\xff'
    if extended:
        version, signature, help_id, ex_style, style, count, x, y, w, h = reader.unpack('<HHIIIHhhhh')
        if version != 1 or signature != 0xffff:
            raise ValueError('Unknown extended dialog version')
    else:
        style, ex_style, count, x, y, w, h = reader.unpack('<IIHhhhh')
        help_id = 0
    if count > 4096:
        raise ValueError('Too many dialog controls')
    result = {'extended': extended, 'help_id': help_id, 'style': hex(style), 'extended_style': hex(ex_style),
              'bounds_dialog_units': [x,y,w,h], 'menu': reader.variable(), 'class': reader.variable(),
              'title': reader.variable(), 'controls': []}
    if style & 0x40:
        font = {'point_size': reader.word()}
        if extended:
            weight, italic, charset = reader.unpack('<HBB')
            font.update(weight=weight, italic=italic, charset=charset)
        font['typeface'] = reader.variable()
        result['font'] = font
    for _ in range(count):
        reader.align()
        if extended:
            help_id, ex_style, style, x, y, w, h, control_id = reader.unpack('<IIIhhhhI')
        else:
            style, ex_style, x, y, w, h, control_id = reader.unpack('<IIhhhhH')
            help_id = 0
        control_class, title = reader.variable(), reader.variable()
        extra = reader.word()
        # Standard size includes the size WORD; extended extraCount excludes it.
        if extra and not extended and extra < 2:
            raise ValueError('Invalid standard control creation-data size')
        creation = reader.take(extra if extended else max(0, extra-2))
        if isinstance(control_class, dict):
            control_class = CLASSES.get(control_class['ordinal'], control_class)
        result['controls'].append({'id': control_id, 'id_hex': hex(control_id), 'class': control_class,
            'text': title, 'bounds_dialog_units': [x,y,w,h], 'style': hex(style),
            'extended_style': hex(ex_style), 'help_id': help_id, 'creation_data_hex': creation.hex()})
    result['parsed_bytes'] = reader.cursor
    result['trailing_bytes'] = len(data)-reader.cursor
    if any(data[reader.cursor:]):
        raise ValueError('Unparsed nonzero dialog data')
    return result


def inspect(source):
    sys.path.insert(0, str(Path(__file__).resolve().parent/'python'))
    import pefile
    source = Path(source)
    data = source.read_bytes()
    pe = pefile.PE(data=data)
    dialogs = []
    try:
        for kind in getattr(getattr(pe, 'DIRECTORY_ENTRY_RESOURCE', None), 'entries', []):
            if kind.id != 5:
                continue
            for item in kind.directory.entries:
                for language in item.directory.entries:
                    record = language.data.struct
                    content = pe.get_data(record.OffsetToData, record.Size)
                    dialogs.append({'resource_id': item.id, 'resource_name': str(item.name) if item.name else None,
                        'language_id': language.id, 'resource_sha256': hashlib.sha256(content).hexdigest(), **parse(content)})
    finally:
        pe.close()
    return {'source': str(source), 'sha256': hashlib.sha256(data).hexdigest(),
            'vendor_code_executed': False, 'dialogs': dialogs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dll', type=Path)
    parser.add_argument('output_json', type=Path)
    args = parser.parse_args()
    result = inspect(args.dll)
    with args.output_json.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps({'source': result['source'], 'sha256': result['sha256'], 'dialogs': len(result['dialogs'])}))


if __name__ == '__main__':
    main()
