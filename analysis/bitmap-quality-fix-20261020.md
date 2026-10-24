# Lossless bitmap capture repair — October 20

Driver **0.5.2.0 (r10)** is installed on the Windows 10 host. Two completed real
CorelDRAW X7 prints now embed PNG with **zero changed pixels out of 27,889**.
Both retain the original bitmap's eight gray levels. The prior r9 capture
embedded JPEG, changing 3,996 pixels and introducing 153 gray levels.

## Cause and change

The manifest already mapped `PageOutputQuality.High` and `.Normal` to PNG, but
the installed provider exposed no public output-quality feature. A native High
request was discarded before printing. Added a hidden GPD feature explicitly
mapped to public `PageOutputQuality`, with High as its only/default option.
The [v4 manifest documentation](https://learn.microsoft.com/en-us/windows-hardware/drivers/print/v4-driver-manifest)
describes the image-format policy; the [GPD mapping documentation](https://learn.microsoft.com/en-us/windows-hardware/drivers/print/gpd-ppd-based-feature-description-changes)
describes the public feature/option mapping used here.

The r10 UI binaries, full-preferences JavaScript and DEVMODE map match r9
exactly. No new certificate trust was added; the package reused the previously
approved identity. The default laser resolution remains 167 DPI.

## Verification

- Native GPD expansion: all 16 declared features observed. Inf2Cat: no errors or
  warnings. Signed catalog accepted by Windows; installation and package
  hashes recorded in `runtime/printer-properties-r10-install.json` and the r10
  package's build, native-validation and test-signing reports.
- Native provider: High is the sole/default quality for machine and user.
  All seven named quality requests normalize to High and survive DEVMODE
  conversion. Six complete native laser-preference snapshots also round-trip.
- Actual X7 PrintOut, normal defaults: capture
  `cdd7acaa-069d-49ac-9fb9-91f48bf250d0`, raster/vector powers 45/15.
- Actual X7 PrintOut after receiver fix: capture
  `10de26b4-b52d-4a55-bfb5-3f85a509cee0`, powers 46/16.
- Both published sources contain a 167 × 167 PNG identical to the original BMP.
  Complete per-job preferences match the selected XML. Both locally convert and
  encode with the correct independent powers, 30/1 ips, 1000 PPI, Autostart Off,
  unchanged vector geometry, and a 145 × 140 raster.
- User DEVMODE snapshots restore byte-for-byte after each test; laser options
  and optional full-preferences payload match the pre-update defaults.
- Final full regression: **201 tests passed**, 64.093 seconds.

Immutable reports are under `runtime/bitmap-quality-fix-20261020/`, including
`verification.json`, `fidelity-before.json`, `fidelity-after.json`, the native
quality audit, capture helpers' reports and `python-regression-final.log`.
Published receipts and sources are archived in
`captures/host-x7-bitmap-quality-20261020/`. `tools/verify_bitmap_capture.py`
independently fails the old JPEG source and passes the new PNG source.

## Receiver race found during verification

There were **three** actual X7 print calls, including one that did not publish.
During the second print, the desktop history glob descended into `.receiving-*`
while the receiver published its receipt. On Windows this can block the final
directory rename. That attempt saved `failed.json` with WinError 5 and left an
unpublished receipt; the test helper incorrectly accepted its temporary name.
The first full regression also exposed a receive-close failure in a desktop test.

The desktop catalog now excludes temporary directories before descending into
them. A new regression checks that an unpublished, partially written receipt is
never opened or admitted to history. The Corel test helper likewise waits for a
published UUID directory. Fourteen desktop tests pass, followed by the complete
201-test run and the successful final 46/16 X7 capture.

The failed capture was preserved unchanged at `unpublished-46-16`; it was never
published, replayed or sent. JobServer was restarted idle in Capture only.
Computer Use twice refused to bind its listed window with the error
`window id 1444554 no longer belongs to ...; current owner is ...` despite
identical owner strings. The verified project-owned process was therefore
restarted through process management, with its idle status and empty spool
queue checked first. No replacement Windows UI automation was used.

## Remaining scope

This fixes bitmap corruption during capture. It does not establish pixel-for-
pixel parity of the final raster with XP: ordinary X7 rendering still resamples
the bitmap, and the resulting origin is (1068,1326) versus the previously saved
XP origin (1068,1332), a one-row difference on the fitted raster grid. Width and
height now match XP's 145 × 140; vector geometry is unchanged. Keep this separate
from the resolved JPEG artifacts when comparing future bitmap features.

No new XP capture, physical connection, laser probe, live enabling or laser job
occurred. JobServer ends idle in Capture only with no error. The installed host
is Windows 10 build 19045; Windows 11 deployment remains untested.
