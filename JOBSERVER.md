# Aurora JobServer

October 23: per-color raster and mixed printing at 167 DPI passed the three-raster,
two-vector physical test. Pipeline 4 enables them for opaque fills/text with
Pause, Bottom-Up and Invert off. Per-color vector and global bottom-up were
already accepted. See [current acceptance/package status](analysis/per-color-raster-mixed-and-package-20261023.md).
A standalone x64 preview now bundles Python/Tk; the source launcher described
below remains available for development. Clean-machine/Windows 11 installation
validation and public signing remain outstanding.

The owner requested enabled-by-default startup on October 23. Normal desktop
launches now create a new live session for new prints. Prior captures remain
held; an unresolved delivery guard keeps startup in Capture only. Use
`--capture-only` when launching for offline work. Job-level Autostart is unchanged.

The target product workflow is now explicitly [XP-style direct printing](frontend/DIRECT-PRINT.md):
CorelDRAW Print submits artwork/settings and JobServer sends automatically.
The installed printer and the normal JobServer window now implement this flow.
The manual commands and older queue window remain development/diagnostic tools.

The [first integrated CorelDRAW physical print](analysis/integrated-print-live-20261018.md)
has now passed through the native printer and automatic bridge. The owner
started the machine with Autostart off and confirmed the finished engraving
looks right. That one-job host stopped; the installed printer is currently
back in capture-only mode. The normal window adds queue history, connection
status, capture-only/live controls and optional per-user startup.
Its [live window test](analysis/desktop-jobserver-20261018.md) has also passed:
the owner enabled printing, submitted once, pressed machine Start, and accepted
both parts. One upload completed and capture-only mode was restored.

The replacement now has a working **local queue and preparation pipeline**.
It accepts captured `.jbs` jobs, prepares their raster data, and retains originals,
prepared outputs, settings metadata, and event history. The PP_ver5 job processed
through this queue matches the original XP JobServer output byte for byte.

Version 0.2 adds **experimental, explicit Ethernet delivery**. Its full TCP
exchange is tested against a loopback controller simulator; the first physical
Aurora validation is recorded in `runtime/live-validation`. The diagnostic queue does not
automatically send jobs. “Ready” means prepared locally; exporting a file does
not mark it as transmitted or engraved. A separate native Windows test printer
is now installed with laser Properties; see [package status](frontend/PRINTER-PACKAGE.md).
Its receiver currently saves local captures only.

## Normal printing

Double-click `launch-jobserver.cmd` from this project. It uses this computer's
bundled Python runtime when present, falling back to `pythonw` on PATH. This is a
portable Python prototype, not an installed Windows service or standalone EXE.
Python 3.10+ with Tk is required for the GUI. The command-line tools use only the
Python standard library.

Normal launches start with **Laser printing enabled** for new submissions.
Choose **Capture only** (or launch with `--capture-only`) to save CorelDRAW prints
locally with their laser settings and no physical delivery. Existing captures
are never sent merely by restarting or enabling printing.
**Aurora Capture (Preview Only)** continues to save
separate preview captures and never becomes a laser delivery queue.

Prepare the laser, material and focus before printing. If you selected Capture
only, select **Enable laser printing** to resume. New prints convert and deliver automatically,
with no second software Send button. Raster/vector settings still come from
CorelDRAW's printer Properties. Autostart Off requires the machine Start button;
Autostart On may start engraving as soon as a print arrives.

In Properties → Advanced, the established Travel Speed is **0.100 ips**.
The r11 update corrects its earlier display of 100 while preserving the same
working output command. Accepted old material presets migrate automatically
when loaded; other legacy travel values remain held until explicitly changed
to select ips. Changing unrelated controls does not release those held values.
Travel speeds other than 0.100 ips still require validation before delivery.

**Capture only** finishes the current print and holds later prints locally.
Waiting prints can be canceled before conversion starts. Closing the window
finishes the current delivery and accepted Windows print transfers before
exiting. Captures and held jobs from earlier sessions remain history; enabling
printing or restarting never replays them. To intentionally repeat artwork,
submit another Print from CorelDRAW.

Print history includes **Completed** and **Duration**. Completed is the local
computer time when JobServer received the successful completion report.
Duration is the laser's reported job time, displayed as minutes:seconds.milliseconds
(or hours:minutes:seconds.milliseconds for longer jobs). It excludes upload and
time waiting for the machine Start button. The selected print's details include
the full completion date/time and exact reported seconds. Existing completed
history fills these columns automatically from its saved delivery records.
Unsent, active, failed, or operator-confirmed jobs without measured timing show
a dash rather than an estimated physical finish. A horizontal scrollbar keeps
the columns accessible in smaller windows.

