# First physical test of newly generated X7 artwork

The owner accepted the X7 lettering, then explicitly authorized the staged
square-and-TEST calibration job. The replacement generated and delivered it
from the host without the XP driver/JobServer in the delivery path. The owner
reported manual Start, completed raster engraving, and a square measuring one
inch. The raster was too light; the owner requested a 50% relative power increase
for the next test. That means raster power 30% -> 45%, with speed 30 ips and
vector 1 ips / 15% / 1000 PPI retained.

This confirms a completed physical test and the reported one-inch dimension,
not general production calibration. Separate width/height, measurement precision
and bed-origin offsets were not supplied. No geometric scale correction was
applied. The original generic artwork paths remain draft-blocked.

## Delivery evidence

- Queue: `runtime/calibration-physical-test-167/queue`.
- Job: `bf07ee8f-afa8-4eb0-a7e7-370014cf95cd`.
- Successful delivery: `305b82a4-7cb5-48de-821a-d43fd6b5e80a`.
- Prepared CG: 948 bytes, SHA-256
  `376affd16d87733d506de26618d0ac6105b797a3a98523bcd6afca34b7e0034a`.
- Main TX: 1,294 bytes, SHA-256
  `ad557a7c03ebbe1c53928510c2c8415c3ecfd26cb039017ce66683c375755243`.
- Main RX: 528 bytes, SHA-256
  `834c4efef0a3ca66e3c14ac36ff7bed911b73459836ec3068e45b8eeb4125a0d`.
- Controller time: 9.818 seconds; end code 0; `completed_with_warning`.
- Both status frames: `ffe1010000020200`; features 5459 and 330476101.
- Exactly one upload event. Actual main TX matches the planned stream exactly.

The initial connection was actively refused before any job bytes were sent.
The already-authorized unsent job was then retried with the previously verified
legacy connection-recovery sequence. Port 99 itself refused the connection,
then main/status/realtime channels and full preflight succeeded. As in the
earlier sender validation, this establishes a working sequence, not which
individual recovery step is necessary. No upload was repeated and no job was
sent after the successful completion.

The known `set_xyup_feed` token warning recurred. Its first line is joined to
firmware debug text about laser scale/iterations/Speed/Power. Further debug
lines, the raster acknowledgement, two Manual Power lines and the final channel
messages are retained in full. The debug Power values are not interpreted as
verified laser-output percentages. Similar debug text occurred in the earlier
XP-reference replay. The raw command settings are independently checked.

The active-delivery marker was cleared after the completion record was saved.
The owner's readiness, manual Start and final observation are recorded as job
events. `live-validation-summary.json`, `physical-delivery-result.json` and
`measurements.json` are alongside the queue. Per-job metadata containing the
original staged `operator_ready=false` is an immutable staging snapshot; the
later authorization receipt/events establish the actual readiness decision.

## 45% candidate

Update: the owner authorized this candidate on October 18. It was delivered
once and the controller reported completion in 9.800 seconds. See the
[45% physical test](power45-calibration-live-20261018.md). The staging and
authorization notes below describe its state before that subsequent test.

`runtime/calibration-square-test-167-power45` contains the same geometry and
exposure bytes, raster speed 30 ips, raster power 45%, and unchanged vectors.
Its title is `AuroraCal167P45`. Its raw commands differ from the first test only
in title and the single raster power command. The constrained staging path
accepts only the reviewed 30% and owner-requested 45% variants, not arbitrary
artwork or a general draft-release switch.

- Raw: 6,203 bytes, SHA-256
  `528429b18393de89cbb386b97656a94ddba5000411b43dba2b19350adaea8c5c`.
- CG: 943 bytes, SHA-256
  `1c0915fe73473ae92991e13d62ecd628fc52c2f95093139ea621dba3b91fe806`.
- `runtime/coreldraw-next-settings.json` records the next-test process settings.

The 45% candidate has not been physically sent. The prior readiness authorization
was for the completed 30% test. Wait for a new readiness instruction before
executing the next physical job. No approval or calibration status is inferred
for other material, settings, artwork or Windows 11 installations.

The actual reply stream is preserved without artwork/license data as
`tests/fixtures/aurora-square-calibration.json` and replayed one byte at a time
through the parsers and delivery tracker. Additional staging tests ensure the
45% variant changes only raster power/title, retains Autostart off, and rejects
unreviewed power values. The full Python suite passes 80 tests; the frontend's
24 checks remain passing from the latest frontend build.
