"""Summarize classic Ethernet PCAP traffic for one engraver, without networking."""
import argparse
from collections import defaultdict
import ipaddress
import json
from pathlib import Path
import socket
import struct


def packets(path):
    with path.open("rb") as source:
        header = source.read(24)
        if len(header) != 24 or header[:4] not in (b"\xd4\xc3\xb2\xa1", b"\xa1\xb2\xc3\xd4"):
            raise ValueError("Expected classic microsecond PCAP")
        endian = "<" if header[:4] == b"\xd4\xc3\xb2\xa1" else ">"
        if struct.unpack_from(endian+"I", header, 20)[0] != 1:
            raise ValueError("Expected Ethernet link type")
        while record := source.read(16):
            if len(record) != 16:
                raise ValueError("Truncated PCAP record")
            seconds, micros, captured, original = struct.unpack(endian+"IIII", record)
            if captured > 16*1024*1024:
                raise ValueError("Unreasonable PCAP packet size")
            frame = source.read(captured)
            if len(frame) != captured:
                raise ValueError("Truncated packet")
            yield seconds+micros/1_000_000, frame


def inspect(path, device, output):
    flows = defaultdict(list)
    udp = []
    seen = 0
    for timestamp, frame in packets(path):
        seen += 1
        if len(frame) < 34:
            continue
        ether_type = struct.unpack_from("!H", frame, 12)[0]
        offset = 14
        if ether_type == 0x8100 and len(frame) >= 38:
            ether_type = struct.unpack_from("!H", frame, 16)[0]
            offset = 18
        if ether_type != 0x0800:
            continue
        ip = frame[offset:]
        ihl = (ip[0] & 15)*4
        if ihl < 20 or len(ip) < ihl:
            continue
        size = struct.unpack_from("!H", ip, 2)[0]
        src, dst = socket.inet_ntoa(ip[12:16]), socket.inet_ntoa(ip[16:20])
        if device not in (src, dst):
            continue
        # Fragmented packets need IP reassembly, which this inspection tool doesn't implement.
        if struct.unpack_from("!H", ip, 6)[0] & 0x3fff:
            raise ValueError("Fragmented device traffic requires a full packet analyzer")
        transport = ip[ihl:size]
        if ip[9] == 6 and len(transport) >= 20:
            sport, dport, seq, ack = struct.unpack_from("!HHII", transport)
            header_length = (transport[12] >> 4)*4
            payload = transport[header_length:]
            key = (src, sport, dst, dport)
            flows[key].append({"time": timestamp, "seq": seq, "ack": ack, "flags": transport[13],
                               "payload_hex": payload.hex()})
        elif ip[9] == 17 and len(transport) >= 8:
            sport, dport = struct.unpack_from("!HH", transport)
            udp.append({"time": timestamp, "src": src, "sport": sport, "dst": dst, "dport": dport,
                        "payload_hex": transport[8:].hex()})
    output.mkdir(parents=True, exist_ok=True)
    summaries = []
    for number, (key, segments) in enumerate(sorted(flows.items()), 1):
        payloads = [bytes.fromhex(s["payload_hex"]) for s in segments if s["payload_hex"]]
        entry = {"src": key[0], "sport": key[1], "dst": key[2], "dport": key[3],
                 "packets": len(segments), "payload_packets": len(payloads),
                 "payload_bytes_including_retransmissions": sum(map(len, payloads)),
                 "prefix_hex": b"".join(payloads)[:128].hex()}
        (output / f"flow-{number:02d}.json").write_text(json.dumps({"flow": entry, "segments": segments}, indent=2))
        summaries.append(entry)
    result = {"pcap": str(path), "device": device, "total_packets": seen, "tcp_flows": summaries, "udp": udp}
    (output / "summary.json").write_text(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pcap", type=Path)
    parser.add_argument("--device", default="192.168.1.244")
    parser.add_argument("--output", type=Path, default=Path("captures/network/decoded"))
    args = parser.parse_args()
    ipaddress.ip_address(args.device)
    result = inspect(args.pcap, args.device, args.output)
    print(json.dumps({k: v for k, v in result.items() if k != "udp"}))
    print(json.dumps({"device_udp_packets": len(result["udp"])}))


if __name__ == "__main__":
    main()
