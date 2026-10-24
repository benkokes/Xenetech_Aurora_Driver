"""Independently verify saved native Windows settings in the Python backend.

Reads a completed ClassicNativeRoundtrip --matrix report. No printer calls,
renderer invocation, controller connection or production queue mutation.
"""
import argparse
import base64
import csv
import hashlib
import json
import re
from pathlib import Path
import tempfile
import zipfile

from aurora_jobserver import classic_settings as classic
from aurora_jobserver.printer_settings import settings_from_xps, ticket_payload, ticket_selection


def verify(source, destination, document=None):
    source, destination = Path(source), Path(destination)
    if destination.exists():
        raise FileExistsError('Choose a new verification directory')
    result_text = (source/'result.txt').read_text(encoding='utf-8-sig')
    if not result_text.startswith('PASS:'):
        raise ValueError('Native report did not finish successfully')
    with (source/'cases.tsv').open(encoding='utf-8-sig', newline='') as stream:
        cases = list(csv.DictReader(stream, delimiter='\t'))
    if not cases or len(cases) > 1000 or len({item['index'] for item in cases}) != len(cases):
        raise ValueError('Invalid native case manifest')
    count = re.match(r'PASS: (\d+) independent full snapshots', result_text)
    if count is None or int(count.group(1)) != len(cases):
        raise ValueError('Native result and case manifest disagree')
    if set(cases[0]) != {'index', 'case', 'payload_characters', 'devmode_bytes'}:
        raise ValueError('Unknown native case manifest')
    package = None
    if document is not None:
        with zipfile.ZipFile(document) as archive:
            package = [(info, archive.read(info.filename)) for info in archive.infolist()]
        if not any(info.filename == 'Metadata/Job_PT.xml' for info, _ in package):
            raise ValueError('Expected the known Corel reference document job ticket')
    results = []
    covered = set()
    with tempfile.TemporaryDirectory() as temp:
        for case in cases:
            if not case['index'].isdigit():
                raise ValueError('Invalid case index')
            index = int(case['index'])
            expected_xml = (source/f'expected-{index}.xml').read_text(encoding='utf-8-sig')
            payload = base64.b64encode(expected_xml.encode('utf-8')).decode('ascii')
            expected = classic.parse(payload)
            covered.update(expected)
            if len(payload) != int(case['payload_characters']):
                raise AssertionError('Native manifest payload length changed')
            expected_selection = classic.carriers(expected)
            stages = {}
            for stage in ('validated', 'restored'):
                xml = (source/f'{stage}-{index}.xml').read_bytes()
                actual_payload = ticket_payload(xml)
                selected = ticket_selection(xml, allow_custom=True)
                if classic.parse(actual_payload) != expected or selected != expected_selection:
                    raise AssertionError(f'Python/native settings disagree: {case["case"]} {stage}')
                settings = classic.decode(selected, actual_payload)
                if settings['held_features'] != classic.holds(expected):
                    raise AssertionError('Native settings changed backend feature holds')
                held = bool(settings['held_features'])
                try:
                    classic.ensure_supported(settings)
                except ValueError:
                    if not held:
                        raise
                else:
                    if held:
                        raise AssertionError('Unverified native feature bypassed its hold')
                if package is not None:
                    archive_path = Path(temp)/'native-settings.oxps'
                    with zipfile.ZipFile(archive_path, 'w') as archive:
                        for info, data in package:
                            archive.writestr(info, xml if info.filename == 'Metadata/Job_PT.xml' else data)
                    if settings_from_xps(archive_path) != settings:
                        raise AssertionError('Full document scope changed native settings')
                stages[stage] = {'xml_sha256': hashlib.sha256(xml).hexdigest(),
                                 'held_features': settings['held_features']}
            results.append({'index': index, 'case': case['case'], 'payload_characters': len(payload), 'stages': stages})
    report = {'state': 'native_settings_independently_verified_by_python', 'case_count': len(results),
              'native_stages_verified': len(results)*2, 'full_document_reads': len(results)*2 if package else 0,
              'snapshot_fields_checked': sorted(covered), 'cases': results,
              'printer_or_device_io_performed': False}
    destination.mkdir(parents=True)
    (destination/'verification.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('native_report', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--document', type=Path, help='Known Corel XPS capture for job-ticket scope checks')
    args = parser.parse_args()
    report = verify(args.native_report, args.destination, args.document)
    print(json.dumps({k: v for k, v in report.items() if k != 'cases'}, indent=2))


if __name__ == '__main__':
    main()
