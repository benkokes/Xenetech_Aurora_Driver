# Complete original Preferences controls — r8

Update: the owner confirmed the three full pages, but OK reported a null-reference
error. R9 (0.5.1.0) replaces that save path and is now installed; see the
[save repair report](properties-ok-save-repair-20261018.md). The owner confirmed
that the corrected OK returns to CorelDRAW Print without an error. A real 46/16
Corel print now preserves all 42 snapshot fields/16 color rows and matches the
reference pixels and vector paths during offline encoding. The remainder describes the r8 controls and
transport work retained by r9.

The owner correctly reported that r7's first three tabs were incomplete. R7
supplied tab names, basic controls and material presets, with explanatory text
where many original controls belonged. It did not provide full UI parity.

R8 is installed as **0.5.0.3**, package `build/printer/AuroraV4-0.5.0-r8e`.
Installed file hashes match the signed package. Native default and user tickets
still select **167 DPI, raster 45% / 30 ips, vector 15% / 1 ips / 1000 PPI,
Autostart off**. Paper remains 30 × 18 inches; application rendering is 600 DPI.
JobServer was reloaded with the full-settings reader and remains **Capture only**.
No physical laser connection or engraving was performed during this update.

## Controls and persistence

All three pages now contain the visible groups from the owner's screenshots:

- Output modes; color use/sort/pause; raster inversion and bottom-up; raster
  and vector sliders/numeric controls; all focus choices and thickness;
  Autostart and Beam Constantly On; plate dimensions, rotary, offsets/centering;
  in/mm conversion; material Save/Load/Delete.
- Nine original resolution values; travel speed; Clip Art/Photo/Custom;
  dither choices and manual contrast; plate rotations and engraving mirror;
  stamp enable/profile; JBS location/filename preferences; fixed Aurora model.
- Sixteen enabled/disabled color rows with swatches, exact RGB values,
  editable power/speed/PPI, and separate color-profile Save/Load/Delete.

The stamp profile's *subdialog* was not included in the owner's screenshots.
The Factory Default 1 button explains this missing reference; it does not invent
profile parameters. The selected stamp enable/profile is preserved and held.

The 16-color initial table reproduces the owner's **screenshot profile**, not
claimed factory defaults. Color processing starts disabled. The reference table
is read-only as a named built-in; edits can be saved under a new profile name.

Material presets snapshot every field. Color presets load only their color
table and profile name. Both use bounded XML, hash-based filenames, file locks
and atomic replacement in `%LOCALAPPDATA%\AuroraJobServer\classic-presets`.
No prior r7 material file existed on this account; the old format is retained
untouched. Saving/deleting a preset is an explicit persistent action; Cancel
discards changes to the current print request.

Dimensions retain canonical inches while the UI switches units. Unedited
dimensions survive roundtrips without rounding drift. Edited mm values retain
six decimal places in canonical inches. Power supports 0.01%, speed 0.001 ips.
The original global vector speed range is 0.001–15 ips; selected-color speed is
0.001–150 ips, matching the separate screenshot scales.

## Per-print transport and behavior limits

`ClassicSettings.cs` defines a complete, versioned settings snapshot, including
all 16 color rows. `ClassicTicket.cs` writes it as a private ParameterInit in the
calling request. Existing GPD features carry exact known options or an explicit
Custom sentinel. Windows validation must preserve both representations; a
conflict or missing snapshot rejects the request. No mutable current-defaults
file or named material is consulted later by a queued job.

`AuroraSettings.js` and `Aurora-devmode.xml` preserve the payload in the private
DEVMODE when CorelDRAW uses GDI. The maximum payload is 20,000 base64 characters;
the observed full DEVMODE is 41,404 bytes. The script performs no file, registry
or network access and does not use queue/user property bags for job settings.

JobServer strictly parses the full XML, validates identities/ranges/precision,
and checks the nine carrier options. Windows' own PageDevmodeSnapshot parameter
is recognized as opaque provider data; it never substitutes for laser settings.
Different settings at different ticket scopes are rejected.

**Visible and saved does not mean the new engraving behavior is implemented.**
The proven combined flatbed path remains operational, including arbitrary
numeric values within its existing encoder range. Active, unverified options
hold the job **before rendering or device upload**, identifying the feature:
output modes other than Both; color processing; inversion/bottom-up; non-default
focus or beam mode; changed plate geometry/offsets/centering/rotary; changed
travel speed; bitmap presets/dither/contrast; rotation/mirror; stamp processing;
legacy output-location/filename changes; resolutions outside 100/167; raster
speeds above the existing 31-ips encoder limit. Inactive subordinate values,
such as a stored thickness with No Focus selected, remain saved without altering
the proven output.

User priority remains **167 DPI**. The supplied 500-DPI XP reference was already
preserved and checked; no repeat capture was requested or sent.

## Verification

- 124 Python regression tests pass, including per-job independence, malformed
  XML, cross-scope conflicts, carrier/payload conflicts, and pre-render holds.
- Ten complete-window checks pass: full bindings, material/color snapshots,
  native save failure/retry, Cancel, units/boundaries, and selected-color row
  retention across tab switches. All three pages were rendered and inspected.
- Five Windows Script Host/MSXML checks pass, including namespace aliases,
  fully namespaced type attributes, legacy reset and independent snapshots.
- Four independent settings snapshots survive the actual installed provider's
  MergeAndValidate → DEVMODE → PrintTicket conversions, restored in reverse
  order. They include defaults, 46/16, fractional speed/power/PPI and a full
  unverified-options snapshot. Queue defaults remain unchanged.
- Real Corel artwork plus the Windows-restored settings passes the offline
  intake/encoder. Default and changed numeric settings retain the **exact
  accepted raster pixels, vector coordinates and transfer dialect**. The
  unverified snapshot holds before rendering and produces no transferable job.
- All 15 GPD features expand natively. Inf2Cat reports no warnings/errors.
  Catalog signing reuses the already approved identity; trust stores are unchanged.

Evidence: `runtime/printer-properties-r8-verification.json`,
`runtime/printer-properties-r8-install.json`,
`runtime/classic-native-roundtrip-20261019-022349`,
`runtime/classic-pipeline-verification/verification.json`,
`runtime/complete-preferences-regression-final.log`, and
`runtime/classic-properties-review/classic-tab-{0,1,2}.png`.

The actual CorelDRAW window/OK/Commit capture check is still awaiting the owner.
Do not equate the native provider roundtrip with a completed Corel print test.
New encoder features still require controlled offline XP comparisons.

## Native compatibility findings

Microsoft documents the [constraint entry points](https://learn.microsoft.com/en-us/windows-hardware/drivers/print/javascript-constraints)
and [private DEVMODE property bags](https://learn.microsoft.com/en-us/windows-hardware/drivers/print/v4-driver-property-bags).
The currently published property-bag example uses an **https** XML namespace.
This Windows 10 PrintConfig implementation expects the **http** identifier:
`http://schemas.microsoft.com/windows/2011/08/printing/devmodemap`.
The exact identifier was independently found in the installed Microsoft binary;
changing the schema identifier restored provider initialization. A URL's scheme
is significant in an XML namespace even when the documentation link uses HTTPS.

The provider also requires actual namespace-qualified xsi:type DOM attributes,
not an attribute whose literal name merely contains a colon. Namespace
declarations for the new ParameterInit are placed on the PrintTicket root.
These cases were corrected and included in the real native roundtrip test.
Earlier r8 staging packages remain diagnostic artifacts and must not be installed;
the current signed/verified package is **r8e**.
