# Collector completion and travel-speed units — October 20

Both fixes are implemented and tested. **Printer package r11 / 0.5.3.0 is
installed** on the existing Windows 10 host. The local JobServer was restarted
idle in Capture only with explicit support for old and new complete settings.
No laser connection, probe, live enabling, physical job, XP print or XP network
reconnection occurred in this round. Windows 11 remains untested.

## Travel units and saved settings

XP evidence shows 0.100 ips emits `100. set_xyup_feed`, while 1.000 ips emits
1000. The replacement had displayed 100 for its working command 100. New
complete preferences use Version 2 and store TravelSpeed in ips, default 0.100.
The Advanced tab displays that value with an ips label. The encoder's working
command is deliberately unchanged; no new travel speed is enabled.

The backend still parses immutable Version 1 captures exactly as stored. Their
supported travel value remains 100. For Version 2 the supported baseline is
0.1; every other travel value is held before rendering/encoding. Both versions
generate byte-identical working jobs for the baseline.

The Properties reader upgrades only the known accepted Version 1 value 100 to
Version 2 / 0.100. Other old values retain their version/value and their hold,
including an old value 0.1 which must not silently become the new supported
baseline. The form identifies the legacy value and requests explicit travel
reselection. Other control edits do not reinterpret it. An explicit change to
the travel control selects ips and writes Version 2; nonbaseline values still
remain held. Existing preset files are not rewritten by loading them. Tests
cover real preset save/load as well as immutable payloads and idempotence.

## Collector repair

New maintained sources are `tools/xp-reference-collector/collect-new-jobs.vbs`
and `tools/xp_reference_collector.py`. Old runtime scripts, empty failed files,
completed reference jobs and logs remain untouched.

The guest collector requires a changed, bounded nonempty file, correct header
and final END_PLOT line, unchanged size/timestamp around the read, and identical
binary snapshots one second apart. It checks XP JobServer is closed and no
network adapter is connected while watching and before copying. It refuses
existing destinations and stops after 30 minutes or a stop marker.

Crucially, it writes **candidate.jbs / CANDIDATE**, never CAPTURED. Framing and
stability alone do not prove a valid binary job. The host independently decodes
the complete candidate, including picture sizes, row trailers, payload and end
commands, and rejects draft, Autostart and empty-artwork references. Only a
successful full decode publishes Default.jbs and verified.json. Exclusive file
creation preserves prior evidence; interrupted publication requires a new case.

The new script is staged at
`runtime/xp-mcp-tests-20261020/collector-v2/` with a stop marker. **It has not
been started in XP.** Real Windows Script Host fixture tests ran on this host,
including a zero-byte intermediate followed by a complete file, partial files,
bad header, identical binary copies, same-length changing binary content and
refusal to overwrite. Host decoding additionally rejects corrupt row trailers
even when the file has a complete-looking footer. Raw and compressed valid
fixtures pass. No private capture files are needed for these regressions.

The first host run was blocked by sandbox access to existing WSH settings.
The tests then ran outside the sandbox, without policy changes. They exposed
VBScript's byte-array indexing behavior and runtime-error exit-code ambiguity;
binary reads/comparison and explicit copy-failure exit handling were corrected.
Initial failed logs are retained alongside passing results.

## Verification and deployment evidence

Evidence root: `runtime/collector-travel-fix-20261020/`.

- Full Python suite: **209 tests, OK**, 68.886 seconds (`full-python.log`).
- After the status-capability marker and package version change: desktop
  lifecycle **14 tests pass**, package/settings **9 tests pass**.
- Complete C# controls: **15 checks pass**, including saved legacy presets,
  explicit travel reselection, unrelated edits and unchanged other controls.
  Final logs/screenshots are in `ui-final-passed/` and `ui-final-passed.log`.
  A prior deeply nested test report path hit .NET Framework's path limit; the
  test scratch stores now use a checked temporary directory. Its failed report
  remains in `ui-final/`; this did not change the user's preset store.
- Native provider: **130 independent snapshots / 260 stages** survive native
  validation and DEVMODE conversion with machine/user defaults unchanged.
  Python independently verifies all fields and feature holds (`native-matrix`,
  `native-backend-check`). No print is submitted by this matrix.
- **One actual CorelDRAW X7 capture** carries exact Version 2 / 0.100 ips
  preferences. It retains every original bitmap pixel as PNG. Raster pixels,
  raster/vector commands and vector paths match the prior working baseline
  exactly. Original machine and per-user defaults are restored byte-for-byte.
  This was run on r10's unchanged GPD/transport with the updated host reader
  before the r11 UI installation. See `x7-verification.json` and
  `x7-version2-confirmed-reference/`.
- One earlier X7 attempt stopped **before PrintOut** because the XP bitmap-only
  source did not match the helper's bitmap-and-square geometry check. Defaults
  were restored exactly; no duplicate print was submitted. Evidence is in
  `x7-version2-baseline/`.
- r11 package GPD hash exactly matches r10's previously validated GPD; its
  native-validation report is reused for that identical input, not a new GPD
  test claim. New Inf2Cat passes without errors/warnings. The package reuses
  the approved development identity, with no certificate-store change.
- The owner accepted Windows elevation. The first elevated launch omitted the
  existing .cmd launcher's process-only execution option and Windows blocked
  it before installation. Corrected launch succeeded. No system execution
  policy was changed.
- Installation: `runtime/printer-properties-r11-install.json` reports installed.
  Every installed package file matches its signed build hash
  (`installed-integrity.json`). Eight post-install native snapshots pass and
  are independently checked by Python (`installed-backend-check`). Seven
  output-quality roundtrips still pass with High as the only/default quality;
  PNG policy and 167 laser DPI are retained.
- Final receiver supports complete settings versions 1 and 2 and remains
  idle Capture only, null session/current print, no error. No device sender
  was started by installation.

Next: exercise the new collector's full watch loop during the next authorized
XP bitmap comparison. That requires the owner to accept its new Open File
warning if XP displays one. Then use a richer grayscale ramp/alternate origins
to resolve dither and contrast details; the eight-level sample alone does not
prove those algorithms. Neither these bitmap effects nor other travel speeds
have been enabled by this update.

## Later XP watch-loop follow-up

The owner subsequently authorized and completed the new collector's Open File
steps. One actual XP file-only baseline print now passes the complete watch
loop and independent host verification, byte-identical to the existing XP
reference. The collector is stopped, original settings/drawing/inbox restored,
and inbox restoration independently read back. This supersedes the earlier
"not started in XP" status for the normal watch loop. The slow contrast failure
has not yet been rerun in XP. See [watch-loop evidence](xp-watch-loop-20261020.md).

The subsequent [actual XP contrast check](xp-contrast-watch-20261020.md) also
passed: one complete capture matches the old recovered reference byte-for-byte.
No empty archive or duplicate print occurred. Restoration and disconnected /
Capture-only final state were verified. Contrast processing is still held in
the production encoder; this validates collection of its XP reference.
