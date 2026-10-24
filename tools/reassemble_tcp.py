"""Strict offline reassembly of one direction from inspect_pcap JSON.

Identical retransmissions are accepted. Gaps, conflicting overlaps, tuple reuse,
and streams larger than the configured bound are rejected. This is for small
controller sessions, not a general TCP implementation.
"""
from dataclasses import dataclass
import argparse
import json
from pathlib import Path


MASK = (1 << 32) - 1


def sequence_delta(sequence, base):
    return ((sequence - base + (1 << 31)) & MASK) - (1 << 31)


@dataclass(frozen=True)
class ReassembledStream:
    data: bytes
    first_sequence: int | None
    has_syn: bool
    has_fin: bool
    has_reset: bool
    duplicate_bytes: int

    def acknowledged_by(self, segments):
        """TCP receipt only; this does not establish application acceptance."""
        if not self.data:
            return True
        return any(s['flags'] & 0x10 and
                   sequence_delta(s['ack'], self.first_sequence) >= len(self.data)
                   for s in segments)


def reassemble(segments, max_bytes=64 * 1024 * 1024):
    syns = {s['seq'] for s in segments if s['flags'] & 2}
    if len(syns) > 1:
        raise ValueError('Multiple TCP connections share this flow; split them first')
    payloads = [(s, bytes.fromhex(s['payload_hex'])) for s in segments if s['payload_hex']]
    base = ((next(iter(syns)) + 1) & MASK) if syns else (payloads[0][0]['seq'] if payloads else None)
    has_fin = any(s['flags'] & 1 for s in segments)
    has_reset = any(s['flags'] & 4 for s in segments)
    if base is None:
        return ReassembledStream(b'', None, False, has_fin, has_reset, 0)
    pieces = [(sequence_delta((s['seq'] + bool(s['flags'] & 2)) & MASK, base), data)
              for s, data in payloads]
    if pieces and not syns:
        # A capture without SYN may begin with an out-of-order segment.
        earliest = min(offset for offset, _ in pieces)
        pieces = [(offset - earliest, data) for offset, data in pieces]
        base = (base + earliest) & MASK
    result = bytearray()
    duplicates = 0
    for offset, data in sorted(pieces, key=lambda item: item[0]):
        if offset < 0 or offset + len(data) > max_bytes:
            raise ValueError('TCP sequence range is outside the supported bound')
        if offset > len(result):
            raise ValueError(f'Missing TCP bytes at offset {len(result)} through {offset - 1}')
        overlap = min(len(data), len(result) - offset)
        if result[offset:offset+overlap] != data[:overlap]:
            raise ValueError(f'Conflicting TCP retransmission at offset {offset}')
        duplicates += overlap
        result.extend(data[overlap:])
    for segment in segments:
        if segment['flags'] & 1:
            fin_offset = (sequence_delta(segment['seq'], base) + bool(segment['flags'] & 2)
                          + len(bytes.fromhex(segment['payload_hex'])))
            if fin_offset != len(result):
                raise ValueError('TCP FIN does not match the reconstructed payload end')
    return ReassembledStream(bytes(result), base, bool(syns), has_fin, has_reset, duplicates)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('flow', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    flow = json.loads(args.flow.read_text())
    stream = reassemble(flow['segments'])
    with args.output.open('xb') as output:
        output.write(stream.data)
    print(json.dumps({'bytes': len(stream.data), 'has_syn': stream.has_syn,
                      'has_fin': stream.has_fin, 'has_reset': stream.has_reset,
                      'duplicate_bytes': stream.duplicate_bytes}))


if __name__ == '__main__':
    main()
