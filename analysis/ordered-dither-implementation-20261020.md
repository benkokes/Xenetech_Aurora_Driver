# Ordered dithering implementation — October 20

Implemented `aurora_jobserver/ordered_dither.py`: recovered Ordered4/8 tables,
explicit normalized phase, immutable binary exposure output, unchanged input
size/row order, bounded 167-DPI geometry, and a draft-only encoding API. Uses
row/column byte translation without new dependencies. No production decoder,
installed driver, UI preference, printer defaults or physical delivery behavior
was changed. `DitherBitmaps` remains an explicit production hold.

`tools/build_ordered_dither_review.py` verifies immutable input hashes before
creating a fresh review directory. It writes only marked, non-autostart drafts,
previews and verification evidence. An unmarked comparison exists in memory
only; no unmarked output file is written.

Results:

- Four complete raw jobs, two independent XP artworks times two algorithms,
  match the captured XP bytes exactly except the required draft marker.
- Compressed forms independently decode to identical pixels, dimensions,
  origins, process settings, row order and commands. Native raw and CG DPI
  fields use different representations; the check compares decoded DPI.
- Two review drafts use the actual X7 intake exposure, preserving its source
  pixels as algorithm input, raster rectangle and vector coordinates. They are
  previews, not claims of XP renderer pixel identity or physical validation.
- 34 targeted tests passed, including eight new tests (seven portable and one
  private-reference test covering four jobs), existing raster preferences,
  output-mode handling, native conversion and loopback controller checks.
- Invalid dimensions, mutable/wrong-length input, unsupported algorithms,
  missing/invalid phase, wrong DPI/grid, out-of-bounds geometry and vector-only
  misuse are rejected. Crop/tile phase consistency and threshold boundaries
  pass. Source scenes remain unchanged.
- Both draft formats are rejected by ordinary queue preparation/wire planning.
  Every active production dithering mode remains held before encoding.
- Existing output directories and changed reference hashes are rejected before
  evidence is overwritten or a new output directory is created.

The first test assertion compared raw/CG encoding metadata directly and failed
because their native resolution fields differ (167 vs167000). Corrected the
test to compare decoded resolution/geometry/pixels; the implementation already
matched all four raw XP files. Final targeted log is preserved.

Evidence: `runtime/ordered-dither-dev-20261020/targeted-regression.log`,
`ordered-tests.log`, `review/verification.json`, six marked raw/CG drafts and PNG
previews. Final state audit is saved beside them. Existing full-range and older
reference captures were read without printing again. No XP UI interaction,
device connection, equipment status probe or laser send occurred in this step.
All network test traffic was confined to the loopback controller simulator.

Remaining phase question: the recovered tables exactly fit both artworks at
appropriate offsets, and a grid-origin rule fits. Arbitrary-origin anchoring has
not been independently confirmed. The API therefore requires explicit phase,
the review tool labels its origin rule a candidate, and normal printing keeps
the effect held. A different-origin experiment should be specifically targeted
at this ambiguity. Contrast still requires an image-dependent quantizer;
Floyd/Jarvis/Stucki implementations remain outside this increment.