**Check connection** requests status on port 29 only. It sends no job and does
not reset the controller. A response establishes communication, not that the
laser is idle or physically ready. Interrupted uploads require an observed
physical outcome before another delivery can proceed. Record that outcome in
capture-only mode; recording it never resends the job.

The optional **Open JobServer when I sign in** checkbox manages only this app's
entry in the current user's Windows Run key. It is off unless explicitly enabled
in the window. Startup still opens in capture-only mode.

Normal window data lives under `runtime/desktop-jobserver`: captures, isolated
live sessions, delivery transcripts, history and rotating `jobserver.log` files.
The app listens only on `127.0.0.1:515`; another local receiver cannot own that
port at the same time. No administrator rights are needed to run the window.

## Diagnostic queue

Double-click `launch-jobserver-tools.cmd` for the older Add job, Export prepared,
Cancel, Retry and history tools. This queue does not automatically deliver jobs.
It automatically prepares submissions and observes `runtime/jobserver/inbox`.

Queue data is stored under `runtime/jobserver`, which is ignored by Git. The
checked reference job is already prepared in a separate `runtime/development`
queue; launch that queue with:

```powershell
python -m aurora_jobserver --state runtime/development gui
```

## Command-line operation

From this project directory, using the bundled Python executable or another
Python 3.10+ interpreter:

```powershell
python -m aurora_jobserver submit path/to/job.jbs
python -m aurora_jobserver process
python -m aurora_jobserver list
python -m aurora_jobserver show FULL-JOB-UUID
python -m aurora_jobserver export FULL-JOB-UUID path/to/new-output.jbs
python -m aurora_jobserver cancel FULL-JOB-UUID
python -m aurora_jobserver retry FULL-JOB-UUID
python -m aurora_jobserver watch
```

Use `--state DIRECTORY` **before** the command to select another queue. Do not
run a desktop preparation worker and a command-line preparation worker on the
same queue simultaneously; an OS file lock prevents this. Submitting jobs and
reading status from another process is supported.

`submit --settings metadata.json` stores a per-job JSON object for future printer
integration. These values are metadata only; they do not override power, speed,
or other commands already embedded in the job.

## Explicit Ethernet delivery

The `send` command performs one attempt, using the selected job's verified
prepared snapshot. It never reconnects to repeat a physical transfer. It supports
the observed CG raster path (including raster jobs with a vector tail), not the
unverified vector-only jobtype branches.

Normal Vector Only printing at 167 DPI uses that same CG envelope with a
one-pixel zero-exposure raster at explicit 0% raster power, then the requested
vector paths. Its square-and-circle physical test was accepted on October 22.
Cut selection uses effective hairline width regardless of stroke color. Fills,
text and images are excluded from Vector Only output. At the current X7
600-DPI source setting, the observed hairline threshold is 0.5 DIP plus numeric
tolerance; thicker outlines do not cut. Other source rendering profiles still
require validation.

If a Vector Only print has no eligible paths, JobServer records “Nothing to cut
— not sent” locally and keeps accepting prints. No network connection, machine
movement, completion beep, or unresolved-delivery marker is produced for that
empty print. Change the outlines to hairline and submit a new Print normally.
Old held captures are never replayed when laser printing is enabled.

Per-color **Vector Only at 167 DPI** is supported after the owner's five-path
physical test. Select Vector Only and Use Color Settings in Properties, then
set power/speed/PPI for the colors used by the drawing in Color Settings. Those
palette values replace the global vector settings for that job. Hairline width
still selects cuts regardless of color. JobServer labels these prints Per-color
and shows the saved palette in their details.

Use whole-percent palette powers and vector speeds no higher than 15 ips.
Color matching uses the original exact RGB palette; unmatched RGB uses the
White entry's process. Pauses combined with disabled/zero-power paths remain
held. With pauses off, all-disabled colors are recorded locally as Nothing to
cut. Raster/mixed per-color output remains held; ordinary global raster/mixed
printing is unchanged. See [integration and physical result](analysis/per-color-vector-integration-20261022.md).

**Bottom-Up Engraving at 167 DPI** is implemented and physically verified.
Select Bottom-Up Engraving in the first Properties tab. It engraves from the
artwork's lower edge upward while preserving its upright appearance and placement.
The accepted raster-only test used 30 ips/45%, finished in 81.680 seconds, and had
no missing bands or unexpected marks. Other resolutions remain held for this
option. See [physical result](analysis/bottom-up-physical-validation-20261022.md).

