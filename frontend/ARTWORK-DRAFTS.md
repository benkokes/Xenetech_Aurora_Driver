# Artwork-to-Aurora draft encoder

The captured CorelDRAW `test.cdr` document now has independently generated raw
and compressed Aurora draft jobs. This stage performs no device I/O. Drafts are
marked uncalibrated and are rejected by normal queue preparation and wire-plan
construction. There is no release/send switch in this tool.

The owner has accepted the X7 lettering. A separate constrained tool now stages
only that exact reviewed square-and-TEST reference for a physical measurement;
see [CALIBRATION-TEST.md](CALIBRATION-TEST.md). This does not release arbitrary
drafts or mark the renderer calibrated. The owner has accepted the completed
[45% raster-power physical test](../analysis/power45-calibration-live-20261018.md).
Broader artwork and placement validation remain.

A separate [printer pipeline](PRINTER-PACKAGE.md) now encodes validated scenes
under the explicit experimental Corel flatbed profile, using the options attached
to each print. This does not remove markers from existing draft files or change
the ordinary offline draft encoder. Its full path is tested only against a local
controller simulator while native driver installation is pending.

## CorelDRAW placement compatibility

The 100-DPI comparison confirmed a 1000 x 1000 square at (900,1220), while the
167-DPI reference has a 1002 x 1002 square at (876,1212). The explicit
`coreldraw-xp-draft` profile reproduces the **entire vector command section byte
for byte at both resolutions**, including position, closure, speed, power, PPI
and final pen-up/origin commands. This is an offline reference fit, not physical
calibration or validation for arbitrary artwork/applications.

The model is limited to the current CorelDRAW X7 capture, a 600-DPI source
printer ticket, the 30 x 18 inch flatbed and target 100 or 167 DPI. Intake reads
the source resolution from the XPS package PrintTicket and rejects a missing,
mixed or different resolution. Selection is explicit. A page-size mismatch is
rejected. Paths that map out of bounds fail; engraving crossing the old surface
boundary gets a review reason and cannot be encoded. The source page geometry
stays in the manifest/SVG; the profile records how controller coordinates and
the exposure plane are derived.

For a source cutting coordinate c in inches, the observed model is:

```text
target_pixel = round((c + 1/600) * target_dpi) - 1 - center_adjustment
job_coordinate = target_pixel * pixel_pitch
```

At 100 DPI, adjustment is (0,0), pitch is 10, surface is 3000 x 1800 pixels.
At 167 DPI, adjustment is (5,3), pitch is 6, surface is 5000 x 3000 pixels.
The source XPS ticket confirms 600 DPI. The +1/source-DPI and -1/target-DPI
terms describe the observed Corel print-coordinate mapping, not a guarantee
about every CorelDRAW version or a machine-origin correction. Source coordinate
quantization is irreversible and may affect other points near a rounding
boundary. More artwork and physical measurements remain necessary.

Raster rendering applies the corresponding continuous translation before
sampling and cropping on the target surface. Font metrics, hinting and glyph
edges still differ: at 167 DPI XP is 140 x 42 at (978,720), versus the new
draft's 140 x 41 at (972,720). At 100 DPI XP is 84 x 24 at (1000,740), versus
83 x 24 at (1000,730). Both use only 0/255 for this black text. No raster padding
or extra shift is introduced to hide these differences.

Current artifacts:

- `runtime/coreldraw-compat-jbs-100` and `runtime/coreldraw-compat-jbs-167`: drafts.
- `runtime/coreldraw-compat-100-checked` and `runtime/coreldraw-compat-167-checked`:
  source snapshots, measured source DPI, geometry, exposure and clipping checks.
- `runtime/coreldraw-compat-comparison-100/comparison.json` and the 167 counterpart:
  independent native-command and signal comparisons.
- `runtime/coreldraw-compat-review/raster-comparison.png`: magnified decoded
  samples, retaining the placement differences for review.

All drafts remain blocked from normal queue/wire handling. **75 Python tests
and 24 frontend checks pass.** No new laser job was sent.

## XP comparison received

The same drawing was captured through CorelDRAW 11 and the XP driver, without
running the laser. The raw job is 6,341 bytes, SHA-256
`4eea537809c0a3248d32bde7bd30df2060d60fec572049308fadc44f3fe7e2e7`.
It confirms all requested process settings and a 1002-by-1002-unit square for
one nominal inch. The original 1000-unit draft is retained as an earlier model.

The explicit `xp-167-6mil-draft` profile now renders at exactly 167 samples per
inch, then emits six job units per sample. Vector coordinates use 28.4 device
coordinates and the integer rounding observed in the XP driver, giving 1002
units per inch. This matches the captured square's size; it is not a physical
calibration result. The old `aurora-167-6mil-draft` profile retains its original
1000/6 sampling rate for comparison and does not silently change meaning.

