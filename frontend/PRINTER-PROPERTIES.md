# Direct laser controls in printer Properties

## Current installed package: r10, 0.5.2.0 (October 20)

Bitmap captures now use lossless PNG. The hidden public High output-quality
option activates the manifest's existing PNG policy; the r9 Properties UI and
laser preferences transport are unchanged. Two real X7 captures retain every
source bitmap pixel and selected 45/15 or 46/16 powers. All 201 regression tests
pass. See [repair evidence](../analysis/bitmap-quality-fix-20261020.md).
The historical package descriptions below describe earlier changes.

## Raster controls verified against XP (October 19)

Invert Raster Output and Bottom-Up Engraving now work in the backend at 167 DPI.
All three independent XP bitmap jobs match the raw encoder byte for byte.
Bottom-Up reverses rows, uses PICT-LL and starts at the original last row;
Invert complements the stored raster samples within the same bounds. Vector
settings and paths are preserved. Other resolutions retain a hold for these
controls. The existing r9 window/snapshot already carries both options, so no
driver installation or default change was required. Native conversion,
loopback transfer and all 169 Python tests pass. JobServer remains Capture only;
the new controls have not been physically engraved. See
[reference results](../analysis/raster-preferences-results-20261019.md).

## Output-mode backend update

The original XP Both/Raster Only/Vector Only captures are now compared. Raster
Only is enabled in the backend and keeps the raster unchanged while omitting
cutting commands. Its native conversion and exactly-once loopback transfer pass.
Vector Only matches the original job bytes offline, but remains held until its
legacy network-transfer profile is verified. All 132 Python tests and six native
Windows snapshot roundtrips pass. The existing r9 Properties package already
carries these choices, so no new driver installation was required. The host is
Capture only. The actual Corel Raster Only capture passed: TEST's pixels,
placement and raster settings match the accepted X7 reference, with no square
cutting commands. The owner restored Both afterward. See the
[output-mode results](../analysis/output-mode-results-20261018.md).

The optional `ClassicNativeRoundtrip --matrix` diagnostic now verifies 128
separate snapshots across enums, numeric limits/precision, all sixteen colors,
long strings and Unicode. Independent Python verification reads all 256 native
validated/restored tickets and their full XPS job scopes, preserving feature
holds. Thirteen component checks cover every palette row, unit conversions,
dependencies and save failures. These are read-only provider/component tests;
the installed r9 driver and its defaults were not changed.

## Current save repair (r9)

Version **0.5.1.0**, `build/printer/AuroraV4-0.5.1-r9`, repairs the expanded
window's OK path after the owner reported a null-reference error. It updates
the complete settings XML before notifying Windows and validates the XML without
depending on feature-wrapper objects after mutation. Missing native responses
produce clear messages and a full diagnostic log. Save/failure/cancellation
regressions and four real Windows roundtrips pass. The owner confirmed the
three full pages and that OK returns to CorelDRAW Print without error. A real
46/16 Corel print now preserves all 42 snapshot fields and 16 color rows; its
offline encoded pixels, placement and vectors match the reference exactly. JobServer remains
Capture only, with the 167-DPI defaults preserved. See the
[save repair report](../analysis/properties-ok-save-repair-20261018.md).

## Complete original controls and per-job snapshots (r8)

Version **0.5.0.3**, `build/printer/AuroraV4-0.5.0-r8e`, is installed and its
files match the signed package. The first three tabs now contain the visible
groups from the original XP screenshots, including focus/plate controls,
all nine resolutions, bitmap/orientation controls, and the editable 16-color
table. The original stamp-profile subdialog still needs a reference.

Settings are captured in a complete per-job snapshot and survive Windows'
private DEVMODE conversions. Material presets save the entire snapshot; color
profiles load just their palette. Cancel leaves the calling print unchanged.
The proven flatbed path remains available. New, unverified active options cause
JobServer to hold the job before rendering/upload, with a named reason.
The default remains **167 DPI**, 45/15 powers and Autostart off; JobServer is
**Capture only**. No new engraving occurred.