```powershell
python -m aurora_jobserver send FULL-JOB-UUID --host CONTROLLER-IPV4
```

This is a physical send command: existing automatic-start commands are retained,
so the laser can start immediately. For the first replacement test, close the XP
JobServer, prepare the laser for the same recorded small test job, and coordinate
the test with the operator. The owner has confirmed normal engraving start for
the first replacement test and confirms that the completed engraving looks the
same as XP. The controller reported 202.0400 seconds and the same known token
warning. See [the live validation record](analysis/live-validation-20261017.md).

Default ports are 23 (main), 29 (status), and 30 (realtime), with a 7,200-second
upload/completion deadline. `--main-port`, `--status-port`, `--realtime-port`, and
`--timeout` override these. The host
must be a literal unicast IPv4 address. `--controller-path` changes the textual
JM_PATH metadata, not the source file or local output location; it defaults to
`c:\xfiles\jbs\Convert\Default.jbs`.

The connection layer opens main, status, and realtime channels in that order and
keeps them for the attempt. It permits the captured `0x1200` startup status but
requires `0x0200` after initial synchronization, plus byte-6 value 2. It checks the captured feature
values 5459 / 330476101. It rejects custom pre-job table contents before upload.
These are compatibility checks for this specific controller profile; the status
values are not a verified general-purpose machine readiness definition.

The transport uses nonblocking duplex I/O, bounded replies, and deadlines, so it
continues reading controller output while writing large jobs. It requests
`host_terminate` after the observed channel 5 end notification, then records the
channel 80 job-time / final marker. Controller warnings remain visible in a
`completed_with_warning` result.

Synchronization follows the native library: wait 500 ms and drain available
replies, including when there is no prompt. Feature replies may include command
echo or just `#` plus ten decimal digits, followed by CR/LF and byte `01`. Both
forms have been observed from this machine. No realtime application payload is
sent in the supported path.

Close XP JobServer before live delivery. For a stale connection, the explicit
`--reset-connection` option uses the native library's port-99 recovery action.
It disconnects existing controller clients and must only be used with the
machine idle and no unresolved physical delivery. The default sender never
automatically invokes it. The controller can refuse that connection even when
the recovery action works; the native code also continues after refusal. The
sender then still requires valid status, matching features, and the pre-job
handshake before uploading. `--recovery-port` changes that port for a simulator.

## Delivery persistence and recovery

Each attempt has a UUID, endpoint snapshot, stage history, result or error, and
raw status/main TX/RX transcripts under `jobs/JOB-UUID/deliveries/ATTEMPT-UUID`.
The queue changes through `connecting → uploading → awaiting_report → completed`
(or `completed_with_warning`). The upload boundary is committed before the first
job upload byte is offered to the socket.

- Failure before upload becomes `delivery_failed`. Retry is an explicit action.
- Failure or process interruption after upload begins becomes `delivery_unknown`.
  Cancel and Retry cannot relabel or requeue that job.
- An exclusive controller lock serializes senders across queues using the same
  lock directory. The default is this project's `runtime/device-locks`; all
  application copies must share a `--locks DIRECTORY` to coordinate across
  separate installations. This local lock does not prove ownership against XP
  JobServer or other computers.
- Before upload, a durable controller marker records the queue, job, and attempt.
  It is cleared after recorded completion. An unresolved marker blocks another
  send, including one from a different queue using that lock directory.
- The queue migrates the older schema transactionally, preserving existing jobs,
  events and inbox receipts. It saves `queue-v1-backup.sqlite3` before rebuilding
  the original state constraint.

Recover an interrupted sender's records while holding its controller lock:

```powershell
python -m aurora_jobserver recover-deliveries --host CONTROLLER-IPV4
```

Recovery never sends data. An interrupted connection with no upload boundary is
retryable; one that crossed the boundary remains uncertain. After the operator
checks what happened at the machine, record the observed outcome:

```powershell
python -m aurora_jobserver resolve-delivery JOB-UUID --outcome completed --note "Operator verified the finished job and idle machine"
python -m aurora_jobserver resolve-delivery JOB-UUID --outcome not_started --note "Operator confirmed no engraving started"
python -m aurora_jobserver resolve-delivery JOB-UUID --outcome stopped --note "Operator confirmed the job was stopped and the laser is idle"
```

