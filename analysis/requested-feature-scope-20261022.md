# Owner's required features before packaging

On October 22 the owner identified three wanted XP features: per-color
power/speed/PPI, Bottom-Up Engraving, and Cylindrical Mode. These now take
priority over standalone packaging and broad duplication of completed tests.

## Bottom-Up Engraving

Implemented in the normal 167-DPI print encoder and supported by the complete
per-job preferences snapshot. Independent XP files establish row reversal,
PICT-LL origin, and the (height-1)*pitch origin adjustment. Existing raw-byte,
native, and loopback tests passed. This is not evidence of physical bottom-up
acceptance. Next: one asymmetric, recognizable physical sample through the
normal Corel print path when the owner prepares material and authorizes it.
Do not repeat the already successful XP baseline/Bottom-Up captures.

## Per-color power/speed/PPI

The original 16-color table and immutable job settings exist. Offline vector
and flat-fill raster models have independent XP evidence; semantic coverage
preserves X7 edges. Production UseColors is still held. The experimental
schema/reader and draft encoders are not yet the normal print pipeline.

Next: finish the production route for supported opaque colors, establish the
remaining mixed raster/vector boundary using the prepared reference rather
than repeating completed single-mode cases, and validate a compact multi-color
physical sample. Preserve hairline-width cut selection regardless of color;
color selects process settings, not whether a line is a cut. Unsupported images,
gradients, transparency, fractional color settings or combinations must retain
explicit holds until implemented and verified. Sorting and pauses have partial
evidence but are not additional requirements inferred from this request.

## Cylindrical Mode

The owner confirmed there is no rotary attachment available and requested
implementing what can be established without hardware. The preference is
transported, but production holds it and the normal encoder emits flatbed mode.
The original setup formula has now been recovered and implemented in a marked
offline draft encoder; surface/placement and physical behavior are still
unverified. Do not guess a diameter or enable rotary motion based on the checkbox.
See priority-feature-development-20261022.md for the code, evidence, and checks.

## Execution order

Bottom-up physical acceptance is the smallest remaining validation; per-color
production integration is the main software task; rotary needs attachment and
XP behavior evidence. Independent offline work can proceed while waiting for
the owner. This scope update performs no print, device connection, mode change,
driver installation, or XP network reconnection.