See the [complete implementation and verification report](../analysis/complete-preferences-20261018.md)
for behavior limits, file formats and evidence. All 124 Python tests, ten full
window checks, five MSXML checks and four independent native Windows roundtrips
pass. The real Corel artwork retains the accepted geometry/pixels in offline
encoding. The owner's CorelDRAW window and subsequent capture check remain pending.

The sections below describe earlier releases and are historical.

## Earlier tab and material update (r7)

The r7 build has the XP tab names: Laser Output Control, Advanced,
Color Settings and About. Raster/vector controls stay on the first screen;
resolution moves to Advanced. Material Setting adds per-user Save/Load/Delete
for complete presets. Loading edits this dialog only; OK copies the chosen
values into the print. A preset is never read later by a queued job. Saving or
deleting a named preset persists that explicit action even if the dialog is
subsequently canceled; Cancel still leaves the current print's settings alone.

Materials live at `%LOCALAPPDATA%\AuroraJobServer\material-profiles.xml`.
Atomic replacement and an exclusive file lock protect writes; a stale second
Properties window cannot overwrite newer presets. Invalid/unsupported profile
files are retained and reported, leaving the base printer controls usable.

Native checks cover the tabs, preset snapshot/load/Cancel/reload/delete,
concurrent edits, hostile XML rejection and the existing Windows ticket merge.
Visual previews are at `runtime/printer-properties-tab-preview/tab-0.png`
through `tab-3.png`. The r6 package remains available for rollback.
The r7 update is packaged as `build/printer/AuroraV4-0.4.1-r7`, version 0.4.1.0,
and signed with the existing approved development identity. Its GPD is byte
identical to r6 and its default stays at 167 DPI. Native feature expansion,
catalog signability, signature verification and installation dry-run checks
passed. Installation uses `Install-Aurora-Properties-Update.cmd` with Windows
administrator consent; its result is recorded in
`runtime/printer-properties-r7-install.json`. The update adds no certificate trust.

Installation has completed. Native registry inspection reports version 0.4.1.0,
and the installed GPD, manifest, UI executable and COM metadata hashes match the
signed package. Default and user PrintTickets still contain all nine original
selections, including 167 DPI, 45/15 powers and Autostart off. Native inspection
still reports the 30 × 18 inch page and 600-DPI source rendering. The owner has
been asked to verify the new tabs and a save/load/cancel material roundtrip in
CorelDRAW X7. No print is required for that check.

The original driver has nine DPI choices and more controls than the current
backend. See [feature map](../analysis/xp-preferences-parity.md). New controls
are enabled only with implemented output behavior. The Color Settings tab
currently explains that per-color processing is not implemented; it does not
accept color settings which would silently be ignored. The supported native
DPI choices remain 100 and 167 pending additional XP comparisons.

## Earlier r6 UI

Version 0.4.0.0 adds a native desktop printer extension so CorelDRAW's first
Preferences/Properties window shows the laser controls. It replaces the
Paper/Quality → Advanced navigation for this printer. CorelDRAW still owns the
caption and placement of its Preferences button.

The new **Aurora Laser — Printer Properties** window has two visible sections:
raster power/speed/resolution and vector power/speed/PPI. Plate size, combined
output and Autostart are on the same screen. Power uses whole-percent numeric
controls; speed, PPI and DPI lists come from the installed driver's capabilities.
The fixed output/focus features are preserved with the job.

This changes the settings UI only. The GPD, option identifiers, PrintTicket
namespace, intake, encoder and transport are unchanged. The receiver is still
capture-only following the successful integrated physical test.

## Implementation

- `PrinterPreferences.cs`: form and option model; edits are staged until OK.
- `PrinterExtension.cs`: Windows event context, native capabilities, async
  validation/commit, UI-thread request completion and cancellation.
- `BuildPrinterInterop.cs`: imports the installed Windows printer COM type
  library as metadata, with REGKIND_NONE and no registration changes.
