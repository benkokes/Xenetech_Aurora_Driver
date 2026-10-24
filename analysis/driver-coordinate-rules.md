# Driver coordinate rules: static evidence for the frontend

Inspected the already extracted XP `xtlasergr.dll` without executing it. SHA-256:
`6aad6387df4d5e83008f17badeb8d284a9031d63d4ff61699c148a5913bc2c0d`.
Addresses below are virtual addresses in that image.

## Resolution and job-coordinate scaling

The helper at `0x00409b01` maps the resolution argument to an integer scale:

| Resolution | Integer scale | Spot string from `0x00409b61` |
| ---: | ---: | --- |
| 50 | 20 | `20.000` |
| 100 | 10 | `10.000` |
| 167 | 6 | `6.000` |
| 200 | 5 | `5.000` |
| 250 | 4 | `4.000` |
| 333 | 3 | `3.000` |
| 500 | 2 | `2.000` |
| 1000 | 1 | `1.000` |
| 1200 | special coordinate branch | `0.833` |

Unknown values fall back to integer scale 1 / spot string `1.000`; this does
not establish that they are valid selectable driver resolutions.

## Surface dimensions differ from nominal DPI at 167 and 333

Additional static evidence: `0x00406dea` first multiplies the nominal resolution
by 1000, then substitutes 333333 for 333000 and 166667 for 167000. This helper is
used for page-surface allocation at `0x00406e1a`, separately from the integer
coordinate multiplier above. The allocation code multiplies this value by
0.001, the DEVMODE page width/height in 0.1 mm, and 0.00393701, adds 0.5 and
applies floor. Constants decoded directly from the matched graphics DLL:

| Address | Double |
| --- | ---: |
| 0x00402dd0 | 0.5 |
| 0x00402dd8 | 0.00393701 |
| 0x00402de0 | 0.001 |

For the 7620 x 4572 DEVMODE page this gives:

| Nominal DPI | Allocation DPI | Surface pixels | Nominal DPI x page inches |
| ---: | ---: | --- | --- |
| 100 | 100 | 3000 x 1800 | 3000 x 1800 |
| 167 | 166.667 | 5000 x 3000 | 5010 x 3006 |
| 333 | 333.333 | 10000 x 6000 | 9990 x 5994 |
| 500 | 500 | 15000 x 9000 | 15000 x 9000 |

`DrvEnablePDEV` stores the surface size at PDEV 0x244/0x248.
`FillDeviceCaps` (`0x0040463b`) reports those counts as both printable resolution
and physical dimensions in pixels, while reporting the unadjusted nominal DPI
at GDIINFO 0x28/0x2c. It reports physical millimeters using integer division of
the DEVMODE size by ten: 762 x 457 mm. Its reported pixel offsets are zero.

These inconsistent size/DPI descriptions may affect CorelDRAW's page mapping.
Half the nominal/surface difference at 167 is five X and three Y pixels,
equivalent to 30 and 18 job units. Those happen to equal the corrected draft's
raster-origin discrepancy. This is a hypothesis about application placement,
not proof of a fixed controller offset; do not silently subtract those values.
The vector discrepancy is 34 and 21 units, so additional application/GDI
quantization or placement behavior remains to be explained. A controlled
100-DPI reference is requested because its nominal and allocated dimensions
agree, providing a separate test of this hypothesis.

The coordinate routine at `0x00406490` reads the resolution fields at PDEV
offsets `0x9a` / `0xa0`, calls the integer helper, applies orientation, offsets
and optional reflection, then scales the incoming coordinates. The ordinary
branch at `0x0040665f` multiplies by the resolution-specific factor. At
`0x0040667e` and `0x0040668f` it shifts right three bits, adds one, then shifts
right one bit, consistent with rounding 28.4 fixed-point GDI coordinates to
integer output positions. Origins are added at PDEV `0x22c` / `0x230`.
Resolution 1200 has a separate arithmetic branch at `0x004065b7`, including
factors 50 and 6 and decimal remainders. It needs separate implementation and
test evidence; it must not be handled by the ordinary factor-1 fallback.

The bitmap writer shifts its pixel location left four bits before calling this
same coordinate routine (`0x00407aeb` through `0x00407af5`). It emits the returned
integer/decimal pair as `%d.%1d %d.%1d V`, and later writes the original nominal
resolution to each raw raster header (`0x00407bb3` onward). Header initialization
calls the spot-string helper and emits `set_gspot` at `0x00407565` onward.
The two reference rasters have nominal resolution 167 and `6.000 set_gspot`;
their vector coordinates are multiples of six, consistent with this path.

These factors support an **inference of approximately 1000 job coordinate units
per inch** for the observed ordinary mode. They also reveal a possible rounding
distinction: nominal 167 DPI times factor 6 is 1002 rather than 1000. Likewise,
333 times 3 is 999. A renderer using exactly 167 pixels/inch must not silently
assume it matches a physical pixel spacing of exactly 0.006 inches. The new XPS
intake currently reports standard page millimeters and a normal 167-DPI preview;
it does not yet map that preview to calibrated laser coordinates or exposure.

## Required confirmation before new job generation is validated

Update: the controlled CorelDRAW 11 capture of the one-inch square confirms a
1002 x 1002 unit span at nominal 167 DPI. The explicit XP draft profile now uses
167 samples/inch and the driver's 28.4 coordinate rounding. The original
1000-unit model is preserved separately. Placement and text rasterization still
differ, so neither this span match nor codec validation establishes physical
calibration. See `corel11-comparison-20261017.md`.

Capture a deliberately sized rectangle/line and raster feature from XP, with
known artwork dimensions, page size, print scaling, resolution, orientation and
origin. This can initially be an offline inbox capture with JobServer stopped;
it does not require engraving. Compare expected corners and raster placement
against the emitted commands, including the nominal-167 rounding distinction.
Repeat for a changed origin/orientation before those modes are supported.
Physical measurement is still required to establish actual dimensions on the
engraver. Speed, power and pulse-density units are a separate question.

The new frontend keeps page geometry separate from the JBS encoder so these
machine-coordinate and raster-spacing rules can be implemented explicitly.
