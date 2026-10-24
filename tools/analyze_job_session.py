"""Recover validated jobs and controller replies from decoded PCAP flows.

Reads files only. It never connects to a controller or replays captured bytes.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

if __package__:
    from .reassemble_tcp import reassemble, sequence_delta
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.reassemble_tcp import reassemble, sequence_delta
from aurora_jobserver.jbs import prepare
from aurora_jobserver.replies import MainReplyStream


def find_jobs(data):
    cursor = 0
    jobs = []
    while (start := data.find(b'!ZX\rJOB ', cursor)) >= 0:
        footer = start
        while (footer := data.find(b'END_PLOT\r', footer)) >= 0:
            end = footer + len(b'END_PLOT\r')
            try:
                job = prepare(data[start:end])
            except ValueError:
                footer = end
                continue
            jobs.append((start, end, job))
            cursor = end
            break
        else:
            raise ValueError('A JBS header was found but no complete supported job follows')
    return jobs


def describe_stream(stream, opposite):
    return {'bytes': len(stream.data), 'sha256': hashlib.sha256(stream.data).hexdigest(),
            'has_syn': stream.has_syn, 'has_fin': stream.has_fin, 'has_reset': stream.has_reset,
            'duplicate_bytes': stream.duplicate_bytes,
            'all_payload_tcp_acknowledged': stream.acknowledged_by(opposite)}


def analyze(decoded, output):
    flows = [json.loads(path.read_text()) for path in sorted(decoded.glob('flow-*.json'))]
    by_key = {(f['flow']['src'], f['flow']['sport'], f['flow']['dst'], f['flow']['dport']): f
              for f in flows}
    output.mkdir(parents=True, exist_ok=True)
    sessions = []
    for key, client in by_key.items():
        if key[3] != 23:
            continue
        reverse = (key[2], key[3], key[0], key[1])
        if reverse not in by_key:
            raise ValueError(f'Missing controller direction for {key}')
        server = by_key[reverse]
        tx, rx = reassemble(client['segments']), reassemble(server['segments'])
        jobs = find_jobs(tx.data)
        if not jobs:
            continue
        if not tx.has_syn or not rx.has_syn:
            raise ValueError('Job connection startup is missing from the capture')
        number = len(sessions) + 1
        parser = MainReplyStream()
        events = parser.feed(rx.data) + parser.finish()
        records = []
        for index, (start, end, job) in enumerate(jobs, 1):
            name = f'session-{number:02d}-job-{index:02d}.jbs'
            with (output / name).open('xb') as target:
                target.write(job.data)
            records.append({'file': name, 'stream_start': start, 'stream_end': end,
                            'bytes': len(job.data), 'sha256': hashlib.sha256(job.data).hexdigest(),
                            'format': job.input_format, 'rasters': job.rasters,
                            'auto_start': job.auto_start, 'title': job.title})
        for suffix, data in [('client.bin', tx.data), ('controller.bin', rx.data)]:
            with (output / f'session-{number:02d}-{suffix}').open('xb') as target:
                target.write(data)
        session = {'client': list(key[:2]), 'controller': list(key[2:]),
                   'tx': describe_stream(tx, server['segments']),
                   'rx': describe_stream(rx, client['segments']), 'jobs': records,
                   'before_first_job': tx.data[:jobs[0][0]].decode('ascii'),
                   'after_last_job': tx.data[jobs[-1][1]:].decode('ascii'),
                   'client_writes': [{'time': s['time'],
                                      'offset': sequence_delta(s['seq'], tx.first_sequence),
                                      'bytes': len(bytes.fromhex(s['payload_hex'])),
                                      'controller_bytes_acknowledged_before_write':
                                          sequence_delta(s['ack'], rx.first_sequence)}
                                     for s in client['segments'] if s['payload_hex']],
                   'reply_events': [dict(asdict(e), raw=e.raw.hex()) for e in events]}
        sessions.append(session)
    report = {'decoded_flows': str(decoded), 'sessions': sessions,
              'note': 'TCP ACK confirms byte receipt, not engraving success. Control 04 also occurs before the job.'}
    with (output / 'report.json').open('x', encoding='utf-8') as target:
        json.dump(report, target, indent=2)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('decoded_flows', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    report = analyze(args.decoded_flows, args.output)
    for session in report['sessions']:
        print(json.dumps({k: v for k, v in session.items() if k != 'reply_events'}))
        print(json.dumps({'notable_replies': [e for e in session['reply_events']
                                             if e['kind'] != 'text']}))


if __name__ == '__main__':
    main()
