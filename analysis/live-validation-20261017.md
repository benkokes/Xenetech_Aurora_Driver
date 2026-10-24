# First replacement-sender physical validation

The replacement sent one approved small raster job directly from this host to
the Aurora. The owner confirmed normal engraving start and then confirmed that
the completed engraving looks the same as the original XP test. The controller
reported `JOB_TIME 202.0400`, end code `0`, and the same `set_xyup_feed` token
warning already observed under XP. The queue saved `completed_with_warning`.

The complete main-channel client stream matches the original XP session byte
for byte, including handshake commands, preprocessing, metadata, compressed JBS,
and final host termination. No further job was sent after completion.

## Evidence and scope

- Queue: `runtime/live-validation`.
- Job ID: `0c5ecd50-db33-417b-bfa1-bcc8a9eca6a4`.
- Successful attempt: `e3fd2c72-6aa9-4183-9f44-dd8c72594a13`.
- Prepared input: 18,994 bytes, one 1490 × 532 CG raster, original automatic-start
  command retained. SHA-256:
  `946b6bb7e0445025a135be243d7edd0d3817f8ae5c583fda708a6703f568a0f0`.
- Actual main TX: 19,340 bytes. SHA-256:
  `79f517a636e84fcc45fa796557ef718c8f91ff53d3f32746ffb6049cfa34fc59`.
  This is identical to the reassembled original XP client stream.
- Actual main RX: 313 bytes. SHA-256:
  `d4350dd252b7801c81c089979a9966449fa3800eb9f292042ceb24963bfb0abe`.
- Raw TX/RX transcripts and per-attempt event history are retained under the job.
- Summary: `runtime/live-validation/live-test-result.json`.
- A small copy of the controller replies, without job artwork or license fields,
  is tracked as `tests/fixtures/aurora-live-no-echo.json`.

The active-delivery marker was cleared only after completion was recorded. The
queue also records the owner's final visual confirmation as an event. This
validates one specific raster transfer path on the current Windows host; it is
not validation of every controller feature, vector-only jobtype, Windows 11
print integration, or unattended production use.

## Startup behavior learned from the live test

Three recorded attempts failed before the upload boundary. The first rejected
startup status `0x1200`; the second required a synchronization prompt that was
absent; the third treated the recovery port's refusal as fatal. All have
`upload_started=false`; none transmitted the test job. Diagnostic probes also
used only connection, status, synchronization and feature-query messages.

The working sequence uses the original library's optional connection-recovery
action, opens main/status/realtime ports 23/29/30, drains synchronization replies
after a timed wait, accepts the actual bare feature responses, and validates the
pre-job response before crossing the durable upload boundary. These differences
were added to the simulator and regression tests before the successful upload.

The native synchronizer at `ETCComX.ocx` VA `0x10006440` does not require a prompt:
it sends the synchronization string, waits 500 ms, drains available bytes, and
returns even when nothing was received. Actual host-side feature replies were:

```text
#0000005459 LF CR 01
#0330476101 LF CR 01
```

The original XP trace contained command echo and prompts. The replacement now
accepts both observed forms while still requiring the exact feature values.

The controller returned `0x1200` during early connection setup and `0x0200` in
the working session. Opening the realtime channel correlated with that change;
these observations do not establish the general physical meaning of that flag.
The realtime connection carried no application payload in the supported path.

Port 99 returned a connection refusal even during the diagnostic that restored
communication. The native recovery code near VA `0x1000ba74` also ignores the
connect result before attempting to reconnect. The explicit reset option
therefore permits refusal but still requires the subsequent status, feature,
and pre-job checks. It never bypasses an uncertain-delivery marker or repeats an
interrupted physical upload. This connection reset is not a physical stop command.

The checks establish a working sequence; they do not independently prove which
individual connection details are strictly required by every firmware variant.

## Known warning and completion

The unchanged job includes `100. set_xyup_feed`. The controller reports:

```text
Error 2: Token 'set_xyup_feed' not found.
```

It continues engraving and sends the channel 5 end notification. The replacement
then sends `host_terminate` once and receives the channel 80 job-time / final
marker. The warning is retained in the result rather than silently removed or
treated as an interrupted transfer. The owner confirms the print looks complete
and matches XP. The intended effect of the unsupported command is still unknown.

The full suite has 49 passing tests, including real sockets against the loopback
simulator, startup-status transition, absent echo, accepted/refused recovery,
partial uploads and disconnects, cross-queue locking, persistent recovery and
schema migration. The actual live reply fixture is replayed one byte at a time,
checking feature values, exactly one termination action, warning retention, and
the final 202.04-second completion report.
