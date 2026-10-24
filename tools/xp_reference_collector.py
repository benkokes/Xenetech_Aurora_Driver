"""Validate offline XP collector candidates; no printer/device APIs.

The guest's framing/stability checks are preliminary. Only a complete independent
decode can publish Default.jbs and an immutable verified.json success report.
"""
import argparse
import json
from pathlib import Path
import re
import time

from aurora_jobserver.jbs import MAX_JOB_BYTES
from tools.compare_preference_jobs import decode, summary


def case_path(root, label):
    if not re.fullmatch(r'[a-z0-9-]{1,48}', label):
        raise ValueError('Invalid capture label')
    root = Path(root).resolve(strict=True)
    case = root / label
    if case.is_symlink() or (case.exists() and case.resolve().parent != root):
        raise ValueError('Capture directory must stay inside collector root')
    return root, case


def arm(root, label, timeout=6):
    root, case = case_path(root, label)
    case.mkdir(exist_ok=True)
    if any((case/name).exists() for name in ('candidate.jbs', 'Default.jbs', 'verified.json')):
        raise FileExistsError('Preserve existing capture; choose a new label')
    if (root/'stop-collector.txt').exists():
        raise ValueError('Collector is stopped; do not print')
    # FSO can briefly hold the shared request file. Exclusive temporary creation
    # also prevents concurrent host arm requests from silently replacing it.
    temp = root/'request-next.tmp'
    with temp.open('x', encoding='ascii') as stream:
        stream.write(label)
    try:
        temp.replace(root/'request.txt')
    finally:
        if temp.exists():
            temp.unlink()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            status = (root/'collector-status.txt').read_text().strip()
        except OSError:
            status = ''
        if status == 'ARMED ' + label:
            return case
        if status.startswith('BLOCKED:') or status == 'STOPPED':
            raise ValueError('Collector unavailable; do not print: ' + status)
        time.sleep(.2)
    raise TimeoutError('Collector did not arm; do not print')


def verify(root, label):
    _, case = case_path(root, label)
    if (case/'Default.jbs').exists() or (case/'verified.json').exists():
        raise FileExistsError('Preserve existing verification; choose a new case')
    # Read at most the decoder limit plus one byte, even if the candidate grows.
    with (case/'candidate.jbs').open('rb') as stream:
        data = stream.read(MAX_JOB_BYTES + 1)
    job = summary(decode(data))
    if job['draft'] or job['autostart']:
        raise ValueError('Offline reference must be non-draft with Autostart Off')
    if not job['rasters'] and not job['vector_paths']:
        raise ValueError('Reference job contains no artwork')
    report = {'state': 'verified_offline_reference', 'case': label,
              'physical_device_io': False, 'decoded': job}
    # Decode before creating output. Exclusive creation preserves both failed
    # candidates and prior reports. A success requires both complete files;
    # any interrupted publication requires a fresh case, never an overwrite.
    with (case/'Default.jbs').open('xb') as stream:
        stream.write(data)
    with (case/'verified.json').open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('arm', 'verify'))
    parser.add_argument('root', type=Path)
    parser.add_argument('label')
    args = parser.parse_args()
    if args.action == 'arm':
        arm(args.root, args.label)
        print('ARMED ' + args.label + '; confirm XP cable disconnected and JobServer closed before printing')
    else:
        report = verify(args.root, args.label)
        print(json.dumps({'state': report['state'], 'case': args.label,
                          'bytes': report['decoded']['bytes'], 'sha256': report['decoded']['sha256']}))


if __name__ == '__main__':
    main()