Only use an outcome that was actually established. `completed` retains a warning
that the result was reconciled by the operator. `not_started` makes explicit Retry
available again. `stopped` records a job that began but was stopped before
finishing, after the operator confirms the laser is idle. It is recorded as a
failed delivery, preserving the observation and earlier error in its history.
Resolving any outcome does not resend the job or enable laser printing.
No network stop/cancel operation has been reverse engineered;
the local Cancel button cannot stop an active physical engraving.

## Repeatable simulator check

The simulator binds only to `127.0.0.1` and uses four temporary TCP ports. It
expects one known job and exits after that session. Start it in one terminal:

```powershell
python -m tools.controller_simulator path/to/known-job.jbs --warning
```

It prints the ports as JSON. In another terminal, submit and prepare that
same job in a test queue, then send it to those ports:

```powershell
python -m aurora_jobserver --state runtime/simulator-demo submit path/to/known-job.jbs
python -m aurora_jobserver --state runtime/simulator-demo process
python -m aurora_jobserver --state runtime/simulator-demo send JOB-UUID --host 127.0.0.1 --main-port MAIN-PORT --status-port STATUS-PORT --realtime-port REALTIME-PORT --recovery-port RECOVERY-PORT
```

An actual CLI demonstration with the captured small job is saved in
`runtime/simulator-demo`. It completed as `completed_with_warning` and reproduced
the original main-channel stream SHA-256
`79f517a636e84fcc45fa796557ef718c8f91ff53d3f32746ffb6049cfa34fc59`.
The warning and 202.014-second report were supplied by the simulator; they are
not a new measurement of the laser. The same captured job is used by the separate
`runtime/live-validation` queue; `test-job.json` identifies the selected job and
its hash. Read the queue's saved delivery record for its current live-test state.

## Persistent queue behavior

- Every submission receives a UUID and its own `jobs/UUID` directory.
- `source.jbs` and `settings.json` are captured before the queue entry commits.
  Modifying the original source afterward does not change the queued snapshot.
- SQLite transactions record `queued → preparing → ready`, with separate failed
  and canceled states and an event history. Jobs and history are not deleted on
  exit.
- A failed job does not block later jobs. Retry is explicit. Cancellation during
  preparation cannot be overwritten by the worker's completion update.
- An interrupted preparation is requeued at the next worker start, while holding
  the exclusive worker lock. Since this phase performs no device delivery,
  repeating preparation does not risk repeating a physical job.
- Source and prepared-file SHA-256 hashes are checked before use/export.
- Export refuses to overwrite an existing destination and leaves the job ready.
  The prepared file retains the original start/autostart commands.

## Inbox handoff for the future printer frontend

Write each complete job under a temporary extension, then rename it to a unique
`.jbs` filename in the inbox. Publish only after the final bytes have been flushed
and the file has been closed. Atomic publication is the intended handoff.

The current watcher additionally requires two unchanged observations and an
`END_PLOT` footer. It leaves source files in place and records durable receipts,
so restarting the watcher does not enqueue the same observed file again. A new
timestamp/size generation is eligible again, allowing intentional repeat prints
even when the content is identical. This stability heuristic is not a substitute
for atomic publication by the new printer frontend.

The old XP driver has **not** been redirected into this inbox. Its registry,
JobServer settings, and printer remain unchanged.

## Input support

- Observed raw raster encoding (`C3 58`, flags `0x41`): validate and compress.
- Observed compressed encoding (`63 47`, flags `0xc1`): validate and preserve.
- Textual vector-only JBS: preserve, after checking framing and completion.
- Empty `.prn`, incomplete output, unknown picture encodings, mixed raster
  encodings, and invalid row data: reject or record as failed.

The converter is verified against one confirmed mixed raster/vector print. It
does not yet implement every original JobServer feature, DBI editing, firmware
updates, serial delivery, rubber-stamp conversion, or arbitrary other controllers.

## VirtualBox access and next Ethernet evidence

The working driver is inside the running `LaserLaptop` XP VM on this computer:

