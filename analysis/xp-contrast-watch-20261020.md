# XP slow contrast watch-loop check — October 20

**Passed the contrast case that previously produced an empty archive.** One
actual XP file-only print was captured completely by the repaired watcher and
independently decoded on the host. Its complete 20,819 bytes match the earlier
recovered contrast reference exactly. No second print was needed.

No physical laser connection, probe, laser send, live enabling or XP network
reconnection occurred. The host stayed Capture only. This is collector/output
evidence, not a physical engraving test or production contrast enablement.

## Actual test

Backed up XP's current C:\xfiles\etherin\Default.jbs into the fresh
collector-v2/contrast-inbox-before folder before changing settings. The file
was the original 4,802-byte inbox job, SHA-256
`bc6a3e4985fb4f7e0767197269356bb21ea1018d9fe784afc88b04739103deb1`.
The stopped baseline collector log and previous case were preserved. The new
raw request label was `contrast-levels4-watch`, with no newline.

Opened the same owned bitmap reference in XP CorelDRAW 11. Used Raster Only,
167 DPI, raster 30 ips/45%, Manual Contrast enabled, low 0/high 255/# Colors 4,
dithering off, normal orientation, mirror/invert/bottom-up off, 0.100 ips
travel, No Focus, Autostart Off, Beam Constantly On, 30 × 18 inches, zero
offsets, As in document/100%. The original output mode was Both, Manual
Contrast off, inactive # Colors 255; these were recorded for restoration.

Preparation was interrupted and later resumed before printing. Rechecked VM
cable off/NIC2–8 absent and the empty fresh case. The owner clicked the new
Open File warning. The collector's live WMI guards passed and it reported
ARMED contrast-levels4-watch. The host arm helper confirmed that handshake.

Submitted **exactly one** CorelDRAW Print To File. During XP's BuildHistogram
progress display, the collector remained ARMED and no candidate existed.
After completion it saved candidate.jbs (20,819 bytes) and reported CANDIDATE.
The spool.prn is empty, as expected for this driver's separate JBS output.

Host full decoding then published Default.jbs and verified.json. The verified
job matches every byte of
runtime/xp-mcp-tests-20261020/contrast-levels4-complete/Default.jbs, SHA-256
`bd05ad1f75db96acf8e9c7a5155d982ecd5d284fb6aa399b27eafcd766a5af5d`.
It contains one 145 × 140 raster at (1068,1332), 167 DPI, Autostart Off, with
exactly four signals: 0, 84, 170, 255. The original failed zero-byte archive
remains untouched in contrast-levels4/Default.jbs.

The event log records one ARMED, one CANDIDATE and STOPPED for this case.
The zero-byte XP inbox intermediate itself was **not directly observed** in
this run. The evidence is successful collection of the same previously failing
contrast job, deferral during histogram processing, complete structural
validation and byte identity. Do not claim this run measured the intermediate's
duration or exercised every possible file-writing race.

## Restoration and evidence

Stopped the collector and confirmed STOPPED before inbox restoration.
Restored Both output, Manual Contrast off and inactive # Colors 255, without
printing again. Closed the owned bitmap without saving; the original
color-raster document is active. Owned CDR SHA-256 is unchanged:
`fa17a1f6b46d4543154e261671100e35aa2bbfaa27806a39969faeb30e3f90aa`.

Restored the original inbox, then copied it back independently into
collector-v2/contrast-inbox-restored-readback. All 4,802 bytes match the backup.
The stop marker remains, XP cable is off/NIC2–8 absent, and the host is idle
Capture only with null session/current print and no error.

Immutable reports and read-only verification script are in
runtime/xp-contrast-watch-20261020: contrast-verification.json, restoration.json,
final-vm-state.json and verify-contrast.py. Raw candidates, the verified job,
spool, event log and backup/readback files are under
runtime/xp-mcp-tests-20261020/collector-v2. No production code changed and no
unchanged broad regression was rerun for this reference-only check.

The collector now has actual XP evidence for both the normal baseline and
the previously failing contrast case. Next useful work is richer grayscale
and alternate-origin artwork to distinguish contrast and dithering algorithms.
Those effects and nonbaseline travel speeds remain held for laser delivery.
