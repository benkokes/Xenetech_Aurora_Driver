# Offline per-color vector model

All five actual XP references are preserved under
`captures/xp-color-preferences-20261019`. The owner confirmed original-profile
and accepted global settings restored after collecting them.

`aurora_jobserver/color_vectors.py` produces a vector command body from native
paths, explicit opaque RGB colors and the original 16-color settings table.
It implements exact color lookup, unknown index 16 with process fallback to
White (15), reverse draw order within a sorted color, per-field process caching,
disabled/zero-power omission, and return-to-origin pauses at color transitions.
The unmatched sentinel is retained for ordering rather than clamped early.

Given the independent global capture's geometry/pixels and known input colors,
the existing raster encoder plus this body reproduces all five complete raw XP
files byte for byte. The unknown-color White fallback retains the observed
100-ips setting in this offline model only. Converted CG output preserves
decoded paths, process values, raster samples, origins and normalized DPI.
Comparison drafts retain the marker that blocks preparation and wire planning.

The global multi-path reference exposed repeated PU / 2 RA setup in artwork.py.
The global encoder now emits that setup once between successive paths, exactly
as XP does. Geometry and process values are unchanged; single-path output is
unchanged. Per-color framing intentionally differs and remains in its own model.

Seven added test methods cover the independent reference files and hashes,
ordering/caching, no input mutation, explicit malformed-input rejection, disabled
paths, production holds, and draft blocking. Full suite: **176 passed in 54.585
seconds**, no skips. Log:
`runtime/xp-color-preferences-20261019/vector-model-regression.log`.
Native conversion and simulator tests use this host's loopback interfaces only.

The model is **not connected to the print pipeline**. Production UseColors is
still held before encoding. Colored raster segmentation, frontend extraction of
multiple cut colors, arbitrary bitmap quantization and physical per-color output
remain unfinished. Fractional color power and pause/disabled combinations are
explicitly rejected by the model pending independent evidence. Tests of other
cache combinations and White-versus-unknown sentinel ordering are synthetic/static
checks, not additional XP captures.

Next evidence is the prepared filled-square raster sample at
`Z:\Aurora-XP-Reference\color-raster-preferences-20261019`. Its Corel 11 save/reopen
and package hashes are verified; it has not yet been printed in XP. The five
earlier vector captures do not prove full per-color raster compatibility.
