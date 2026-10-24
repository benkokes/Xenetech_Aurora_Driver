"""Check native feature expansion, not merely GPDCheck's exit code or BUD cache.

Microsoft's checker returns zero and produces a BUD for some definitions whose
semantic expansion fails. Require every declared feature to appear in its native
feature enumeration. Operates on a temporary copy, without touching the spooler.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


SHARED_FILES = ('MSXPSINC.GPD', 'STDNAMES.GPD', 'STDDTYPE.GDL', 'STDSCHEM.GDL',
                'STDSCHMX.GDL', 'UNIRES.DLL')


def validate(source, checker, shared_files):
    source, checker, shared_files = map(lambda p: Path(p).resolve(),
                                        (source, checker, shared_files))
    expected = set(re.findall(r'^\*Feature:\s+(\w+)', source.read_text(), re.M))
    if not expected:
        raise ValueError('GPD declares no features')
    with tempfile.TemporaryDirectory(prefix='aurora-gpd-') as temp:
        temp = Path(temp)
        copied = temp / source.name
        shutil.copyfile(source, copied)
        for name in SHARED_FILES:
            shutil.copyfile(shared_files / name, temp / name)
        result = subprocess.run([str(checker), '-n', '-k', '-x', '-v4', '-da', str(copied)],
                                cwd=temp, capture_output=True, text=True, timeout=60)
        observed = set(re.findall(r'^Feature:\s+(\w+)\s+\(', result.stdout, re.M))
        missing = sorted(expected - observed)
        if result.returncode or missing or not copied.with_suffix('.BUD').is_file():
            raise ValueError('Native GPD validation failed; missing features: ' +
                             ', '.join(missing) + '\n' + result.stdout + result.stderr)
        return {'state': 'native_feature_expansion_passed',
                'gpd_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'expected_features': sorted(expected), 'observed_features': sorted(observed),
                'bud_bytes': copied.with_suffix('.BUD').stat().st_size,
                'checker_output': result.stdout, 'device_io_performed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('gpd', type=Path)
    parser.add_argument('--checker', required=True, type=Path)
    parser.add_argument('--shared-files', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    report = validate(args.gpd, args.checker, args.shared_files)
    args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