- `build-printer-properties.ps1`: builds using the existing Framework compiler.
- `PrinterPreferencesTests.cs`: form behavior and validation against the native
  Windows provider without changing printer defaults or submitting jobs.

Windows launches the extension for this driver's PrintPreferences event. The
extension reads the calling application's PrintTicket, rather than mutable
global defaults. OK sets its private feature options, validates asynchronously,
checks that Windows preserved every requested laser value, commits and completes
the request on the UI thread. Cancel closes the request without committing.
The application makes no controller connections and cannot submit a print.

The driver's manifest registers extension ID
`{12CE902C-DD91-41A9-AD32-F51B6DE8C15B}` with the existing Aurora PrinterDriverID.
The EXE and COM metadata DLL are covered by the signed package catalog and are
installed in its Driver Store directory. No extra runtime is downloaded.
This follows Microsoft's [printer extension model](https://learn.microsoft.com/en-us/windows-hardware/drivers/print/printer-extensions)
and [manifest registration](https://learn.microsoft.com/en-us/windows-hardware/drivers/print/v4-driver-manifest).

## Build and checks

```powershell
./frontend/build-printer-properties.ps1
./frontend/build-printer-properties.ps1 -Test
python -m tools.build_printer_package build/printer/NEW-DIRECTORY --printer-ui build/printer-ui
```

Run native GPD validation, catalog generation and signing as described in
[package instructions](PRINTER-PACKAGE.md). The build also supports the earlier
data-only package when `--printer-ui` is omitted. Do not install that variant
when testing the new window.

The current build is `build/printer/AuroraV4-0.4.0-r6` (version 0.4.0.1), installed
successfully with the same approved development signer. The catalog SHA-256 is
`68e94654deadf5aa0606211dac3dcf17f30f3eb3c9d619c9bde7bf184506a6f9`.
The installed native registration and version are verified; all nine native
default selections, 30 × 18 inch paper and 600-DPI source resolution are
unchanged from r4. Eight Python settings tests pass. Native checks confirm
initial values, deferred editing, OK, Cancel and preservation of 46/16 power
values through Windows' in-memory MergeAndValidatePrintTicket operation.

The owner confirmed that r5 opens the custom first-screen raster/vector window
from CorelDRAW. The owner also reported that Cancel showed the fallback Document
Properties window. R5 incorrectly passed E_ABORT to the extension request. R6
passes S_FALSE (1), matching Microsoft's
[operator-cancellation sample](https://github.com/microsoft/Windows-driver-samples/blob/2e237713e298495b141560a5e7c76d6b1efa0153/print/v4PrintDriverSamples/PrinterExtensionSample/ExtensionSample/PrintPreferenceWindow.xaml.cs#L80).
Failure HRESULTs are reserved for an extension failure where fallback is wanted.

The owner confirmed that r6 Cancel returns directly to CorelDRAW's Print dialog.
The actual extension Save/Commit path is now also verified: CorelDRAW's print
was received as `ca3feb35-4be8-4cdf-b4f4-efb872178d83` on October 18, 2026 at
21:29:35 UTC. Its native job-attached ticket contains the changed 46-percent
raster and 16-percent vector powers, with every other selection unchanged.
Offline conversion confirms both powers in the laser commands, exact raster
samples/vector geometry/placement, and Autostart off. No physical delivery was
performed. The print completed silently because this receiver saves captures.

Evidence: `runtime/printer-properties-r6-verification.json`,
`runtime/printer-properties-r6-commit-review`, and
`runtime/native-printer-inspection-r5`. The owner confirmed restoring
45/15 in the new window after the capture test. No new physical test is needed
to establish this UI's settings transport; the underlying encoder/transport
and GPD are unchanged from the earlier accepted integration test.

The owner should close any previously open Properties and Print dialogs before
opening Preferences again. Native launch errors are written to
`%TEMP%\AuroraPrinterProperties.log`. The prior r4 package remains available for
diagnosis/rollback; its native Advanced controls are the earlier fallback UI.
