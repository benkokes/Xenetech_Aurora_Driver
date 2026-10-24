# Invert Raster Output and Bottom-Up: XP reference results

The owner completed three offline CorelDRAW 11 prints of the asymmetric bitmap
on October 19. The laser stayed off, XP stayed disconnected and XP JobServer
stayed closed for these file captures. The installed host Properties package
remains r9 (0.5.1.0); no printer defaults or native package were changed.

## Preserved references

All folders are under `captures/xp-bitmap-preferences-20261019`. Original
collector labels and files are preserved. The first folder was labeled baseline,
but the owner explicitly corrected it to **Invert On** before a true baseline
was recaptured. The correction is recorded against its job hash in
`runtime/xp-bitmap-preferences-20261019/capture-label-correction-7794-27967.json`.

| Actual setting | Collector folder | Default.jbs SHA-256 |
|---|---|---|
| Both options off | bitmap-baseline-13084-7847 | f2407eb8860a8af234a19af28a2d27a03f2f900aaf2ebe115c415a37c6714eea |
| Invert On, Bottom-Up off | bitmap-baseline-7794-27967 | 1a5545eb41a1768bffea28635d6dbd317d96ddb394a78f7e57d3d37cd19b3417 |
| Invert off, Bottom-Up On | bitmap-bottom-up-26829-22394 | 3ccdecb7a566c61485cb37b8749ff05ff86bd1c3f6f562f035879784a23e0745 |

Each job is 20,819 bytes with one 145 × 140 raw picture, 167/167 DPI fields,
6-mil pitch, raster speed 30000 native (30 ips), 45% power, no vector paths and
Autostart off. Cropping is retained; inversion does not expand to the full bed
or the bitmap's white outer margins.

## Observed behavior

- Invert changes every one of the 20,300 picture samples to `255 - original`.
  Dimensions, origin (1068,1332), PICT-UL label and all text commands agree.
- Bottom-Up reverses the picture's vertical row order, retaining each row's
  left-to-right logical order. It changes PICT-UL to PICT-LL and the origin to
  (1068,2166). The difference is `(height-1) × pitch = 139 × 6 = 834` in Y.
- Speed, power, resolution and the final pen-up return remain unchanged.

The independent decoder's immutable reports and previews are
`runtime/xp-bitmap-preferences-20261019/baseline-vs-invert/` and
`baseline-vs-bottom-up/`.

## Backend implementation

The existing per-print native snapshot already carries both booleans. The
encoder now accepts them, changes only the raster samples/start/origin label,
and leaves vector geometry and process settings unchanged. Row serpentine
alternation is applied after selecting the emitted row; using the old source
row parity would be wrong for even-height images. Inversion operates within
the existing captured engraving rectangle, including its internal blank gaps.

The complete settings route permits these two options at **167 DPI only**.
At other resolutions they remain held before rendering. Existing orientation,
mirror, color, dither, stamp and focus holds remain in place. Legacy snapshots
without the complete preference block preserve their ordinary output.

Both options compose as complement plus reversed row order. Their combined
case passes synthetic and native-pipeline checks, but no separate combined XP
capture or physical test was run. Individual option jobs and the baseline match
the original XP raw job **byte for byte**, when supplied the captured baseline
pixels/placement. This establishes encoding, not identical X7/XP rendering.
X7 artwork appearance remains the owner's accepted rendering choice.

## Validation and loaded state

- Seven new tests cover the three complete XP byte matches, simultaneous flags,
  immutable scenes, unchanged vectors, odd/even/single-row origin handling,
  other-resolution holds, draft rejection, native conversion and once-only
  dispatch to a controller bound exclusively to loopback.
- Focused related suite: **24 tests passed** in 9.608 seconds.
- Full regression: **169 tests passed** in 51.220 seconds, with no skips.
  Log: `runtime/xp-bitmap-preferences-20261019/raster-controls-regression.log`.
- Revalidated the 128 saved native snapshot cases against the new backend rules:
  256 native-stage reads and 256 full-XPS scope reads passed. This reused the
  preserved provider output; no new printer changes were made. Report:
  `runtime/xp-bitmap-preferences-20261019/native-settings-policy-review/verification.json`.
- Reloaded the verified idle host JobServer. Listener PID 36 at 127.0.0.1:515,
  mode Capture only, session/current print null, no error. No backlog replay,
  laser connection, print submission or physical engraving was performed.

The owner was instructed to restore Bottom-Up off and Both Raster and Vector
after collection. Do not infer a physical readiness authorization from these
offline captures. A future hardware test of the new raster controls requires
the owner's prepared session.
