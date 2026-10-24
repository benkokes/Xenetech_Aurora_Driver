# Per-color preferences: preparation and static evidence

The owner selected per-color processing as the next feature after the completed
Invert/Bottom-Up references. **Use Color Settings remains held** in the backend
until independent XP captures establish the intended output. No host color
processing or physical delivery was enabled during this preparation.

## Controlled artwork

`tools/prepare-color-reference.ps1` used the existing CorelDRAW X7 document API
to create a new 30 × 18 inch drawing and save it as CorelDRAW **11**. It did not
print, change printer settings or edit the owner's existing documents. It
restored the previously active document after closing its own sample.

The reference contains a .125-inch black filled square (raster marker) plus
five .25-inch outline squares in creation order Blue1, Red1, Blue2, Red2,
UnmatchedOrange. Outlines are .003 inch, matching the width of the previously
captured red-square reference. Colors are exact RGB 0/0/255, 255/0/0 and
255/128/0, with no fill. Orange is deliberately absent from the palette.

Creation order and Corel's reported shape collection order are recorded
separately. Do not assume either is the final XP path order. Repeated red and
blue paths distinguish grouping from equal-color ordering. The raster marker
keeps the mixed-output reference representative of the current transfer path.

The Corel 11 file reopened with exactly matching geometry, colors, outline
widths and fill state. Independent packaging checks verify its RIFF/CDRB
signature, file length and hash:
`ad93dc761fad06199eb89331609d646080dc0d957de2f2d5a8f6531dc65e626c`.
Original files and API report are at
`reference/artwork/color-preferences-20261019/`.

The copy-only collector package and manifest are at
`runtime/xp-color-preferences-20261019/package`. It was copied into the existing
Downloads share, with every packaged file hash checked. XP path:
`Z:\Aurora-XP-Reference\color-preferences-20261019`.
This is **prepared artwork, not an XP capture**.

Subsequently the owner captured all five cases: global, unsorted, sorted,
paused and disabled Blue. Preserved
jobs and actual results are recorded in
`runtime/xp-color-preferences-20261019/progress.md`; the original package's
prepared-state manifest is historical and remains unchanged.

## Static findings to check independently

These refer to the matched original graphics module disassembly. Vendor code
was read, not loaded or executed for this analysis.

- Palette lookup at 0x00406eae masks the supplied color to 24 bits and performs
  exact equality against sixteen entries. It returns 16 when there is no match
  or color use is off. This does not alone prove the final unknown-color
  behavior: earlier drawing callbacks can filter an unmatched color before
  parameter selection. The orange sample is intended to resolve that.
- The unsorted XP capture now resolves this sample: orange is retained with
  100000 native speed / 10% / 1000 PPI, matching the last White entry. The
  vector-output clamp at 0x00405dcf–0x00405dde maps an out-of-range index to 15.
  Global fallback or nearest-color matching would not reproduce this result.
  These high-speed values are offline evidence, not physical validation.
- Parameter selection at 0x004077c8 chooses raster or vector defaults, then
  overrides speed, power and PPI for a matching active palette entry when color
  settings are enabled. A disabled entry sets selected power to zero. Zero
  power makes this helper return false, so downstream output can be omitted.
  Power comes from an original byte value; speed and PPI are integer fields.
  Fractional per-color power precision remains unverified.
  The disabled-Blue capture confirms omission of both blue paths and their
  process commands. Removing that contiguous block from sorted output
  reproduces the entire disabled file byte for byte; remaining red/orange
  paths and the black raster marker are unchanged. Pause was OFF for this
  isolation case, so disabled/pause interaction is still unverified.
- The vector insertion branch at 0x00405cf3 distinguishes drawing
  order from palette-index order. The sorted branch uses `jbe` at 0x00405cff:
  an equal-index new object can be inserted before an existing object. Do not
  substitute a stable language sort without checking equal-color paths.
  The sorted XP capture now confirms palette order with reverse draw order
  within each color: Red2, Red1, Blue2, Blue1, UnmatchedOrange. A multiset
  comparison confirms every complete path and its process settings survived
  unchanged, as did the raster marker. Report:
  `runtime/xp-color-preferences-20261019/unsorted-vs-sorted/order-verification.json`.
- The path output routine at 0x00405d9b selects per-object settings and caches
  speed/power/PPI, emitting a command only when its value changes. Complete byte
  matching will therefore require transition caching as well as correct values.
- The pause branch at 0x00405f53–0x00405f7b requires color use, a pause flag,
  emitted current output and a following path of a different color index. It
  calls 0x00407468, which returns to 0,0 and writes PAUSE. The expected count and
  location must come from a capture, including disabled/zero-power colors.
  The paused XP capture confirms exactly two `0. 0. V\rPAUSE\r` insertions:
  Red1 to Blue2 and Blue1 to UnmatchedOrange. Removing only these sequences
  reproduces the sorted capture byte for byte. No pause precedes the first
  vector after the raster marker or follows the final color. Disabled-color
  interaction with pauses remains unverified; the next disabled case has
  Pause OFF to isolate omission behavior.
- Raster output at 0x0040910e calls the color-region sort when color use is on.
  Per-color raster segmentation/merging is a separate problem from assigning
  vector processes. The first sample uses only a black filled raster marker;
  it does not establish arbitrary colored fills or bitmap separation.

## Capture sequence

Ask for one case at a time and preserve each result before Default.jbs can be
overwritten. The first requested case is **Use Color Settings OFF**, with the
same accepted global raster 30 ips/45% and vector 1 ips/15%/1000 PPI, Both,
167 DPI, normal orientation, no offsets and Autostart off.

Later cases use explicit identification settings (not material presets):
Black 30 ips/45%/1000, Red 1 ips/11%/500, Blue 2 ips/22%/750. Save the owner's
original color profile under an unused name before any changes. Compare
unsorted, sorted, pauses, then disabled Blue, restoring the profile afterward.
All instructions are in the packaged COLOR-PREFERENCES-READ-ME.txt. Laser off,
XP disconnected, XP JobServer closed and host Capture only throughout.

All five actual XP captures have now been preserved and independently decoded.
The series-wide report is
`runtime/xp-color-preferences-20261019/capture-series-verification.json`.
These establish the sampled vector behavior and black marker only, not full
per-color raster support or physical validation. Production UseColors remains
held pending implementation and the remaining raster evidence. Original-profile
restoration has been requested; no confirmation is recorded yet.

At preparation time, actual-user VBox reads confirmed the VM running with its
network cable off and other NICs absent. The host status file remains Capture
only with no active session/print or error. No XP or host print was submitted
by this preparation script. Existing 167-DPI inversion/bottom-up implementation
and normal print behavior were not changed.
