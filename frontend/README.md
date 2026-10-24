# Print document intake prototype

The first frontend component reads **Microsoft XPS and OpenXPS** documents and produces
an engraving image plus separate cutting paths. It builds and runs on this
Windows 10 host using its existing 64-bit .NET Framework installation. It does
not itself install a printer, submit to JobServer, or communicate with the laser.
A separate [capture queue](CAPTURE-PRINTER.md) is installed on this Windows 10 /
CorelDRAW X7 host. Synthetic Windows printing passed. The first CorelDRAW capture
was blank because its 30 by 18 inch document used Letter media; queue defaults
and legacy paper fields are now corrected. After restarting CorelDRAW, the
owner printed a 30 by 18 inch page with a one-inch square and `TEST` text.
The square remains a vector and is separated from the engraving text.

## Build and inspect a document

From the project directory in PowerShell:

```powershell
.\frontend\build.ps1
.\build\frontend\Aurora.XpsIntake.exe C:\path\artwork.xps runtime\artwork-preview
```

Choose a **new** output directory. With no cutting rule, all artwork remains in
the engraving preview. For an explicitly selected thin red cutting outline:

```powershell
.\build\frontend\Aurora.XpsIntake.exe C:\path\artwork.xps runtime\artwork-red-cuts --cut-color '#FF0000' --max-cut-width-mm 0.1 --dpi 167
```

The red/0.1 mm rule is a demonstration setting, not a recovered Xenetech default.
It must be matched to the application's artwork and the intended print settings.
A file printed through Microsoft XPS Document Writer can provide a real-world
test input. OpenXPS (`.oxps`) is normalized by Windows' native XPS API before WPF
reads it. Saving an XPS is
an interim diagnostic step; the finished product still requires normal direct
printing into its own Aurora printer queue.

Outputs:

- `source.bin`: immutable source snapshot, with SHA-256 in the manifest.
- `normalized.xps`: native conversion when the original document is OpenXPS.
- `page-001-exposure.bin`: cropped row-major exposure bytes (0 white, 255 black)
  with dimensions, offsets and checksum in the schema-2 manifest, when engraving
  exposure is nonempty. See [draft encoding](ARTWORK-DRAFTS.md).
- `document.json`: page size, raster size, drawing counts, cutting coordinates,
  explicit extraction settings, and reasons requiring review.
- `page-001-engraving.png`: white-backed color rendering with accepted cutting
  strokes removed; fills and other artwork remain. This is not yet calibrated
  grayscale exposure data for the Aurora.
- `page-001-cuts.svg`: page-sized cutting preview with millimeter coordinates.
  SVG uses a visible red preview stroke; the manifest retains the source width.

Coordinates start at the page's upper left, with X right and Y down. No artwork
is centered, fitted to the bed, rotated, or translated automatically. Curves are
flattened after page transforms with a default absolute tolerance of 0.01 mm.
Each page is kept separately. The manifest says `offline_preview_only` and is
written only after all pages succeed. If parsing fails, an incomplete directory
may remain for diagnosis; it is not a ready job.

Preview DPI uses normal document units. The old driver's nominal 167 setting
also uses a six-unit coordinate factor; that rounding distinction needs
calibration before producing new jobs. See the [static coordinate evidence](../analysis/driver-coordinate-rules.md).

## Bounded previews at the original resolutions

The offline document-grid renderer now accepts 50–1200 DPI and an explicit
`--tiled-raster on` option. This locates visible engraving with bounded tiles,
then renders its pixel-aligned crop. A full 30 × 18 inch, 1200-DPI page would
otherwise allocate a 36,000 × 21,600 BGRA image, over 3 GB. The final engraving
region retains the existing 50-megapixel limit; excessive artwork is rejected.

```powershell
python -m tools.preview_resolutions SOURCE.xps runtime/NEW-resolution-review
```

This produces offline previews for 50, 100, 167, 200, 250, 333, 500, 1000 and
1200 DPI, from a single immutable source snapshot. `resolution-review.json`
records each surface, crop origin, exposure hash and vector-path count.
`--resolutions 333 500` selects a subset. Output directories must be new.

For tiled previews, page `pixel_width`/`pixel_height` describe the full logical
surface; the PNG is the visible crop at `preview_x_pixels`/`preview_y_pixels`.
Exposure offsets still use the original page coordinates. Cutting paths remain
in page millimeters. Ordinary full-page outputs have zero preview offsets.

These are **document-grid previews**, without the XP/Corel placement fit. They
do not establish the original driver's output, enable additional DPI choices in
the native printer, encode a JBS or contact the laser. Tiling is rejected with
the existing live Corel profile. Controlled XP captures are required before
extending that path; 1200 also has separate legacy coordinate arithmetic.

All 27 native intake tests pass, including sample-exact comparison of full
versus tiled rendering at 50/167/500 DPI, preserved page origins, full-bed
1200-DPI rendering with vector separation, and rejecting an excessive engraving
region. The existing 115 Python tests pass against the rebuilt intake.

## Experimental per-color offline review (October 20)

The separate build at `build/frontend-semantic-color-20261019` supports source
brush coverage before RGB blending. Actual Corel X7 fill edges reconstruct
exactly. It keeps schema-3 color-review manifests outside the production path.
Ordinary rendering remains byte-identical to the installed reader on the two
saved host reference documents; the installed reader was not replaced.

