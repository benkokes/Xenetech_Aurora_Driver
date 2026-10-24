# Offline raster-color model and native review intake

Owner confirmed original XP profile and accepted global settings restored after
all four raster captures, then authorized implementation.

`aurora_jobserver/color_rasters.py` now creates cropped per-color binary masks,
omits unmatched raster colors, combines the sampled horizontal regions, applies
palette processes and reproduces the observed pause/pen-up serialization.
Shared palette validation lives in `color_settings.py`; vector behavior still
passes its five independent XP file comparisons.

All four raster files reproduce byte for byte, except a mandatory draft marker,
from known flat RGB fills at their measured native-grid positions. Global mode
uses captured grayscale exposure and splits nonempty row bands; this does not
establish a general legacy luminance formula. The review builder also checks CG
commands, decoded pixels, origins, settings and normalized DPI. Eight marked
raw/CG files, input data, previews and verification hashes are preserved in
`runtime/xp-color-raster-preferences-20261019/model-review/`.

The new model accepts only bounded 167-DPI inputs with explicit binary coverage.
Fractional palette powers, multiple separated vertical regions per color,
partial coverage and disabled/zero-power colors combined with pauses remain
explicitly unsupported. Other synthetic mask/process combinations are model
checks rather than additional XP evidence. Normal preparation and wire planning
reject every marked output; no unmarked/Autostart option is exposed.

Eight added Python tests cover these cases and independent reference files.
Full Python suite: **184 passed in 55.203 seconds**, no skips. Log:
`runtime/xp-color-raster-preferences-20261019/raster-model-regression.log`.

## Experimental native intake

The existing intake flattened RGB to grayscale and selected one cut color.
The separate experimental build at
`build/frontend-color-review-20261019/Aurora.XpsIntake.exe` supports
`--color-review on` with the 167-DPI Corel grid. It preserves hashed RGB samples
and nonwhite coverage and extracts all eligible thin opaque stroke colors.
Transforms, clips, width limits, transparency and dash review checks still apply.

Review manifests use schema **3**, status **offline_color_review_only** and an
explicit page warning. The ordinary Scene loader refuses them. The coverage is
diagnostic: white paint cannot be distinguished from the opaque white background,
and exact RGB matching does not solve antialiasing, gradients or bitmap color
quantization. This mode does not feed the live print encoder.

**31 native frontend tests passed**, including new RGB channel, coverage, palette
stroke, alpha/configuration and review-warning checks. The existing real Corel
square-and-TEST capture also passes ordinary/review comparison: source, raster
pixels/metadata, cutting path and dimensions are unchanged at matching 0.2-mm
stroke settings. RGB/coverage hashes and the schema hold are independently
verified in `native-color-review-verification.json` beside the test logs.

These tests do not constitute a new X7 print of the colored-fill drawing.
That real capture is the next input needed to compare native color samples and
placement with XP. No printer/installed intake was replaced, no desktop mode
changed and no physical connection occurred. Production UseColors remains held.