An optional `--text-rendering outline-aliased` mode builds glyph outlines from
the captured font and rasterizes those edges without gray coverage samples.
Gray fills and images retain their values. This reproduces the captured black
text's two signal levels, but is not an exact match for XP's hinted glyphs.
Default `auto` rendering is unchanged. Direct WPF text-rendering options did
not enforce bilevel text in the bitmap renderer; explicit outline rendering
is tested against actual pixels instead of trusting a requested mode.

Earlier scale-only draft: `runtime/coreldraw-xp-jbs-draft`; intake:
`runtime/coreldraw-xp-grid-outlined`; comparison:
`runtime/xp-comparison-corrected/comparison.json`.

| Property | XP | Corrected draft |
| --- | --- | --- |
| Raster speed / power | 30000 / 30 | 30000 / 30 |
| Vector speed / power / PPI | 1000 / 15 / 1000 | 1000 / 15 / 1000 |
| Square size | 1002 x 1002 | 1002 x 1002 |
| Square top-left | 876, 1212 | 910, 1233 |
| Raster size | 140 x 42 | 140 x 41 |
| Raster top-left | 978, 720 | 1008, 738 |
| Raster signal levels | 2 | 2 |

Placement and glyph samples remain unresolved. No arbitrary offset correction
or pixel padding is applied. The owner's XP screenshot confirms As in document,
100% and centering off. `capture/xp-artwork-state.vbs` reads XP's loaded drawing
geometry to distinguish application placement from driver conversion. Both
drafts remain marked and rejected by normal queue/wire handling. No new artwork
was sent to the engraver. Full validation passes 72 Python tests and 22 frontend
checks, including profile scaling, renderer signal levels and comparison metrics.

## Build a draft

Rebuild intake on the explicit Corel compatibility grid, using a new output directory.
Ordinary preview manifests lack the explicit draft coordinate profile and are
not accepted by the encoder:

```powershell
.\frontend\build.ps1
.\build\frontend\Aurora.XpsIntake.exe SOURCE.xps runtime\native-grid --cut-color '#FF0000' --max-cut-width-mm 0.2 --raster-grid coreldraw-xp-draft --text-rendering outline-aliased --dpi 167
python -m aurora_jobserver.artwork runtime\native-grid runtime\draft --settings process-settings.json --title Test
```

The explicit cutting color/width must match the intended artwork. To inspect
geometry while settings are pending, omit `--settings`; the tool writes only
`draft.json`, with state `awaiting_process_settings`, and no JBS files.

Settings have no implicit defaults. For the owner's requested test:

```json
{
  "schema_version": 1,
  "units": "inches-per-second",
  "raster_speed_ips": 30,
  "raster_power_percent": 30,
  "vector_speed_ips": 1,
  "vector_power_percent": 15,
  "vector_ppi": 1000
}
```

These map to `30000. speed / 30.00 power` for raster and
`1000. speed / 15.00 power / 1000. set_vppi` for vectors. The supplied XP
properties screenshot labels speeds in ips, power in percent, and shows a
30-by-18-inch plate with zero offsets and no focus adjustment. Its older raster
31/100 values match the original captured job; the new draft uses the owner's
explicitly requested 30/30 values instead.

The XP UI's inch display path multiplies its stored raster/vector speeds by
0.001 (`xtlaserui.dll`, around VA `0x00405ddc` through `0x00405e50`, constant at
`0x00401670`). The graphics writer emits those stored integers directly as
`speed` at `0x00407877`. This supports the factor 1000 independently of the new
encoder. The first prototype bounds speeds to 0.001..31 ips, power to 0..100%
with two decimal places, and PPI to 1..10000. These are implementation limits,
not a verified full machine capability specification. The API also accepts
explicit `driver-native` speed fields for diagnostic comparisons.

## Original 1000-unit model conversion rules

- Intake schema 2 records nominal DPI 167 and actual render DPI 1000/6. Raster
  samples lie on a six-job-unit grid under the inferred 1000-units/inch model.
- WPF renders the engraving layer with a full opaque white background. A cropped
  unsigned-byte exposure plane stores 0 for white and 255 for black, with a
  source hash, dimensions and page-pixel offset. Cropping changes neither sample
  positions nor signal levels. The first encoder accepts neutral grayscale
  engraving; remaining colored pixels are rejected. The luminance expression is
  recorded, but color equivalence with the XP driver is not established.
- The encoder converts row-major exposure into alternating forward/reversed
  rows with `00 FF` trailers and the observed C358 raw header. The verified
  JobServer codec produces the CG compressed counterpart.
