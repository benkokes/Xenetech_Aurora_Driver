# VirtualBox offline validation — October 20

The owner's new VirtualBox MCP connection was exercised against the existing
LaserLaptop VM. **Two real XP file-only prints** were collected: the controlled
bitmap baseline and Ordered 4x4. No physical-equipment connection, probe, job
send, live enabling or XP network reconnection occurred.

## Integration results

- VM inventory/info and guest screenshots work. LaserLaptop runs XP Home SP2,
  with Guest Additions 7.0.14. NIC 1's cable is off; NICs 2–8 are absent.
- Direct guest keyboard and mouse controls work. Task Manager and a read-only
  WMI script both confirm that JobServer.exe is closed. JobMonitor.exe is a
  separate running utility at `C:\Program Files\Machine Tools\JobMonitor.exe`.
- The temporary, writable `AuroraTests` shared folder maps only
  `runtime/xp-mcp-tests-20261020`. Guest-to-host file copies work with the NIC
  disconnected. No existing share was changed.
- Guest execution with the metadata-confirmed logged-on user Tom, without a
  supplied password, fails with a restricted-account logon error. No password
  or account policy was changed. The guest file-copy API was not separately
  attempted with the same restricted credentials.
- Host Computer Use input fails with `GetCursorPos failed: Access is denied.
  (0x80070005)`. The owner-requested VirtualBox guest control APIs provide the
  working path, without host input injection or network connectivity.
- The owner clicked Open for `preflight.vbs`. WMI and shared report output work,
  but its `GetObject(,"CorelDRAW.Application.11")` lookup fails. This does not
  establish that every Corel COM attachment method is unavailable; the earlier
  collector also tried CreateObject, which this preflight did not try.

## Actual XP prints and independent decoding

An owned byte-identical copy of `bitmapTest1.cdr` was opened in CorelDRAW 11.
The original drawing was kept open. Layout was As in document / 100%, 30 x 18
inches. Printer: Xenetech Laser Engraver, FILE:. Both captures used Raster Only,
167 DPI, raster 30 ips / 45%, No Focus, Autostart Off, normal orientations,
Use Colors/Invert/Bottom-Up/Manual Contrast off. Output stayed at the original
`C:\xfiles\etherin\Default.jbs`; an attempted edit of the output-location field
did not change its read-only text. Empty spool PRNs and copied JBS files are
retained in separate case folders.

| Case | Actual XP job | Result |
|---|---|---|
| Baseline | bitmap-reference/Default.jbs | 20,819 bytes; byte-identical to the existing independent XP baseline, SHA-256 f2407eb8860a8af234a19af28a2d27a03f2f900aaf2ebe115c415a37c6714eea |
| Ordered 4x4 | dither-ordered4/Default.jbs | 20,819 bytes; same 145 x 140 raster, origin (1068,1332), process/header commands; only 0/255 samples, with 3,792 black samples |

The baseline repeat was intentional to establish that autonomous guest control
and file copying reproduce the earlier route. Ordered 4x4 changes 3,477 samples
from that grayscale baseline. Its decoded pixel SHA-256 is
`f2039725941bfde1387192c0df9feb84a8fc0f9f72cab4d590969bd74e2ae266`.

For this bitmap, nearest-neighbor resizing from 167 x 167 to 168 x 168 followed
by nonwhite cropping exactly reproduces every XP baseline sample. One Bayer4
orientation/phase also predicts every Ordered4 sample. These are **sample fits**,
not a general algorithm proof: eight input gray levels do not uniquely identify
thresholds and phase. Dithering remains held in the production encoder.

Evidence: `runtime/xp-mcp-tests-20261020/sample-analysis.json`, the two
`Default.decoded.json` files and untouched original jobs/PRNs. No Ordered8,
error-diffusion, contrast, orientation or focus capture is claimed by this run.

## Source-only publication preflight

Separately staged 165 source/fixture files under
`runtime/publication-preflight-20261020/source-only`, excluding existing runtime,
captures, build products, signing keys and vendor binaries. This is a source-only
staging check on this host, **not a Git clone, secret/history audit, new OS test
or independent Windows installation**.

- Native renderer built from staged sources; all **36 native tests pass**.
- Printer Properties builds from staged sources and Windows' type library.
- Unsigned full-preferences r10 printer package assembles successfully.
- Python unittest reports **197 tests, OK (skipped=45)**. One skip is class-level,
  so subtracting skip entries from the run count is not a reliable flat passed
  count. Earlier commentary's 152 figure was that subtraction; use the verbatim
  runner result. The log identifies the missing private captures/native fixtures.
- No driver update or signing/trust change was performed in this run. This is
  not a rerun of the complete private 201-test regression.

Logs and source hashes are in `runtime/publication-preflight-20261020/`.
Shareable fixtures and clean-Windows installation still need work for release.

## Restoration and pending step

