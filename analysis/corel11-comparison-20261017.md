# Offline XP artwork comparison

Received `after-print-22432-3233/inbox/Default.jbs` from the shared reference
folder. Preserved a project copy at `captures/xp-corel11-test-20261017` with the
before/after inbox listings. The earlier listing was empty; afterward it held
one 6,341-byte file. SHA-256:
`4eea537809c0a3248d32bde7bd30df2060d60fec572049308fadc44f3fe7e2e7`.

Independent decoding validates all 42 row trailers, the 140 x 42 raw C358
raster, nominal 167 resolution fields, flags 0x41, snake row order and exposure
range 0..255. Only two levels occur: 0 and 255, with 2,484 exposed samples.
The job uses `normalstart START` and the requested raster 30000/30 and vector
1000/15/1000 speed/power/PPI. The known `set_xyup_feed` command remains.

XP emits the square from (876,1212) to (1878,2214), a 1002 x 1002 span. This
confirms nominal 167 DPI times the six-unit multiplier. The old draft's 1000
span was incorrect for exact XP compatibility. Added explicit
`xp-167-6mil-draft`, preserving the old profile for provenance. Its vectors use
round-to-nearest 28.4 pixel coordinates followed by the driver's multiply-six
and integer job-unit rounding, as supported by the static routine at 0x406490.

New intake `runtime/coreldraw-xp-grid-outlined` uses nominal/actual DPI 167,
5010 x 3006 page pixels, with optional `outline-aliased` text rasterization.
This uses captured font glyph outlines, not XP GDI hinting, and leaves gray
fills/images intact. Explicit tests verify actual bilevel black glyph pixels
and retained gray fills. Simply requesting the WPF text-rendering option did
not enforce bilevel output in this bitmap path.

New marked draft `runtime/coreldraw-xp-jbs-draft`:

- Raw: 6,226 bytes, SHA-256
  `6e4fe03f2bcac3aff3f716577b6f02d690f7d493d844bdc5e85a0ad68ac7d27f`.
- CG: 959 bytes, SHA-256
  `2d606e1b8bfbb2de2900a40fe6040c250fd42464596e9d43c688cc4bc643ac38`.
- Square: (910,1233)..(1912,2235), span 1002 x 1002; origin is +34,+21
  relative to XP. No hardcoded shift applied.
- Text: 140 x 41, origin (1008,738), 2,456 exposed samples, two levels.
  XP text is 140 x 42 at (978,720). Pixel identity remains unresolved.
- Exposure SHA-256:
  `61e063e22c13cf71eae7349b71dacb5901f8e679a70d0aa05bca1f662fe010e6`.

`python -m tools.compare_artwork_jobs REFERENCE CANDIDATE NEW-DIRECTORY`
independently decodes raw data and reports settings, vector bounds, raster
origins, signal statistics and top-left-aligned crop error without resampling
or concealing placement differences. Current result is
`runtime/xp-comparison-corrected/comparison.json`: settings and square spans
match; 568 of 5,880 padded crop samples differ, mean absolute signal error
24.63265. This error compares cropped images, not absolute page positions.

The owner supplied an XP Print Layout screenshot showing As in document,
100% scale, no centering. X7 reads identical saved ruler/page origins in the
source and converted CDR: page left -0.0015472441 inches, top -0.0064921260.
The read-only `xp-artwork-state.vbs` helper was placed in the shared reference
folder to collect CorelDRAW 11's interpretation of the loaded document. That
report is pending. Do not assume the remaining translation is a machine offset.

Update: both reports are now preserved with the raw reference. Collector v1
could not access the old Shapes.Item interface; v2 uses enumeration and returns
the shape geometry. XP 11.633 reads the exact same square position
(0.908783464566929, -1.23827165354331) inches and 1 x 1 inch dimensions. Its
document origin also matches X7. The active XP file is Z:\test-corel11.cdr;
the host shared-root copy has the same SHA-256 as the prepared version 11 file.
The document ReferencePoint is 3 (top-left) on both hosts. Thus the vector
translation does not originate in an edited or shifted source shape.

The text object measures differently despite the same content, Arial font and
24 pt size: XP's position X is 0.998452755905512, width 0.84505905511811 and
height 0.246889763779528 inches; X7's are 1.0057874015748, 0.837614173228346 and
0.247334645669291. This is evidence of different text layout/font metrics; do
not force identical raster dimensions by padding/cropping samples.

Static analysis also recovered the driver's separate surface-allocation DPI
helper: nominal 167 becomes 166.667, yielding a 5000 x 3000 page surface while
the driver advertises 167 DPI. Details and decoded constants are in
`driver-coordinate-rules.md`. This suggests an application page-mapping cause
for the remaining placement shift. It is not yet confirmed. A second offline
reference at 100 DPI is requested; source/settings stay the same, with only
resolution changed and then restored. Instructions are in
`capture/XP-100-DPI-COMPARISON.md` and the shared reference folder.

Attempted native XP window inspection through the computer-use skill, but
window capture failed on both the initial attempt and the allowed recovery
attempt (FrameArrived/window capture timed out). No UI input or printing was
performed. The corrected v2 collector was validated on host CorelDRAW via
read-only automation before the owner ran it in XP. Some old-version metadata
properties remain unavailable, but enumeration/PositionX/PositionY/dimensions
were successfully collected.

Validation: 72 Python tests and 22 frontend checks. A flaky pre-existing socket
simulator assertion surfaced under fragmented replies: its status thread
could run before the main thread marked an already-received sync. The fixture
now marks synchronization on receipt and waits at most one second for cross-
thread processing; an actual status-before-sync deadlock still fails. No sender
or physical protocol behavior changed.

No new physical job was sent, and draft markers/normal queue and wire rejection
remain enforced. XP must stay offline with JobServer closed while its captured
test job remains in the watched inbox. Cleanup and any physical comparison are
separate pending steps.
