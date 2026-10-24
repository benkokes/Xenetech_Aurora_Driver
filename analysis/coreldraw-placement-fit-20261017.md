# CorelDRAW placement fit from the 100-DPI comparison

The second raw reference is preserved at
`captures/xp-corel11-100dpi-20261017/Default.jbs`, 2,444 bytes, SHA-256
`885a552e9e11efb06c8fd262c66d9ca13b572027896a659067f6a5fd6ad8a1e7`.
All 24 raster row trailers validate. Header fields are 100/100, flags 0x41;
spot size is 10.000. Raster is 84 x 24 at (1000,740), pixel SHA-256
`b732dcb1590613d998ddfeea02243ff66254600b3f3204706517d9f5e3e65c71`.
The square is (900,1220)..(1900,2220), with the same requested settings and
normalstart as the earlier nominal-167 reference.

The source X7 OpenXPS package's `Metadata/Job_PT.xml` explicitly records
ResolutionX=ResolutionY=600. This permits testing a specific print-coordinate
model instead of choosing a constant job-unit shift. For captured source
coordinate c in inches, reconstruct target pixels using:

```text
p = round((c + 1/600) * target_dpi) - 1 - center_adjustment
job_coordinate = p * pitch
```

Center adjustment is (0,0) at 100 DPI, and (5,3) at 167. Pitch is 10 and 6
respectively. The latter adjustment corresponds to half the driver's nominal
5010 x 3006 versus allocated 5000 x 3000 surface difference. The one-pixel
terms and rounding also explain the X7 captured rectangle coordinates relative
to the saved CDR's page-relative geometry. This is an empirical Corel X7/11
reference fit, not proof of a universal Corel behavior or a controller offset.

The explicit `coreldraw-xp-draft` intake/encoder profile uses this model for
vectors and the corresponding continuous translation for raster drawing.
Both target DPIs reproduce the entire XP vector command section byte for byte:

| DPI | Top-left | Opposite corner | Span | Vector bytes equal |
| ---: | --- | --- | --- | --- |
| 100 | 900,1220 | 1900,2220 | 1000 x 1000 | yes |
| 167 | 876,1212 | 1878,2214 | 1002 x 1002 | yes |

This includes settings, path order/closure and final PU/origin commands. It
does not mean entire files match: job titles/draft markers and raster samples
still differ. The generated drafts retain the blocking marker and normalstart.

The new profile requires a measured, uniform 600-DPI source PrintTicket,
exactly a 30 x 18 inch page, and target 100 or 167 DPI. It rejects unsupported
source/target resolution, page size, missing provenance and transformed vector
points outside the legacy surface. A padded render detects engraving clipped
by the compatibility surface; a review flag blocks encoding instead of silently
dropping those samples. Other grid profiles and ordinary intake keep their
original behavior. SVG/manifest cutting geometry remains source page geometry;
the compatibility metadata describes the controller mapping.

Current checked intakes are `runtime/coreldraw-compat-{100,167}-checked`.
Earlier equivalent intakes without the new fringe check remain preserved;
their exposure bytes match the checked intakes exactly, with no review flags.
Drafts are `runtime/coreldraw-compat-jbs-{100,167}`. Independent comparisons are
`runtime/coreldraw-compat-comparison-{100,167}/comparison.json`.

At 100 DPI the candidate raster is 83 x 24 at (1000,730); at 167 it is 140 x 41
at (972,720). Remaining one-sample ink-bound differences and character-edge
differences are visible in `runtime/coreldraw-compat-review/raster-comparison.png`.
Samples are shown at 4x magnification, with relative origin differences retained.
XP and X7 already report slightly different Arial text metrics. The explicit
outline-aliased renderer is not XP's hinted glyph rasterizer. The owner chose
to preserve current X7 artwork appearance. No padding, extra offset, or forced
pixel identity is used.

Raw/compressed draft SHA-256 values:

- 100 DPI raw, 2,446 bytes:
  `dd9ed5cdb232b4b381d3fa00ccf235faa81b48a8050782db2d756a851346f85a`.
- 100 DPI CG, 699 bytes:
  `edfa70b648740ae0ee3ebf2aecbf7342ecaf750d2acbb4cc004ca714862eec64`.
- 167 DPI raw, 6,225 bytes:
  `dc018c29fcbfc9df3c2bdaa5e25fdc2e275124e569b6547fa7ee5d55e04d14ab`.
- 167 DPI CG, 965 bytes:
  `0bbf1163d38ddc453bb34e1c5bd4ab8391881c0b0351581c71f0680a2b208a31`.

Validation passes 75 Python tests and 24 frontend checks. Tests compare all four
actual captured corners at both resolutions, encoded raster DPI/pitch and draft
rejection, wrong source/page provenance, actual XML ticket resolution including
nonstandard namespace prefixes, and clipping of artwork at the old surface
edge. Rebuilt checked intakes for the actual source agree with the earlier
generated exposure planes. No physical transfer occurred during this placement
comparison. A later constrained [physical calibration test](generated-calibration-live-20261017.md)
completed, with the owner reporting a one-inch square and too-light raster text.
Current Python validation is 80 tests. More shapes, rounding-boundary cases,
precise scale/placement and the final Windows printer workflow still require validation.