`python -m tools.review_color_job SOURCE.oxps NEW-DIRECTORY --intake-executable build/frontend-semantic-color-20261019/Aurora.XpsIntake.exe`
uses only complete job-attached settings and exports marked offline drafts.
It has no spool submission or equipment endpoint. Scalar-only captures,
unverified settings and the multiple-color raster/vector boundary are held.
White/bitmap/gradient/transparency classification remains unverified.
See [evidence and current limits](../analysis/semantic-color-coverage-20261020.md).

Current checks: 198 Python tests passed, followed by one added mixed-host test;
36 native tests and 64 small synthetic native compositions passed. Earlier
test counts elsewhere in this document describe historical stages.

## Geometry and rendering behavior

WPF loads the printed XPS document and renders its fonts, paths, image brushes,
images, fills, transformations, clips, and opacity. The visual and drawing trees
are retained together. A cutting stroke must match an explicit opaque solid
color and a maximum physical width. Nonuniform scaling uses the largest scale
factor when deciding whether a stroke is thin enough. Transparent/masked/dashed
matching strokes and matching strokes crossing a clip/page boundary are retained
in the engraving preview and listed for review, rather than exported as an
unclipped continuous cut. Other stroke colors and wider strokes remain rendered.
An object's fill stays in the engraving image when its outline is extracted.
Text is rendered; it is not inferred to be a cutting path from its color.

The reader bounds input to 64 MiB, documents to 100 pages and full-page raster
output to 50 megapixels. Explicit tiled previews instead bound the final visible
engraving region to 50 megapixels. It uses Windows' document decoder; this is not a
general-purpose sandbox or a full XPS conformance validator. Process real
application output to check what the application's print pipeline preserves:
if the application prints a flattened image, the original cutting paths cannot
be recovered from that image by this stage.

## Verification

```powershell
.\frontend\build.ps1 -Test
```

Twenty-seven checks cover physical coordinates; nested scale, rotation, translation
and mirroring; geometry transforms; stroke width/color rules; Bezier flattening;
clipping; transparency; dashes; fills; unstroked gaps; exact pixel comparison of
an original visual against the reconstructed drawing; a two-page XPS write/read
round trip with paths, glyphs and an embedded image; DPI rounding; invalid input;
limits and overwrite rejection. Native XPS/OpenXPS conversion preserves the
fixture's rendered pixels and cutting paths. Generated test artwork is under ignored
`runtime/frontend-tests`.

Blank pages with neither nonwhite engraving pixels nor extracted cuts are flagged
in `review_reasons`. Cutting-only pages are not mislabeled blank.

These checks establish the offline XPS stage. A separate actual CorelDRAW X7
capture also passed with correct page/square dimensions and layer separation;
an offline JBS draft encoder is now implemented. The first XP comparison confirms
process settings and a 1002-unit one-inch square at nominal 167 DPI. The explicit
XP grid and optional aliased glyph-outline mode are documented in
[ARTWORK-DRAFTS.md](ARTWORK-DRAFTS.md). Placement on further artwork, exact glyph rendering and
physical calibration remain. An explicit Corel compatibility profile matches
the full vector command section at both 100 and 167 DPI; generic geometry
profiles remain separate. The Python suite now has 80 passing tests, including LPR
capture, draft encoding and reference comparison checks.

## Windows printer integration

The owner requires XP-style printing: set laser options in printer Properties,
then click Print in CorelDRAW. JobServer handles delivery automatically, without
a second Send step. See [the direct-print workflow](DIRECT-PRINT.md).
The intended path is:

```text
Graphics application -> Aurora Windows printer queue -> print document + settings
                    -> page geometry and engraving image -> calibrated JBS encoder
                    -> JobServer queue -> automatic Ethernet delivery
```

Microsoft's newer [virtual printer API](https://learn.microsoft.com/en-us/uwp/api/windows.graphics.printing.workflow.printworkflowvirtualprintersession)
starts at Windows 11 24H2, build 26100. The [virtual printer design guide](https://learn.microsoft.com/en-us/windows-hardware/drivers/devapps/print-support-app-v4-design-guide)
describes application registration, background document delivery, and print
preferences. Its preferred input is OpenXPS or PostScript. That registration
does not by itself provide an Aurora renderer. Native OpenXPS conversion is now
implemented and tested on this host. This host has .NET 8
runtimes but no .NET SDK, Windows SDK/WDK, or Visual Studio build toolchain found
at the standard locations. The prototype uses the older Framework compiler
already present and does not require changing the system.

CorelDRAW X7 on Windows 10 build 19045 is the confirmed development target. The
[local capture printer](CAPTURE-PRINTER.md) uses the installed Microsoft driver
and a loopback LPR receiver instead of the 24H2-only registration API. Remaining
work includes broader artwork and physical placement validation, the CorelDRAW
capture check for the newly installed [laser Properties printer](PRINTER-PACKAGE.md),
and Windows 11 installation validation. The first constrained
[generated artwork test](../analysis/generated-calibration-live-20261017.md)
completed, with the owner reporting a one-inch square. The subsequent
[45% raster-power test](../analysis/power45-calibration-live-20261018.md)
has a completed controller report and an owner-accepted physical result.

Windows APIs used here: [XPS document loading](https://learn.microsoft.com/en-us/dotnet/api/system.windows.xps.packaging.xpsdocument.getfixeddocumentsequence),
[visual drawing access](https://learn.microsoft.com/en-us/dotnet/api/system.windows.media.visualtreehelper.getdrawing),
and [geometry flattening](https://learn.microsoft.com/en-us/dotnet/api/system.windows.media.geometry.getflattenedpathgeometry).
