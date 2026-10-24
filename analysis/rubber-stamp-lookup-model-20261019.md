# Stamp lookup-table model (offline prediction)

The bounded objective of this pass was to recover the converter's basic edge
and narrow-gap lookup tables. `tools/inspect_stamp_kernel.py` implements that
arithmetic as an analysis tool. It emits JSON only; production imports none of
this module and the stamp feature remains held.

Sources are fingerprinted before producing predictions. The converter is the
same archived BmpPict2 DLL documented in
`rubber-stamp-converter-pipeline-20261019.md`, SHA-256
`1a851b834b1ad4ed3f339093fed57659a8ac3e5f5a8c69d9eaccd6254ffd2238`.
The profile/DPI inputs retain the three checked source hashes from
`rubber-stamp-static-model-20261019.md`. No vendor code was executed.

## Recovered helper behavior

At 0x1000cecc–0x1000cede, the converter stores SplitPower × 255 / 100 as a
binary32 value. Edge-table construction at 0x1000d08b–0x1000d198 ramps from
255 to the complementary split level, then toward zero over the remaining
BasePixels samples. It adds 0.5, converts through MSVCRT `_ftol`, masks to a
byte and subtracts from 255 to write each sample.

The distinction between `fst` and `fstp` matters. A ramp iteration stores a
binary32 copy for the **next** iteration while its current conversion uses the
unrounded subtraction still on the x87 stack. The model tracks exact rational
values and explicit binary32 stores, including ties to an even significand.
It models the bounded arithmetic, not arbitrary x87 control-word environments
or an executing DLL.

The narrow-gap helper at 0x1000ca8c uses a separate branch for a positive gap
width below twice SplitPixel. Its half-width calculation is
`floor(width / 2 + 0.6)`; for these positive integer widths that is the ceiling
of width / 2. It descends to the split level and ascends again, duplicating the
center sample for an even gap. It is a different table from merely cutting a
section from the ordinary edge table.

`0x1000ccfc` returns a cached table for a source gray value. Zero uses the full
base table; white returns a null table. Other source values keep only entries
strictly greater than that gray value, shortening the table. The zero case
must retain any zero entries in the original base table.

Hand-calculated checks include:

| Parameters: BasePixels, SplitPixel, SplitPower | Predicted samples |
|---|---|
| 3, 1, 60 (167-DPI fallback 1) | 153, 187, 221 |
| 5, 2, 30 (167-DPI fallback 2) | 38, 76, 121, 165, 210 |
| Gap width 3 using 5, 2, 30 | 38, 76, 38 |
| Gray source 153 using 3, 1, 60 | 187, 221 |

These are predicted helper values, **not independently captured XP samples**.
They do not authorize engraving or establish complete stamp parity.

## Evidence and validation

The immutable `stamp-kernel-gray-predictions-20261019.json` report in
`runtime/offline-preferences-dev-20261018` contains 45 edge tables, 301
narrow-gap tables, and eight gray-source cases for each profile/resolution.
It includes the relevant original instruction bytes. The earlier edge-only
prediction report is preserved as well. Reproduce a fresh report with:

```text
python -m tools.inspect_stamp_kernel analysis/extracted/tools-suite/BmpPict2/bmppict2.dll analysis/extracted/laser-driver/NewWorld_Files/XGWRegistry.dll NEW-REPORT.json
```

Five focused tests cover hand calculations, exact binary32 halfway cases,
gray-table threshold boundaries, invalid/unbounded inputs, all 45 profile
combinations, and absence of sockets or feature activation. The full suite
then passed **160 tests in 45.137 seconds**. Its log is
`runtime/overnight-stamp-lookup-regression-20261019.log`.

The installed XP converter version, live registry overrides, full two-dimensional
scan, edge interactions, row buffering, cropping, action selection and output
coordinates still need independent confirmation. Do not use these small tables
as a replacement for the unimplemented complete image transform.
