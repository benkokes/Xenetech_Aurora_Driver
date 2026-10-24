# XP printer Preferences feature map

**October 23 per-color raster/mixed acceptance:** three raster colors and two
vector colors completed correctly, end 0 / 28.39 seconds / one exact upload.
Normal pipeline 4 supports per-color Raster Only and Both at 167 DPI for opaque
solid fills/text, with Pause, Bottom-Up and Invert off. The new actual XP mixed
reference proves the multiple-raster-to-vector boundary; its observed Blue-omitted
case is recorded explicitly. A standalone development package is being validated.
See [acceptance and package evidence](per-color-raster-mixed-and-package-20261023.md).
Older held-feature notes below describe earlier development stages.

**October 22 Bottom-Up acceptance:** the owner observed bottom-up scanning and
confirmed complete, upright, correctly positioned artwork with no unexpected
marks. Raster Only, 167 DPI, 30 ips/45%; controller end 0, 81.680 seconds, one
exact upload and cleared guard. See [physical validation](bottom-up-physical-validation-20261022.md).

**October 22 physical acceptance and rollout:** the owner accepted all five
per-color vector paths with no unwanted marks. Controller end 0, 15.648 seconds,
one exact upload and cleared guard. Normal **Vector Only at 167 DPI** now supports
Use Color Settings; JobServer restarted and confirms pipeline 3. Raster/mixed
per-color output remains held. The earlier gated-development notes below are
historical. See [physical acceptance and rollout](per-color-vector-integration-20261022.md).

**October 22 per-color update:** the native Vector Only per-color pipeline is
implemented behind an explicit validation gate, with immutable palette values,
the measured zero-power carrier, and durable all-disabled-color no-op handling.
Normal UseColors remains held pending physical acceptance. Seven new native
tests pass; all 252 discovered checks pass including two WSH fixtures rerun
outside the sandbox. The exact staged five-path test also passes once-only
loopback delivery. See [integration](per-color-vector-integration-20261022.md).
This does not enable raster/mixed color printing.

**Current update (October 20):** r9 (0.5.1.0) is installed with the complete
visible controls and immutable settings transport. Invert and Bottom-Up now
match independent XP files and are implemented at 167 DPI. Five vector-color
and four raster-color XP captures now establish the sampled offline color
model. Three real host capture tests and the semantic coverage fix preserve
X7's edges. Full Python suite: 198 passed, followed by one added passing mixed
host test; 36 native tests and 64 synthetic compositions passed. Use Color
Settings remains held for delivery pending mixed-boundary/content evidence and
physical validation. See [current color results](semantic-color-coverage-20261020.md).
Older installation notes and their test counts below are historical.

**Subsequent owner-directed X7 tests:** 16 actual capture-only jobs verify full
settings transport for dithering, contrast, mirror/rotation, focus and Beam Off.
The 15 non-default cases remain held; their effects are not implemented yet.
The run also exposed lossy JPEG conversion of bitmap artwork in the X7 print
path. Fix lossless capture before judging bitmap-processing parity. See
[X7 test results](x7-feature-tests-20261020.md).

The owner supplied Laser Output Control, Advanced and Color Settings screenshots
on October 18, 2026. This map distinguishes the original controls from the
replacement's current behavior; matching the appearance alone is insufficient.
The installed driver is now r7 (0.4.1.0), adding tabs and material presets while
preserving the native option set and the working 167-DPI default.

Sources: the owner's screenshots; extracted original help under
`analysis/extracted/driver-help`; matched XP graphics/UI DLLs; the controlled
100/167-DPI captures; accepted physical 167-DPI tests. Vendor DLLs were read,
not executed on the host. The screenshot's color powers are the owner's selected
profile, not established factory defaults.

