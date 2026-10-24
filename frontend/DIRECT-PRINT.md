# XP-style direct printing

The owner requires the XP workflow: choose the Xenetech printer and its laser
settings in CorelDRAW, then click Print. JobServer bridges the print job to the
Aurora automatically. A review window with a second Send button is not the
normal workflow.

```text
CorelDRAW Print + printer Properties
    -> Windows spooler: artwork and immutable per-job laser settings
    -> artwork intake and JBS encoding
    -> JobServer: durable queue and automatic Ethernet delivery
    -> Aurora
```

The printer Properties must carry raster speed/power, vector speed/power/PPI,
resolution, output mode, plate size/offset, focus and Autostart as those features
are implemented. Unsupported controls must not silently accept settings that
the encoder cannot honor. A print's settings must travel with that print;
JobServer must not read mutable current defaults when an older queued job runs.

Automatic delivery and the laser's Autostart are separate. Clicking Print must
deliver the job without another software Send action. Whether the laser starts
engraving immediately or waits for its physical Start button follows the
per-job Autostart setting, as in XP. The two calibration jobs used Autostart off;
their manual Start requirement is not the intended permanent print workflow.

The JobServer window is for connection, queue status, failures, cancellation
before delivery and history. Preview can be optional. Successful normal prints
must not need per-job approval or a second application interaction. A failed
or uncertain transmission needs attention rather than an automatic repeat.

## Implemented automatic-dispatch backend

`aurora_jobserver.direct_print.DirectPrintBridge` accepts an already encoded
job, its durable print UUID and its settings snapshot into a dedicated queue.
The background caller repeatedly invokes `step()`: it prepares and sends the
oldest pending print automatically, preserving the existing native commands.
No per-job Send call from the user is needed. The native printer, conversion
pipeline and normal [JobServer window](../JOBSERVER.md) now use this backend.

- Re-delivering the same receipt does not create another engraving. A deliberate
  second Print uses another UUID, even when the artwork is identical.
- A reused receipt with changed bytes/settings is rejected.
- Settings and validated input bytes are snapshotted before publication.
- The controller target is pinned per print. A changed target or mixed manual
  queue blocks dispatch instead of sending old jobs to a newly chosen device.
- Preparation may recover after a crash. Interrupted delivery, failed preflight
  and uncertain uploads stop automatic dispatch, without retry or connection
  reset. The existing controller lock and durable uncertainty guard apply.
- Ordinary uncalibrated drafts and the unsupported vector-only transfer branch
  remain rejected. Metadata does not override laser commands after encoding.

Loopback controller tests cover automatic delivery, receipt replay after
restart, per-print settings, print order, changed source files, target changes,
preflight failures, uncertain uploads and interrupted preparation/delivery.
They make no connections to the physical Aurora.
All 115 Python tests pass, including desktop lifecycle, direct-print backend,
native ticket fixture and automatic conversion/dispatch integration tests.

## Windows integration

The [native printer package and full pipeline](PRINTER-PACKAGE.md) are now
implemented. **Aurora JobServer (Test Capture)**, driver version 0.4.0.1, is
installed with the approved development signer. Native PrintCapabilities lists
every advertised laser option; its default PrintTicket decodes to the accepted
45-percent calibration settings. Windows reports a 30 x 18 inch printable page
and 600-DPI source resolution. A loopback-only receiver supports both local
printer queues. The new normal window controls whether fresh direct prints are
captured locally or automatically delivered. A real CorelDRAW print through
the new queue now carries its native job-attached Properties and converts to
exactly the accepted calibration artwork and commands. Its complete automatic
pipeline also passed against the loopback simulator. A changed-power capture
confirms that 46/16 selections reach both the native ticket and encoded commands,
with all other settings and artwork preserved.

The installed **Aurora Capture (Preview Only)** printer remains capture-only.
It has not been renamed, connected to automatic dispatch, or armed for engraving.
Microsoft XPS Document Writer's existing Properties do not yet supply the
Xenetech laser settings. The older manual desktop queue remains a diagnostic tool.

The `--once --require-empty` host options support an isolated physical test:
refuse existing queues/captures, receive a fresh CorelDRAW print, send once and
stop after completion. Two-capture simulator coverage verifies the second print
is retained without dispatch. Existing-root coverage verifies refusal before
starting the receiver. Normal continuous operation omits `--once`.

The [first integrated physical print](../analysis/integrated-print-live-20261018.md)
passed: CorelDRAW Print triggered the full automatic pipeline, the owner pressed
the machine Start button with Autostart off, and the finished engraving looked
right. The one-job host then stopped and capture-only mode was restored.

The normal launcher now opens a visible JobServer window, initially capture-only.
Enabling laser printing creates a fresh session for new CorelDRAW prints. Switching
to capture-only finishes the current delivery and holds later prints. Restarting
never replays earlier sessions. Status-only connection checks and optional
per-user sign-in startup are available in the window. Its event loop and settings
display have passed a native Windows smoke check. Desktop integration tests use
real LPR receives, the native artwork converter and a loopback controller; they
also cover crash recovery, no replay, cancellation and graceful shutdown.

A real CorelDRAW print has now appeared in the new window as Captured locally,
confirmed by the owner. Its restored 45/15 settings, artwork and placement match
the accepted integrated live print exactly in offline comparison. The owner then
enabled live mode and printed the same drawing once through the window. One
upload completed, and the owner confirmed both parts finished and look right.
The window is back in capture-only mode. See the
[desktop window evidence](../analysis/desktop-jobserver-20261018.md).
Broader artwork and Windows 11 installation validation remain.
Existing capture files and manual-test queues must not become an automatic
delivery backlog when that printer integration is enabled.
