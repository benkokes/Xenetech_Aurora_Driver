# Aurora startup and raster-job Ethernet capture

The owner restarted XP JobServer and sent a normal small test job while the host
recorded the `LaserLaptop` VM's bridged NIC. The owner reports that the print
looks complete, with a token warning on the engraver display. No job was sent by
the replacement software. The trace is stopped; VirtualBox reports `Trace: off
(file: none)` again.

## Preserved evidence

Private originals and generated data are ignored by Git:

- PCAP: `captures/network/startup-job-20261017-01.pcap`, 1,133,557 bytes,
  SHA-256 `7c0454a06c5f718aab90fe3ec7569dbe637998d8ce9bfa154479009e63cd687a`.
- Per-packet records: `captures/network/startup-job-20261017-01-decoded`.
- Reassembled streams, extracted job and current report:
  `captures/network/startup-job-20261017-01-session-v2`.
- Decompressed raster: `captures/network/startup-job-20261017-01-raster`.

The PCAP has 4,863 Ethernet packets, including other guest traffic. Device-filtered
records show the old connections closing and new connections being attempted.
The new main connection is `192.168.1.239:1061 → 192.168.1.244:23`; status uses
port 29. Port 30 has connection traffic but no application payload in this trace.

The main connection contains 19,340 bytes from XP and 681 bytes from the
controller. Both SYNs were captured. Strict sequence-based reconstruction finds
no gaps, conflicting overlaps, or duplicated payload bytes; TCP acknowledgments
cover both entire payloads. The connection stays open after the job, so the
capture is not a recording of its entire lifetime. TCP acknowledgment is not
evidence of successful engraving.

## Observed exchanges

The old main connection receives `\nHPGL\n` during shutdown. The new main
connection receives the following sequence, with response processing and delays
between the steps:

1. `\nM99\n!ZX\n` twice.
2. `\n0 dsp_feature 1 wchar\n`, with decimal reply `#0000005459` and byte `01`.
3. `1 dsp_feature 1 wchar\n`, with decimal reply `#0330476101` and byte `01`.
4. After the owner submits a job, `\nM99\n!ZX\n` again.
5. `\n1 wchar pre_job_table\r`, with a reply containing `01 04`. No custom
   pre-job table body is present in this example.
6. Preprocessing/display commands, `ifexists jobtype 5 jobtype`, `JM_PATH`,
   `HOTWATCH_CYCLE_START`, and the complete compressed JBS job.
7. After the engraving, `ifexists host_terminate host_terminate\n`.

The metadata path in this session is
`c:\xfiles\jbs\Convert\Default.jbs`. It is sent as controller command text;
this does not establish any need for the replacement's files to live there.

The archived `ETCComX.ocx` corroborates synchronization at VA `0x10006440`
(including its 500 ms delay), feature queries at `0x10006841` and `0x10006917`,
and the pre-job query at `0x100086ae` (waiting for byte `04`). The archived
JobServer 3.9.40.0 has matching framing templates at `0x0040ba2b` / `0x0040ba74`.
Its raster conversion success branch emits jobtype 5 at `0x00419199`. Other
conversion paths use other jobtypes; these have not been generalized into a
live sender.

## Extracted job

The 18,994-byte JBS begins at stream offset 307 and ends at offset 19,301.
SHA-256: `946b6bb7e0445025a135be243d7edd0d3817f8ae5c583fda708a6703f568a0f0`.

It has one 1490 × 532 CG/LZW raster, resolution fields 167000, flags `0xc1`, and
an `autostart START` command. Decompression produces 793,744 bytes and validates
all 532 row trailers. Decoded SHA-256:
`d75f275d111683d0c691046b0736d1a206ad6c417c0672ceceb1c5711ca4693d`.

The existing JobServer input validator accepts this second, independently
captured compressed job without changing it. Only the earlier PP_ver5 raw / XP
converted pair establishes byte-exact raw-to-compressed conversion; this capture
does not include the second job's raw source file.

## Token warning and completion sequence

The controller reports the exact warning:

```text
Error 2: Token 'set_xyup_feed' not found.
```

The uploaded JBS contains `100. set_xyup_feed\r`. This warning occurs with the
original XP driver and original JobServer; it was not introduced by replacement
code. The controller continues processing, the owner reports a complete-looking
print, and the controller later reports `JOB_TIME 202.0140`. This does not prove
that the unsupported setting has no effect. Preserve the command and warning
while investigating its intended meaning; do not silently delete it.

