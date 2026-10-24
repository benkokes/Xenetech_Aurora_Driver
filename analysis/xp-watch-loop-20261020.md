# XP collector watch-loop validation — October 20

**Passed one actual XP file-only print through the new watch loop.** The
collector archived a complete 20,819-byte candidate, and the independent host
decoder verified every byte against the previously established XP baseline.
No laser connection, probe, laser job, live enabling or XP networking occurred.
The laser did not need to be powered on.

## Setup and result

- VirtualBox confirms NIC1 cable off and NICs2–8 absent before and after.
  Task Manager, sorted by image name with all users visible, showed JobMonitor
  between Explorer and lsass and no JobServer. The collector's WMI guards also
  passed before arming and copying. JobMonitor was left running.
- Backed up the current XP inbox into the fresh `collector-v2/inbox-before`.
  Its 4,802 bytes match the previously restored original exactly.
- Used the owned byte-identical Bitmap-Reference.cdr, preserving the original
  color-raster drawing. Selected Raster Only; 167 DPI; raster 30 ips/45%;
  No Focus; Autostart Off; Beam Constantly On; travel 0.100 ips; Custom bitmap;
  dithering/contrast/invert/bottom-up/mirror off; normal orientation; zero
  offsets; 30 × 18 inches; As in document / 100%. Other controls were unchanged.
- The first launch stopped safely at invalid-label validation. My PowerShell
  preparation had added CRLF to request.txt. Corrected it to the exact raw
  bytes `baseline-watch`, matching the maintained host helper's format. This
  was a setup error, not an accepted malformed request. No print or candidate
  occurred during that attempt. Its event remains preserved.
- The owner accepted both Open File security warnings directly. No security
  prompt was automated. The corrected script reached ARMED baseline-watch;
  the maintained host `arm` command confirmed the handshake before printing.
- Submitted **exactly one** XP Print To File job. The saved spool.prn is empty,
  as expected for this driver; the actual JBS is written to the unchanged
  C:\xfiles\etherin\Default.jbs inbox.
- The guest saved candidate.jbs and reported CANDIDATE, without claiming a
  verified capture. Before host validation, Default.jbs and verified.json
  were absent from the case folder. The host full decode then published both.
- All 20,819 bytes match the independent bitmap-reference/Default.jbs, SHA-256
  `f2407eb8860a8af234a19af28a2d27a03f2f900aaf2ebe115c415a37c6714eea`.
  Decoded raster: 145 × 140, origin (1068,1332), 167 DPI, Autostart Off.
- Requested stop and confirmed STOPPED before touching the inbox. Events show
  one ARMED, one CANDIDATE and one STOPPED after the preserved startup rejection.
  No duplicate print or capture occurred.

## Restoration

Restored Both Raster and Vector without printing again, closed the owned
bitmap without saving, and returned to the original color-raster drawing.
Other baseline settings were unchanged. The owned CDR still has SHA-256
`fa17a1f6b46d4543154e261671100e35aa2bbfaa27806a39969faeb30e3f90aa`.

Restored the original 4,802-byte inbox and copied it back from XP into the
fresh collector-v2/inbox-restored-readback folder. It matches the backup
byte-for-byte, SHA-256
`bc6a3e4985fb4f7e0767197269356bb21ea1018d9fe784afc88b04739103deb1`.
The collector remains stopped with a stop marker. The host is idle Capture
only, no session/current print/error, and XP's cable remains disconnected.

## Evidence and limits

Immutable reports and read-only verification code are in
`runtime/xp-watch-loop-20261020/`: preflight.json, startup-note.md,
baseline-verification.json, restoration.json and final-vm-state.json.
Raw candidate, verified job/report, spool, event log and backup/readback files
remain under `runtime/xp-mcp-tests-20261020/collector-v2/`.

This validates the normal XP watch loop, its guard/arm/candidate/verify/stop
flow and restoration. The actual slow contrast-rendering case has **not** been
repeated with the new watcher yet. Zero/partial/changing-file rejection is
covered by the earlier host WSH and decoder regressions; do not describe this
single baseline capture as a new XP reproduction of every failure path.
No production code changed and no broad test suite was needlessly rerun.

The next useful bitmap work is a richer grayscale ramp and alternate origins
to distinguish dither phase/threshold and contrast algorithms. The existing
eight-level sample does not prove them generally. Nonbaseline travel and new
bitmap effects remain held for laser delivery.

## Later contrast follow-up

The owner subsequently authorized the slow contrast case. One actual XP
Manual Contrast / four-color print now passes the repaired watch loop and
full host decoding, byte-identical to the earlier completed contrast job.
Original settings/drawing/inbox are restored and independently read back;
collector stopped, XP disconnected, host Capture only. This supersedes the
earlier unrun-contrast status. The transient zero-byte inbox was not directly
observed in that follow-up. See [contrast watch evidence](xp-contrast-watch-20261020.md).