- Raster origin equals crop pixel offset times six. Paths use the inferred
  1000 units/inch, with 0.1-unit coordinate rounding. Existing explicit returns
  to the first point are preserved; a closed path gets a final return when
  needed. Disconnected paths retain separate pen-up moves.
- Raster is emitted first, then vector speed/power/PPI and PU/PD/V commands.
  The framing uses the observed flatbed initialization and `normalstart START`,
  never `autostart START`. The original `set_xyup_feed` command is preserved;
  the known controller token warning may therefore remain in a future test.
- Source and exposure hashes, dimensions, page bounds, review flags and process
  settings are checked before writing. Outputs require a new directory.

This model deliberately keeps the native raster pitch separate from the ideal
physical vector geometry. XP nominal-167 coordinate quantization may differ:
167 samples times six is 1002 units, while the intended inch is 1000 units.
That distinction, raster origin/orientation and actual physical scale still need
XP reference comparison and measurement. No calibration claim follows from
passing a codec round trip.

## Original generated outputs and result

`job.raw.jbs.draft` and `job.cg.jbs.draft` contain the explicit marker
`( AURORA_DRAFT_UNCALIBRATED_V1 )` immediately after `!ZX`. Ordinary `prepare`,
the queue worker and the sender's wire profile reject it. Only the pure offline
encoder/validator uses `allow_draft=True`. Do not remove the marker to bypass
the pending validation.

`draft.json` records source identity, requested and native settings, inferred
coordinates, raster placement and output hashes. Current test artifacts are in
ignored `runtime/coreldraw-jbs-draft`, based on
`runtime/coreldraw-native-grid-draft`. The exact source remains capture
`1a0f7e91-725d-4daa-a037-3e822b54806e`.

- The square is 1000 by 1000 inferred job units, starting at (908.3,1230.0).
- `TEST` exposure is 141 by 42 pixels, origin (1008,732) inferred job units.
- The independently inspected raw raster has 42 valid trailers and decodes to
  the exact exposure SHA-256
  `e6dee165b53ec9b46216892ea6fcd23d3c2d262ffd8a7bba6f70ec3d44b8e86c`.
- Raw draft: 6,410 bytes, SHA-256
  `26385b29477c1f3df201bf3da76eee2739a688a370c1b353c8b4e66da3a9ec80`.
- Compressed draft: 1,479 bytes, SHA-256
  `693f2965797702d9b4c3620950275ab4be47017fe763bd191e6ac54352c0721d`.

At that stage the suite passed **68 Python tests and 21 frontend checks**. Checks
cover speed mapping, power/PPI, physical path dimensions and closure, raster
placement and row order, independently decoded signal bytes, draft rejection by
queue/wire, bad hashes and bounds, unsupported grids/color, explicit settings,
and exposure cropping/polarity. No new laser job was sent.

Current scope is one page, flatbed, zero origin adjustment, nominal-167 mode,
neutral raster engraving and the selected cutting paths. Multipage delivery,
rotary/focus modes, arbitrary resolution/color profiles and UI/service integration
remain future work. The requested XP comparison is now received; see the section
above for the corrected profile and remaining placement/rendering differences.
# Ordered dithering review — October 20

`aurora_jobserver.ordered_dither` now implements the measured Ordered 4x4 and
8x8 exposure tables for 167 DPI. It consumes existing exposure samples without
resizing, cropping or changing geometry. Input polarity is 0 blank / 255 full
exposure. Matrix phase is explicit; automatic origin anchoring remains pending.

`encode_ordered_draft` preserves cutting paths and returns marked drafts with
Autostart Off. Ordinary queue preparation and wire planning reject both raw and
compressed drafts. The production preference decoder still holds active
`DitherBitmaps`, including Ordered4/8. No printer package update is needed for
this offline development step.

The private reference review tool can be run from the repository root:

```powershell
python -m tools.build_ordered_dither_review runtime/xp-mcp-tests-20261020 runtime/ordered-review-new --x7-intake runtime/grayscale-probe-20261020/encoded-baseline/intake
```

Use a fresh output directory. Four complete raw drafts match the two independent
XP artworks at both matrix sizes, except the required draft marker; compressed
decoding preserves pixels, commands, settings and geometry. Two further drafts
use X7's own source pixels and retain its vector coordinates. PNGs and an
immutable verification report accompany the drafts. The tool neither prints nor
launches a renderer or connects to equipment. Private reference files are not
part of the public repository; portable phase/geometry/hold tests need none.

The phase candidate relates raster origins to the captured grid origin
(169,171) pixels. More than one phase fits the older eight-level artwork. A
targeted different-origin comparison is still needed before enabling the effect
for normal printing. Manual Contrast and other dithering algorithms remain held.