The firmware does not terminate the error with a newline before its first
`laser scale=...` diagnostic. The reply parser preserves that full line.

The late stream includes:

```text
AD 05 06 45 30 06 AC AD 50 0A 0D
                  E  0           (50 is ASCII P)
JOB_TIME 202.0140 0A 0D 04 AC
```

`AD` consumes the next byte as a channel identifier. This is corroborated by the
`ETCComX.ocx` dispatch table: `AD → 0x10007983`, which appends the next byte
without processing it as another control character. The observed channel
identifiers are 5 and 80 (`0x50`). Thus `AD 05` is a channel selection, rather
than two independent control events. The parser carries channel context across
fragmented TCP reads; `AC` terminates a channel message and clears the context.

Tracing the archived JobServer handler resolves the late ordering:
`0x004133c3` dispatches `AC` by channel; channel 5 goes through `0x00413507`
to `0x0040aa40`. That handler checks the message's `06 E` prefix and sends
`host_terminate` at `0x0040aae1`, then displays “Job Complete” / returns to inbox
processing. Channel 80 dispatches at `0x004134de` to `0x00412d60`, which parses
`JOB_TIME` at `0x00412dcc`. The replacement recognizes only the observed channel
5 payload `06 E0 06`; other end codes remain uncertain.

The owner-facing job-time report and final `04 AC` occur **after** XP sends
`host_terminate`. The host's TCP ACK on that write covers 660 controller bytes;
`JOB_TIME` starts at controller offset 660 and final `04` at 679. Therefore a
sender that waits for `JOB_TIME` and final `04` before sending `host_terminate`
would not reproduce the observed ordering. It might wait indefinitely on a
different firmware implementation. Byte `04` also occurs in the pre-job reply,
so it must not globally mean “engraving complete.”

Status queries on port 29 stop during the job in this capture. The first status
after startup has flags `0x1200`; subsequent observed replies have `0x0200`.
These are still raw flags / legacy numeric codes, not verified machine-state
labels.

## Implemented from this evidence

- `tools/reassemble_tcp.py`: bounded, sequence-aware reconstruction, including
  retransmissions, overlap conflicts, gaps, sequence wrap, SYN and FIN checks.
- `tools/analyze_job_session.py`: extract supported complete jobs and preserve
  the framing, replies, channel changes, errors, and byte-acknowledgment context.
- `aurora_jobserver/replies.py`: incremental port-23 reply decoder, independent
  of TCP segmentation; exposes controls and complete channel messages.
- `aurora_jobserver/wire.py`: offline construction of the observed raster-job
  framing. Given the extracted job and metadata path, its concatenated requests
  reproduce all 19,340 bytes of the captured main-channel client stream exactly.
  This is not a network sender; steps have response gates and must not be blindly
  concatenated and replayed.
- `aurora_jobserver/delivery.py`: offline tracking for one explicitly started
  delivery attempt. It ignores pre-job `04`, requests `host_terminate` once after
  the channel 5 end message, and then requires the channel 80 job-time / `04 AC`
  report. The captured session finishes as `completed_with_warning`. Disconnects
  during delivery and unrecognized end codes yield `delivery_unknown`, with no
  automatic retry. It does not open sockets or change the persistent queue.

The suite now has 34 passing tests, covering the capture, complete transfer-byte
comparison, stream fragmentation, channel selectors, missing data, conflicting
retransmissions, sequence wrap, bounded input, completion ordering, duplicate
notifications, unknown delivery outcomes, and the persistent queue / codec.

The remaining Ethernet work is to implement the connection/session transport
and device ownership behavior, connect delivery tracking to the persistent queue,
and verify it with a local controller simulator before a controlled live test.
Interrupted physical transfers must become an uncertain-delivery state rather
than automatically repeating a job. No new capture is required from the owner
just to recover the token wording.

Subsequent work in version 0.2 implemented the explicit TCP sender, persistent
delivery attempts, shared controller locks and uncertainty markers, plus a
loopback simulator. The suite now has 44 passing tests. A real command-line
simulation reproduces this captured client stream byte for byte. Physical
compatibility testing remains outstanding; see [current sender documentation](../JOBSERVER.md).
