# Development history — Xenetech Aurora print support

These are chronological engineering notes. Some entries describe earlier
versions and are superseded by later work. For installation and everyday use,
start with the current [user README](README.md).

Reverse-engineering workspace for replacing an XP-era Xenetech Aurora laser
printer driver while retaining direct printing from artwork applications.

October 23 update: the owner accepted per-color raster/mixed output (three
raster colors and two vector colors). Normal pipeline 4 supports these modes
at 167 DPI for opaque fills/text, plus the previously accepted per-color Vector
Only and global bottom-up modes. Standalone Windows x64 preview packaging is
implemented in `packaging/`; see [validation and remaining release work](analysis/per-color-raster-mixed-and-package-20261023.md).
This host is Windows 10; actual Windows 11 and clean-machine installation remain
unvalidated. The following chronological status text includes earlier stages.
Normal desktop startup now enables printing for new submissions, as requested
by the owner. Old captures remain held. Use `--capture-only` for offline startup;
the per-job Autostart option is unchanged.

Current status: independent raster conversion matches the confirmed XP reference
job byte for byte. A persistent JobServer prototype now provides a desktop queue,
inbox watcher, preparation, export, and history. Experimental Ethernet delivery
is implemented and tested against a local controller simulator, including the
captured job's complete transfer. The replacement has now completed an approved
physical raster job: the owner confirms it looks the same as the XP test, and
the entire transmitted main-channel stream matches XP byte for byte. A Windows
11 printer frontend now has an XPS/OpenXPS intake prototype that separates
explicitly selected cutting strokes from the engraving image. A preview-only
printer queue on this Windows 10 host has passed a synthetic print through a
loopback receiver. CorelDRAW X7 also printed a 30 by 18 inch page with an exact
one-inch vector square and engraving text, separated successfully by the intake.
An offline encoder now produces marked, non-deliverable Aurora drafts with
explicit settings. A constrained newly generated square-and-TEST job has now
passed physical testing; the owner accepted the 45% raster-power result.
Broader artwork and placement validation remain. The required final workflow
matches XP: CorelDRAW Print submits the job and JobServer delivers it automatically.
The automatic capture-to-encoder-to-dispatch path now passes local integration
tests. The signed native printer **Aurora JobServer (Test Capture)** is now
installed. Windows confirms its 30 x 18 inch page and all laser Properties
options. A real CorelDRAW print through this new queue now carries all laser
settings and converts to the accepted test's exact artwork and commands.
The [native print check](analysis/native-coreldraw-print-20261018.md) also passed
automatic delivery to the loopback simulator. A subsequent
[integrated live print](analysis/integrated-print-live-20261018.md) completed
from CorelDRAW Print through automatic JobServer delivery to the Aurora; the
owner pressed the machine's Start button and accepted the finished engraving.
The one-job host stopped and capture-only mode was restored. Routine startup
packaging has now gained a normal [JobServer window](JOBSERVER.md) with connection
checks, print history, capture-only/live controls and optional sign-in startup.
The [new window's live print test](analysis/desktop-jobserver-20261018.md) also
passed: one CorelDRAW print delivered once, both parts looked right, and the
owner restored capture-only mode.
Windows 11 installation and broader artwork validation remain.

The native printer now opens a [direct Properties window](frontend/PRINTER-PROPERTIES.md)
with raster and vector controls on its first screen. Cancel returns directly to
CorelDRAW Print; a captured job confirms OK saves changed power selections into
the job's settings and encoded commands. This UI update remains capture-only.

Double-click `launch-jobserver.cmd` to open the normal window. It starts in
capture-only mode. Once laser printing is enabled for a prepared session, new
CorelDRAW prints deliver automatically; previous captures are never replayed.
The separate `launch-jobserver-tools.cmd` retains the manual diagnostic queue.

Work on [matching the original XP Preferences](analysis/xp-preferences-parity.md)
now includes the complete visible controls on the first three tabs, plus full
material/color presets and immutable per-job settings. The installed r9 update
(0.5.1.0) preserves the 167-DPI default and passes native Windows DEVMODE
roundtrips. New active options whose output is unverified hold the job before
rendering/upload; UI completeness does not establish encoder parity. The
[r8 report](analysis/complete-preferences-20261018.md) records the behavior limits
and checks. The owner confirmed all three pages. An
[OK-button save repair](analysis/properties-ok-save-repair-20261018.md) is installed;
the owner confirms OK returns to Print without error. A real 46/16 Corel print
preserves the complete snapshot and reproduces the reference artwork in offline
encoding; JobServer remains Capture only.
The [three XP output modes](analysis/output-mode-results-20261018.md) now match
the encoder byte for byte when given the captured pixels and paths. Raster Only
is enabled and passes the complete loopback pipeline. Vector Only at 167 DPI
now uses the physically accepted CG carrier: zero raster exposure/power,
followed by the cutting paths. Normal cut selection uses hairline width,
regardless of color. A Vector Only print without eligible hairlines shows
“Nothing to cut — not sent” and does not block a corrected print. See the
[Vector Only integration](analysis/vector-only-production-20261022.md).
The actual
CorelDRAW Raster Only capture also passed: its TEST pixels, origin and raster
settings match the accepted X7 reference, with no vector cutting commands.
The owner restored Both afterward; JobServer remains Capture only.
Bounded offline rendering previews all nine original resolutions, 50–1200 DPI.
Per-color, orientation, bitmap and focus behavior still need XP comparisons.
New [offline Preferences tools](analysis/offline-preferences-development-20261018.md)
compare pure/mixed output modes, raw/compressed pixels, placement and process
commands. The owner completed the three asymmetric grayscale XP references.
[Invert and Bottom-Up](analysis/raster-preferences-results-20261019.md) now
match the original raw jobs byte for byte and are implemented at 167 DPI.
Native conversion and loopback checks pass, along with all 169 Python tests.
The existing Properties controls carry these options; no reinstall is needed.
JobServer remains Capture only and these options still need physical validation.
Five actual XP color references now establish the sampled vector palette,
sorting, disabled-color and pause behavior. The separate
[offline color-vector model](analysis/color-vector-model-results-20261019.md)
reproduces all five complete files byte for byte; all 176 tests pass.
Per-color printing remains held while colored raster processing and native
extraction of multiple cut colors are developed.
The [raster-color model and experimental RGB intake](analysis/color-raster-model-results-20261019.md)
now reproduce four independent XP flat-fill raster jobs as marked drafts.
All 184 Python tests and 31 native frontend tests pass. The separate review
reader preserves RGB and multiple cut colors; its schema cannot enter normal
print encoding. A real X7 colored-fill capture and broader bitmap behavior
remain to be checked before enabling per-color printing.
Two [actual host color prints](analysis/host-color-capture-results-20261019.md)
have now been captured autonomously. Vector geometry/colors match XP. The filled
color print exposes blended-edge loss in exact RGB separation; retaining brush
identity through rendering is the next fix. Per-color printing remains held.
An expanded overnight check also preserves 128 native full-settings snapshots,
independently verifies them in the Python backend, and passes a 3,600-case
offline raster campaign. Additional [original Preferences evidence](analysis/preferences-static-evidence-20261018.md)
recovers the rubber-stamp dialog resources and maps inversion, bottom-up and
beam-mode flags. These checks do not activate unverified engraving options.
Further [stamp analysis](analysis/rubber-stamp-static-model-20261019.md) recovers
five built-in fallback profiles and the command builder, while preserving its
unverified status. Imported raw/CG jobs requiring the original converter's
unimplemented stamp preprocessing now stop before preparation or delivery.

The first saved job has been decoded into two raster previews and 23 vector
polylines. Both raster payloads decompress exactly to their originals, and the
new converter reproduces the complete 92,759-byte JobServer output.

- [Initial findings](analysis/initial-findings.md): architecture, evidence, hashes,
  recovered command templates, and open questions.
- [Working XP installation](analysis/xp-capture-14978-28204.md): installed driver
  matches, confirmed folders, connection settings, and the next files needed.
- [First reference job](analysis/reference-job-findings.md): validated raster
  layout, vector preview, and database inspection.
- [Independent raster conversion](analysis/raster-codec.md): recovered packing
  and compression, exact reference comparison, tests, and supported scope.
- [JobServer prototype](JOBSERVER.md): launch instructions, persistent queue,
  supported input, and the VirtualBox protocol-capture findings.
- [XP-style direct-print workflow](frontend/DIRECT-PRINT.md): printer settings,
  automatic JobServer dispatch, implemented backend and remaining Windows integration.
- [Native printer package](frontend/PRINTER-PACKAGE.md): job-attached laser
  settings, full local pipeline tests, native installation and capture validation.
- [Direct printer Properties](frontend/PRINTER-PROPERTIES.md): raster and vector
  controls on the first settings screen, native per-job save and Cancel behavior.
- [Captured Ethernet job session](analysis/ethernet-session-20261017.md): startup,
  full transfer reconstruction, controller replies, and the original token warning.
- [First live replacement test](analysis/live-validation-20261017.md): verified
  physical result, startup fixes, preserved evidence, and current limits.
- [Print document intake prototype](frontend/README.md): XPS page rendering,
  separate cutting paths, millimeter coordinates, and 24 frontend checks.
- [Artwork-to-Aurora drafts](frontend/ARTWORK-DRAFTS.md): native raster grid,
  requested process settings, raw/CG generation, draft checks and calibration limits.
- [CorelDRAW 11 reference comparison](analysis/corel11-comparison-20261017.md):
  exact vector-command matches at 100/167 DPI with the explicit Corel profile,
  and the remaining glyph-rendering differences.
- [Corel placement compatibility](analysis/coreldraw-placement-fit-20261017.md):
  the 100-DPI evidence, matched native vector commands, profile constraints,
  raster comparison and current validation.
- [Reviewed physical calibration candidate](frontend/CALIBRATION-TEST.md):
  accepted X7 lettering, the constrained one-job staging path, exact loopback
  validation, and measurements still needed before production use.
- [Generated artwork physical result](analysis/generated-calibration-live-20261017.md):
  completed square-and-TEST job, owner-reported one-inch square, and the staged
  45% raster-power revision.
- [45% raster-power test](analysis/power45-calibration-live-20261018.md):
  one upload, manual Start, controller completion and owner-accepted result.
- [Windows / CorelDRAW capture printer](frontend/CAPTURE-PRINTER.md): installed
  preview-only queue, receiver, and synthetic Windows print result.
- [CorelDRAW media correction](analysis/coreldraw-capture-20261017.md): first blank
  capture, corrected legacy paper settings, and successful one-inch square/text print.
- [XP capture instructions](capture/README.md): obtain controlled reference jobs
  without sending them to the laser.
- [XP diagnostic collector](capture/collect-xp-info.cmd): read settings and copy
  the installed driver DLLs for comparison.
- `tools/inspect_pe.py` and `tools/disassemble_pe.py`: static analysis utilities.
- `tools/inspect_job.py`, `tools/preview_vectors.py`, and `tools/dump_dbi.py`:
  offline capture inspection and preview utilities.
- `tools/raster_codec.py`, `tools/convert_job.py`, and
  `tools/inspect_converted_job.py`: independent raster conversion and validation.

Local vendor installers, extracted binaries, generated disassembly, captures,
and downloaded dependencies are excluded from Git. The source network share is
kept unchanged.