- VirtualBox 7.0.14; VM UUID `86b4c234-1ba8-4bf6-b47b-49f93e525f24`.
- Guest IP `192.168.1.239`; laser configuration `192.168.1.244`.
- NIC 1 is bridged to the physical Intel Ethernet adapter.
- Downloads is shared into the guest at `Z:\`.

A bounded 20-second passive NIC trace captured the existing control connection.
It was stopped and VirtualBox's original tracing state restored (`off`, file
`none`), as confirmed by `showvminfo`.

Four requests at roughly four-second intervals were observed on TCP port 29:

```text
XP → controller: FF E0 01
controller → XP: FF E1 01 00 00 02 02 00
```

The request bytes match code at `ETCComX.ocx` VA `0x1000edb0`; its routine at
`0x1000ef90` reads eight response bytes. Offline decoding in
`aurora_jobserver/protocol.py` implements only this observed reply shape and the
original library's numeric state calculation. State code 1 has not been labeled
“ready to engrave”; its physical meaning still needs confirmation.

The owner then restarted JobServer and sent a normal small test job during a
second host-side capture. This captured the new connection handshake, complete
upload, controller warning, and completion report. Tracing is stopped and its
original configuration restored again. No test print or new controller
connection was initiated by the replacement code.

The offline wire builder now reproduces all 19,340 main-channel request bytes
from that session, including the 18,994-byte compressed raster job. The reply
decoder handles fragmented reads and the controller's two-byte channel
selectors. See [the complete session findings](analysis/ethernet-session-20261017.md)
for byte counts, timing, hashes, static corroboration, and remaining questions.

The controller warning is `Error 2: Token 'set_xyup_feed' not found.` It comes
from a command in the original XP job. The owner reports that the print looks
complete; the controller reports `JOB_TIME 202.0140`. Its significance still
needs investigation. The captured completion ordering also shows that
`host_terminate` is sent before the job-time report and final `04 AC`.
`aurora_jobserver/delivery.py` now tracks this ordering offline, records the
captured warning, and treats interrupted transfers as uncertain. Live sending
is now connected to the explicit sender and durable delivery records. The first
physical test exposed the required connection order, absent prompts when echo is
disabled, and refused port-99 recovery behavior; those are covered by regression
tests.

VirtualBox documents runtime NIC tracing in its
[controlvm reference](https://docs.oracle.com/en/virtualization/virtualbox/7.0/user/vboxmanage.html).

Private capture files and decoded flow records are under `captures/network`.
`tools/inspect_pcap.py` filters inspection to the configured controller address.
It is a packet-summary tool, not a general TCP/IP reassembly implementation.
`tools/reassemble_tcp.py` adds strict bounded stream reconstruction, and
`tools/analyze_job_session.py` extracts supported jobs and reply events offline.

## Validation

The suite covers persistent restart, interrupted-worker recovery, exclusive
worker locking, cancellation races, source immutability, settings snapshots,
inbox partial files and repeat prints, output integrity, raw and compressed
validation, and exact conversion against XP output. It also checks the observed
status frame across fragmented and coalesced TCP reads. The 49-test suite now
includes the startup/job trace, byte-exact transfer construction, reply channel
changes, sequence wrap, gaps, conflicting TCP retransmissions, and the observed
completion sequence including uncertain-delivery handling. The loopback TCP
simulator requires host termination before returning its job-time report and
exercises fragmented replies, custom-table rejection, profile mismatch,
disconnects, timeouts, controller locks across queues, database migration, and
large uploads with small socket buffers and substantial reply backpressure. It
also covers startup status transitions, a controller with echo disabled, and
explicit recovery with both accepted and refused port-99 connections.
The first physical job's actual no-echo reply stream is preserved as a small
regression fixture without artwork or license data and replayed byte by byte.

The actual desktop event loop was initialized hidden on this host, populated
from the prepared reference queue, and closed automatically without callback
errors. This is a functional smoke check, not a complete visual layout review.
Windows 11-specific printer integration has not been tested. The first physical
delivery passed as recorded above. A separate [frontend prototype](frontend/README.md)
now reads Microsoft XPS pages into offline engraving and cutting previews; it
also supports [offline JBS drafts](frontend/ARTWORK-DRAFTS.md). Those remain
uncalibrated and the ordinary queue worker and sender reject their draft marker.
They are not automatically submitted or delivered.

The owner has accepted the current X7 lettering. A separate constrained
[calibration staging tool](frontend/CALIBRATION-TEST.md) now prepares only the
exact reviewed square-and-TEST job for physical measurement. Its complete
compressed file passed the loopback simulator and the first physical test:
the owner reports a one-inch square and complete but too-light raster text.
The next candidate increases raster power from 30% to 45%, retaining 30 ips
and the vector settings. The owner subsequently authorized it and reported
manual Start; the controller reported completion in 9.800 seconds. The owner
accepted the result as recorded in the [45% test record](analysis/power45-calibration-live-20261018.md).
See the [physical result](analysis/generated-calibration-live-20261017.md).
This does not change ordinary draft rejection or start an automatic
print-to-laser path. Current Python validation is 80 passing tests.
