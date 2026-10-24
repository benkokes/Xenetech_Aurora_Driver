# Offline Preferences development with the laser off

The next comparison tooling and bitmap reference package are ready. No laser
connection, print submission, VM network change or installed driver update was
performed. JobServer remains Capture only. New Preferences behavior is not
enabled by diagnostic pixel matches.

## General preference comparison

`tools/compare_preference_jobs.py` compares mixed, Raster Only and Vector Only
jobs, including multiple pictures and raw C358 or compressed CG pictures. It
walks command/picture boundaries without searching binary pixels for commands.
It validates picture lengths, trailers, seven-bit compressed data and job
completion. Comparison input and total decoded picture sizes are bounded;
invalid input is rejected before a report directory is created. Existing
reports are never overwritten.

Use the workspace Python runtime with:

```text
python -m tools.compare_preference_jobs reference.jbs candidate.jbs new-report-directory
```

Each report contains JSON and decoded grayscale PNGs. It separately records:

- Raster count, dimensions, origin coordinates, UL/LL label and process settings.
- Encoded resolution fields and effective DPI (CG fields use 1000 times raw DPI).
- Pixel equality, mismatch count, average signal difference and matching flips,
  180-degree rotation or inversion. Multiple possible matches are retained.
- Vector geometry and process settings per path, plus normalized text commands.

Title and the offline draft marker are excluded from command equality but
recorded explicitly. Raster pairs follow capture order, so an ordering change
must be examined instead of assuming that the same-numbered pictures correspond.
The tool preserves stored row order after undoing the existing bidirectional
packing. It does not normalize LL to UL or infer physical scan direction from
pixels. This distinction is necessary for the Bottom-Up comparison.

Checks against the independent three XP output-mode captures reproduce the
expected filtering: Raster Only has identical pixels, origin and settings;
Vector Only has identical vector geometry and no picture. A raw/CG comparison
of the actual X7 Raster Only job preserves every sample and its effective DPI.
Reports: `runtime/offline-preferences-dev-20261018`.

## Asymmetric bitmap reference

`tools/make_preferences_sample.py` prepares a new directory containing a
167 × 167, 24-bit uncompressed BMP, PNG reference, manifest, instructions and
three copy-only XP collectors. The bitmap has eight grayscale values, an L,
triangle, stepped wedge and isolated gray marker, with white margins and gaps.
None of its eight flip/inversion variants are ambiguous with the original.
The intended imported size is exactly 1 × 1 inch at 167 DPI; the instructions
explicitly set this size because BMP resolution metadata uses rounded integer
pixels per meter. No fonts or embedded file links are needed.

Generated package:
`runtime/offline-preferences-dev-20261018/xp-bitmap-reference`.
An identical hash-verified copy is in the existing shared folder at
`C:\Users\xws\Downloads\Aurora-XP-Reference\bitmap-preferences-20261018`,
visible in XP as `Z:\Aurora-XP-Reference\bitmap-preferences-20261018`.

The three planned original-driver cases are baseline, inversion only and
bottom-up only. Use a new document, retain the same image size/position, keep
167 DPI, Custom bitmap with dithering/contrast off, raster 30 ips/45%, No Focus
and Autostart off. Collect after each print before Default.jbs is replaced.
Restore Both and the two options off afterward. The package instructions
require the laser off, XP cable disconnected, XP JobServer closed, and the host
in Capture only. These are future XP file captures, not completed references.

The comparison tools use no networking. Seven added regression cases cover
independent XP output, raw/CG equivalence, multiple pictures, command-like binary
pixels, malformed files, numeric bounds, flip/inversion diagnostics, separate
placement changes, BMP padding/row order/DPI, PNG checksums/samples and
non-overwriting collector package generation. The full test result is retained
in `runtime/offline-preferences-dev-20261018/regression.log`.
All **139 Python tests passed** in 42.232 seconds. The generated BMP/PNG was
visually inspected, and its file formats, samples and checksums were checked
independently by the added tests. No native driver installation is required.

## Additional overnight validation

The owner authorized unattended offline testing and a single morning decision
handoff, with a continuation after the stated 3:09 a.m. usage reset. The first
overnight batch completed 128 real native provider roundtrips, independent
Python checks of 256 native tickets and 256 full XPS job scopes, thirteen form
component checks, and 3,600 seeded raster cases across 360 combinations.
The campaign checked 7,200 raw/compressed decodes, 12,000 malformed inputs and
7,200 draft-delivery guards, with sockets explicitly denied. These randomized
checks supplement rather than replace the independent captured XP references.

The final regression suite passed **146 tests** in 43.582 seconds. Aggregate
evidence: `runtime/offline-preferences-dev-20261018/overnight-verification.json`.
The installed driver and machine/user printer defaults were not changed.

XP window capture remained unavailable, so none of the three planned bitmap
references has been printed. The same disconnected VM and Capture only state
are retained. [New static evidence](preferences-static-evidence-20261018.md)
recovers the missing rubber-stamp dialog resources, original option flags and
a contrast-count compatibility issue without executing a vendor DLL. Current
progress, exact remaining work and batched decisions are preserved in
`runtime/offline-preferences-dev-20261018/overnight-handoff.md` for the scheduled
continuations and morning report.
