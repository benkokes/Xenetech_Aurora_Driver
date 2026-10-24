# Per-color, bottom-up, and cylindrical feature development

The owner selected these three features ahead of packaging, then confirmed
there is no rotary attachment available for physical testing. Implement what
can be established offline; do not represent rotary as hardware-validated.

## Changes

`aurora_jobserver/rotary.py` implements the matched XP graphics driver's rotary
setup arithmetic from original DEVMODE dimensions. Static extraction identifies
flag 0x4, `1 set_rotary`, and a five-decimal `zset_axis` value. The two doubles
are pi and 0.003937007874015748 (tenths of millimeters to inches). For positive
dimensions the output is pi/(selected dimension * conversion).

The graphics routine sets EBX to 1 before its branch. Orientations 1/3 select
dmPaperWidth; 0/2 select dmPaperLength. Thus Normal/180 use height, and either
90-degree orientation uses width. Retaining the EBX initialization is important
to interpreting the comparison correctly. The artifact builder permits only
normal-orientation artwork; the setup helper's other branches do not implement
rotated artwork placement.

`tools/recover_rotary_setup.py` checks the original graphics/UI binary hashes
and preserves relevant instruction bytes, disassembly, constants, and limits.
The binaries are read, never loaded or executed. This is static evidence, not a
new XP file capture. UI diameter/radius/circumference conversion, rotary drawing
surface and placement, and physical calibration still need verification.

`aurora_jobserver/color_vector_job.py` composes the existing independently
verified XP per-color vector body with the accepted zero-exposure/zero-power
carrier. It keeps the all-color hairline width rule, validates one opaque source
color per path, carries each palette power/speed/PPI, and omits disabled/zero-power
paths. If none remain it produces no job. Selected vector speeds above 15 ips
are rejected; unused legacy 100-ips palette entries are not motion commands.
Unknown RGB retains the XP White-process fallback. Sorting and pause behavior
reuse the established model and its existing combination holds.

Both new encoders **only emit marked normal-start offline drafts**. Normal
preparation and wire planning reject them. They have no option for production
output or Autostart. Production UseColors and Cylindrical holds are unchanged;
the desktop, printer defaults, driver, and active backend were not modified.

## Saved artwork review

`tools/prepare_priority_feature_reviews.py` reused the saved, validated native
intake for the physically accepted Aurora-Mixed-Test print 9ca241a9. It did not
submit a new host or XP print. New artifacts are at:

`runtime/rotary-offline-dev-20261022/priority-reviews-r1/`

- Bottom-up: raster-only draft, reversed rows, LL origin, original stored samples.
- Per-color vector: five original paths; black 1 ips/15%/1000 PPI, red
  2 ips/20%/750 PPI, blue 3 ips/25%/500 PPI; zero-power/exposure carrier.
- Rotary formula example: original raster samples retained, extra setup commands
  calculated using 7620/4572 DEVMODE units. Those flatbed dimensions exercise the
  formula only; they are **not an actual cylinder configuration**.

These are explicit synthetic review settings, not received operator selections
or recommended material settings. All six raw/CG files retain the draft marker,
have Autostart off, and fail ordinary preparation/delivery. Hashes and checks
are in `verification.json`. Physical-device I/O is false.

## Checks and next work

Two focused suites passed **25 + 15 = 40 tests**, no skips/failures:

- Seven new rotary tests, plus existing raster preferences and complete settings.
- Five new color-vector composition tests, existing XP color-vector comparisons
  (all five original files), and the measured carrier candidate's loopback tests.

This is not a new full-suite run. Logs are in
`runtime/rotary-offline-dev-20261022/{focused-tests-r1,color-vector-tests-r1}.log`.
Static evidence is in `static-r1/static-evidence.json`.

Bottom-up already has the normal 167-DPI pipeline and independent XP byte
matches; only its physical acceptance remains. No further XP bottom-up baseline
is needed. Per-color cut composition is now ready for the next integration and
supervised validation stage, but normal per-color printing is not enabled.
Per-color raster/mixed support still has the previously documented content and
mixed-boundary gaps. Rotary remains offline-only without a hardware test path.
No physical job, device probe, live-mode change, or XP network action occurred.