| Original control | Replacement / next evidence |
|---|---|
| Raster power/speed; vector power/speed/PPI | Implemented in per-job settings and verified through real CorelDRAW printing. Current speed choices reach 31 ips; the original display reaches 150 ips. Extend only after confirming the model's accepted range. |
| Both Raster and Vector | Implemented and physically verified. |
| Raster Only / Vector Only | Three XP captures verify filtering. Raster Only passes XP reference and X7 checks. Vector Only at 167 DPI now uses a physically accepted zero-exposure/zero-power CG carrier with the requested vectors; it does not guess the original pure-vector protocol. Hairline width selects cuts regardless of color; empty cut-only work is recorded locally without sending. See [integration](vector-only-production-20261022.md) and historical [mode results](output-mode-results-20261018.md). |
| Use Color Settings | Vector Only at 167 DPI is implemented and physically accepted, using each print's attached palette and the measured zero-power carrier. Five independent XP vector references support the command model. Raster/mixed per-color output remains held for content and boundary evidence. |
| Sort Color Vectors / Pause Between Colors | Sorted/unsorted repeated-color vector order and raster/vector color pause commands match independent XP cases. Equal-color vector groups reverse drawing order. Pauses combined with disabled colors and the multi-raster-color/vector boundary remain held. |
| Invert Raster Output | Implemented at 167 DPI: captured grayscale samples complement exactly within unchanged bounds. Full raw job matches XP; native and loopback checks pass. Physical test pending. |
| Bottom-Up Engraving | Implemented and physically accepted at 167 DPI. The owner observed upward scanning, complete upright artwork and correct placement. Rows reverse, PICT-LL replaces UL, and origin shifts by (height-1) times pitch. Full XP raw-byte matches, native and loopback checks also pass. |
| Focus: none, manual, thickness, autofocus | No Focus is implemented. Others require command/unit comparisons; do not invent Z motion. |
| Autostart | Implemented as a per-job selection. Tests used Off and the machine Start button. |
| Beam Constantly On | Original resource/control and bit mapping recovered: bit 0x100 selects `40 PWF`; clear selects `1 PWF`. Off still held pending controlled output confirmation; see [static evidence](preferences-static-evidence-20261018.md). |
| Plate width/height | Current 30 × 18 inch flatbed profile only. Other dimensions require surface/capability and edge-placement checks. |
| Plate offsets / horizontal or vertical center | Need known geometry at changed offsets to separate app layout from driver placement. |
| Cylindrical Mode | Original setup arithmetic recovered and implemented in marked offline drafts; normal printing remains held. No rotary hardware is available. UI sizing, surface/placement, and physical calibration are unverified. See [current development](priority-feature-development-20261022.md). |
| Material Setting, Save, Delete | New implementation built and native-tested. Saves complete named presets per Windows account; loading only edits the dialog, and OK copies settings into the job. Presets are not read later by a queued job. |
| Resolution | Original values: **50, 100, 167, 200, 250, 333, 500, 1000, 1200 DPI**. Native selections currently 100/167. Other values require offline comparisons; 1200 has a separate coordinate path. |
| Travel Speed | Currently emitted as the existing fixed command. Need units and changed-setting capture before exposing an editable value. The known controller token warning is retained. |
| Clip Art / Photo / Custom | Recover the preset combinations from original UI code and compare their bitmap output. |
| Dither off; ordered 4×4/8×8; Floyd–Steinberg; Jarvis; Stucki | Not implemented. Need a grayscale ramp with dither off plus one capture per algorithm. Do not assume a standard library produces XP's thresholds, traversal or rounding. |
| Manual contrast: low/high/number of colors | Need grayscale-ramp comparisons with controlled bounds and quantization. Static code caps the original byte count at 255; existing inactive replacement snapshots carry 256, requiring compatible migration before activation. |
| Plate orientation 0°, left/right 90°, 180° | Need an asymmetric raster/vector sample, with plate/page geometry preserved. |
| Engraving normal / reverse-mirror | Need asymmetric raster/vector comparison; determine which geometry is mirrored. |
| Rubber Stamp enable / profile | Original stamp DLL dialog resources recovered: Depth, Split Power, Shoulder, Base and profile controls. Units, factory profiles and representative output remain unverified. See [static evidence](preferences-static-evidence-20261018.md). |
| JBS location / default name / date-time suffix | JobServer already retains unique jobs and history. These legacy file-handoff controls need a modern archive/export equivalent, not the XP watched-folder path copied into the new system. |
| Laser Model | Replacement currently targets this Aurora's configured flatbed only. No unsupported model selector. |
| Color table enable/name/RGB/power/speed/PPI | Immutable 16-color snapshots are parsed and validated. Independent enabled/disabled-color files establish Black/Red/Blue processes; unmatched vectors use White's process while unmatched raster colors are omitted. Full-snapshot native review is offline only. Fractional color powers remain held. |
| Current Color Profile, Save, Delete | Add after per-color print-ticket serialization and output are verified. Keep these distinct from whole-material presets. |

## Resolution evidence

The graphics DLL's helpers at 0x00409b01 and 0x00409b61 map ordinary resolutions
to these coordinate pitches / spot strings:

| DPI | Pitch / spot string | 30 × 18 inch XP surface | Evidence |
|---:|---:|---:|---|
| 50 | 20 / 20.000 | 1500 × 900 | Static driver mapping |
| 100 | 10 / 10.000 | 3000 × 1800 | Independent XP capture |
| 167 | 6 / 6.000 | 5000 × 3000 | Independent XP capture and physical test |
| 200 | 5 / 5.000 | 6000 × 3600 | Static driver mapping |
| 250 | 4 / 4.000 | 7500 × 4500 | Static driver mapping |
| 333 | 3 / 3.000 | 10000 × 6000 | Static driver mapping; nominal/surface mismatch |
| 500 | 2 / 2.000 | 15000 × 9000 | Static driver mapping |
| 1000 | 1 / 1.000 | 30000 × 18000 | Static driver mapping |
| 1200 | special / 0.833 | 36000 × 21600 | Separate arithmetic at 0x004065b7; needs capture |

See [coordinate analysis](driver-coordinate-rules.md). Surface values outside
100/167 are predictions from the original allocation routine, not independent
capture validation. The original intake used a full-page 50-megapixel bound:
500 DPI alone would need 135 megapixels on this bed. Bounded document-grid
offline rendering is now implemented, preserving the final engraving-region
limit. The actual Corel capture rendered successfully at all nine resolutions;
the report is `runtime/original-dpi-preview-matrix-20261018/resolution-review.json`.
These previews do not apply the legacy placement fit or establish XP equivalence.
Raster and vector placement must both be checked before native options are added.
All 27 native intake tests and the 115 Python regression tests pass.

## Current native UI work

The revised native form builds and passes tests for the original four tab names,
first-screen raster/vector controls and material Save/Load/Delete. Resolution
moves to Advanced, matching XP. Features without an implemented output path are
identified explicitly, rather than accepting settings which do nothing.

Native tests cover immutable preset snapshots, XML reload, load followed by
Cancel, delete, rejecting concurrent stale edits, rejecting DTDs, deferred OK
and Windows' in-memory 46/16 merge. No print or printer-default change occurs.
The earlier r6 package is retained for rollback.
The next controlled comparison is prepared at
`Z:\Aurora-XP-Reference\500-DPI-READ-ME.txt` in the existing XP shared folder.
It keeps the original application offline, collects the raw watched-inbox job,
and restores 167 DPI without sending the new job to the laser.

## Owner's current priority

The owner subsequently requested keeping **167 DPI** as the working setting.
No higher native resolution is being enabled. The owner completed the 500-DPI
capture and restored 167. After an initial shared-folder check, the new collector
folder `after-print-18068-12044` appeared and was preserved under
`captures/xp-corel11-resolution-review-20261018-after-print-18068-12044`.
No additional print or capture-path reply is needed.

The 52,458-byte original raw job has SHA-256
`e340bd356fb9047f45b9cae62164a34662beda2a7aff3a4eea4a5ad9730123fe`.
It confirms 500/500 raster headers, `2.000 set_gspot`, a 418 × 124 raster at
(1006,736), raster 30000/45, vector 1000/15/1000 PPI and Autostart off. The square
corners are (908,1230), (1908,1230), (1908,2230), (908,2230): a 1000 × 1000 span.
All vector coordinates match the prior Corel placement model extrapolated to
500 DPI, without introducing a new offset. This extends offline reference
evidence; it does not validate physical 500-DPI engraving or enable it in the
native printer. The working setting remains 167 as requested.

Decoded pixels, commands and verification are retained under
`runtime/xp-resolution-review-18068-12044`. No laser I/O occurred.

The independent tab/material update is packaged and signed as r7, version
0.4.1.0. It preserves the GPD, native option set and 167-DPI default. Its catalog
SHA-256 is `9d745db2a8fe8d023f4635b5a00f1a76eb8e549b4a74c2c141b1ea7d7de72cd0`.
Native GPD expansion, Inf2Cat signability, the reused trusted signature,
installer syntax/dry-run and eight per-option regression tests pass.
Windows installation completed. The installed registry version and file hashes
match r7; default and user tickets still match the accepted 167-DPI / 45/15
selections. The page remains 30 × 18 inches at 600 source DPI. The CorelDRAW
window/preset user check is pending; see `runtime/printer-properties-r7-verification.json`.
No new certificate trust was added and JobServer remains capture-only.