Restored Both Raster and Vector, Floyd selected but Dither off, Manual Contrast
off, 167 DPI, 45/15 powers, 30/1 ips, 1000 PPI, No Focus, Autostart off and the
unchanged `C:\xfiles\etherin\` output directory. Closed the owned drawing without
saving; the original color-raster reference is active again. Original and owned
bitmap CDR hashes still match. The old 4,802-byte inbox job was restored and
copied back independently: **byte-for-byte restoration passes**. See
`inbox-restoration.json`; all new jobs remain archived separately.

XP Explorer's address toolbar was unlocked/moved to make navigation possible.
This is a window-layout change; no security setting was changed.

`collect-new-jobs.vbs` is prepared as a read/copy-only 30-minute collector. It
accepts only whitelisted case labels, waits for a stable changed inbox file,
refuses existing destinations, and stops if XP JobServer starts. It does not
print, change settings, launch programs or use guest networking. **It has not
run**: XP's Open File security warning is waiting for the owner. The existing
Computer Use rule forbids accepting security permission prompts automatically.
The temporary share remains available for that pending Open step. Its request
label is `await-next-test`; there is no pending print command.

Observed follow-up: XP Advanced displays travel speed **0.100 ips**, while the
replacement's working field is 100 and the emitted command is
`100. set_xyup_feed`. A changed-value XP comparison is needed to settle UI/native
units before claiming travel-speed parity. No change was made from this clue.

Final checks confirm NIC 1 off, other NICs absent, and host JobServer idle in
Capture only with null session/current job and no error. Original XP JobServer
was never started. Further XP tests await the collector's Open permission.

## Follow-up after owner opened the collector — completed October 20

This section supersedes the pending-collector and two-print status above.
The collector actually ran from XP guest time 13:01:54 to 13:26:22 and was
explicitly stopped before restoring the inbox. **Nine additional actual XP
file-only prints completed, making eleven total in this test directory.**
No equipment was contacted, XP networking stayed disconnected, and host
JobServer stayed Capture only. The collector checked that XP JobServer was
closed throughout its loop. No additional security prompt was accepted by
automation.

All captures use the owned bitmap, 167 DPI, 30 ips / 45%, Raster Only,
Autostart Off, As in document / 100%. Each test changes only the stated
baseline option; settings are restored between different option groups.

| New case | Confirmed result |
|---|---|
| Ordered 8x8 | Binary raster; 3,792 black samples |
| Floyd–Steinberg | Binary raster; 3,784 black samples |
| Jarvis | Binary raster; 3,775 black samples |
| Stucki | Binary raster; 3,823 black samples |
| Manual contrast, low 0 / high 255 / 4 colors | Four output signals: 0, 84, 170, 255 |
| Manual contrast, low 64 / high 192 / 128 colors | Eight observed output signals: 62, 80, 99, 117, 136, 154, 173, 191; even baseline zero signal maps to 62 |
| Reverse/Mirror | Every pixel is the exact horizontal flip; origin becomes (28068,1332), matching reflection across the 30-inch plate at 6-mil sample pitch |
| Travel Speed 1.000 ips | Only command change is `100. set_xyup_feed` → `1000. set_xyup_feed`; identical raster pixels |
| Beam Constantly On unchecked | Only command change is `40 PWF` → `1 PWF`; identical raster pixels |

Every completed job decodes as one 145 × 140 raster. Apart from Mirror, the
origin stays (1068,1332). Five dither modes now have actual XP evidence,
including Ordered4 from the earlier part of this run. The eight-level bitmap
does not prove complete dither threshold/phase, diffusion rounding or contrast
algorithms. Those features remain held in the production encoder. Travel speed
has a concrete UI/native units discrepancy: XP's original 0.100 ips emits 100,
whereas the replacement currently displays 100 for its existing command 100.
Resolve UI units and stored-setting compatibility before enabling that feature.

The collector had a real failure: both contrast jobs left a stable zero-byte
intermediate long enough to be copied and marked CAPTURED. The independent
decoder rejected these. Both empty attempts remain untouched; the completed XP
inbox files were recovered to `contrast-levels4-complete` and
`contrast-range64-192-complete` **without another print**. Repair the collector
to reject empty/incomplete files before reuse; its status alone is insufficient
evidence of a valid capture. No repaired collector has been run or claimed.

Immutable evidence: `runtime/xp-mcp-tests-20261020/bitmap-controls-analysis.json`,
its read-only `analyze-bitmap-controls.py`, per-case `verified.json` or
`Default.decoded.json`, original JBS/PRN files, and `collector-events.txt`.
The analysis checks exact mirror pixels/origin, isolated travel/PWF command
changes, all job dimensions/Autostart, preserved empty attempts and restoration.
It passed. No unchanged broad production regression was rerun for these
reference-only additions.

Restored Both output, Beam Constantly On, travel 0.100 ips, normal orientation,
Mirror off, Custom / Dither off (Floyd selected), Manual Contrast off with
0/255/255 inactive values; 167 DPI, 45/15, 30/1 ips, 1000 PPI, No Focus and
Autostart Off. Closed the owned bitmap without saving; the original
color-raster drawing is active. The original 4,802-byte inbox was restored
again and independently copied back to
`inbox-restored-readback-after-bitmap-controls/Default.jbs`; its SHA-256 matches
the backup exactly (`bc6a3e4985fb4f7e0767197269356bb21ea1018d9fe784afc88b04739103deb1`).
Collector status is STOPPED; the temporary share remains for future authorized
offline work. Final VM info confirms cableconnected1=off, NICs 2–8 absent.
Host JobServer remains idle Capture only with no session/current print/error.

Not run in this batch: plate rotations, other focus modes, Clip Art/Photo,
broader gray ramps and alternate bitmap origins/DPI, or any physical tests.
