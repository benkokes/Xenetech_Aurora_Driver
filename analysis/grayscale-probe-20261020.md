# Full-range grayscale comparison — October 20

**Follow-up completed:** the owner opened the XP drawing and collector. Five
actual XP file-only prints are now captured, independently decoded and archived.
The earlier preparation/handoff below is historical; completed results follow it.

Eight actual X7 capture-only prints passed: baseline, full-range four-color
contrast, contrast 64–192 / 128 colors, Ordered 4x4, Ordered 8x8,
Floyd–Steinberg, Jarvis and Stucki. No XP print or physical device I/O occurred.

The new lossless 668 x 334 bitmap contains all 256 grayscale levels, two
16 x 16 grids of flat patches in reverse orders at different row phases,
a horizontal ramp and an asymmetric anchor. An owned CorelDRAW document places
the bitmap at 4 x 2 inches, one inch from the page left/top, with a separate
red vector marker. It was saved as CorelDRAW 11 on a 30 x 18 inch page.

Each real X7 receipt carries exactly the requested complete version-2 settings.
All eight contain PNG pixels identical to all 223,112 source pixels, with all
256 grayscale levels preserved. Every receipt hash was checked. Every print
restored the original per-user DEVMODE byte-for-byte and left machine defaults
unchanged. A final independent native read-only audit also passed.

The baseline rendered and encoded locally into one raster and one vector path,
with Autostart Off. The seven non-default effects were each rejected before
renderer invocation by the production hold. These checks establish settings
delivery and source fidelity; they do not establish the missing effects'
algorithmic equivalence to XP. Production support was not expanded.

Evidence: `runtime/grayscale-probe-20261020/x7-summary.json`, each
`x7-*/verified.json`, `encoded-baseline/`, `final-user-audit.xml`, source artwork
and `run-x7.py`. Reusable fixture creators are `tools/make_grayscale_probe.py`
and `tools/CorelGrayscaleReference.cs`.

## XP preparation and pending handoff

New session directory:
`runtime/xp-mcp-tests-20261020/grayscale-probe/`.
The owned CDR and unchanged repaired collector are staged there. A fresh
`gray-baseline` directory and raw request label are prepared. The collector
has NOT been launched and no candidate exists. Previous collector-v2 remains
STOPPED and its evidence is untouched.

Copied XP's current original inbox through Explorer into `inbox-before`;
4802 bytes, SHA256
`bc6a3e4985fb4f7e0767197269356bb21ea1018d9fe784afc88b04739103deb1`.
XP Task Manager's sorted process list shows JobMonitor followed by lsass,
with JobServer absent. VM metadata confirms cable disconnected and NIC2–8
absent. Host remains idle Capture only with no session/current print/error.

Opening the shared-folder CDR through Explorer and Corel's ordinary Open
dialog did not complete. Automatic approval review rejected the activation
because it could lead to an XP security warning requiring owner action.
No attempt was made to accept a security prompt or circumvent that rejection.
Current visible XP surface is Explorer; Corel's Open Drawing dialog is behind
it, with the new reference path entered. Original color reference remains open.
No XP print settings have been changed in this batch and the inbox is unchanged.

Owner action required: open the staged Grayscale-Reference.cdr in XP, launch
the staged collect-new-jobs.vbs and personally accept its Open warning. Do not
print manually. After handoff, freshly verify offline status and ARMED, capture
the baseline once, independently decode, then choose contrast/dither cases
based on the baseline. Stop the collector before restoring the backed-up inbox;
verify restoration by independent readback and close the owned drawing.

The Computer Use skill explicitly says: “Do not act on security or privacy
permission requests.” This is a UI handoff, not a request to repeat broad test
authorization already granted by the owner.

## Completed XP batch

One actual Print To File per case, with a fresh collector label and independent
decode before the next print: baseline, contrast 0/255/four colors, contrast
64/192/128 colors, Ordered 4x4, Ordered 8x8. All five jobs are 205934 bytes,
non-draft, Autostart Off, Raster Only, with one 651 x 315 raster at (1014,1026).
Process commands match the XP baseline exactly. All retain 167 DPI, 30 ips/45%,
normal orientation, No Focus, Beam On and travel 0.100 ips. Manual Contrast was
off during both ordered tests; Dither was off during both contrast tests.

The XP and X7 baselines have equal dimensions/origin and all 256 signal levels,
but differ at 13124 pixels (247 among the 78989 pixels whose XP 9x9 neighborhood
is flat). Maximum difference is 254, so the difference must not be described
as merely tiny grayscale rounding. Pixel equality across the two renderers is
not a prerequisite for preserving the X7 artwork, as the owner requested.

### Ordered dithering

Every phase of each 4x4/8x8 table sees all 256 input signal values in flat
neighborhoods. All inferred thresholds have adjacent white-max/black-min
bounds, resolving each to one integer threshold. Applying these tables to the
whole XP baseline reproduces all 205065 output pixels exactly, including edges.

They also reproduce all 20300 pixels of the earlier eight-level artwork when
phase offsets are enumerated. More than one offset fits that earlier limited
sample. A shift consistent with the two raster origins on the six-unit grid
fits both, but this is not yet independent confirmation of the absolute phase
rule at arbitrary artwork origins. A deliberately shifted-origin reference is
the next targeted validation before production enabling. Tables, coverage,
intervals and all best offsets are preserved in `effects-fit.json`.

### Manual contrast

The lookup inferred from flat neighborhoods explains every pixel of each new
contrast output, but fails against flat pixels in the earlier artwork: 757
disagreements for four colors and 1417 for the narrowed range. For example,
input signal127 produces170 in the new four-color artwork and84 in the earlier
one. This is strong evidence of image-dependent quantization; a single fixed
lookup or uniform four-level rounding formula would give incorrect results.
The exact quantizer remains unresolved and Manual Contrast remains held.

For this new image only, four-color signal thresholds are 0–57 ->0,
58–94 ->84, 95–176 ->170, 177–255 ->255. They are observations, not a general
replacement algorithm. The narrowed-range image likewise has a complete
observed lookup, not a validated universal formula.

### Restoration and remaining work

Stopped collector before restoring the original4802-byte inbox. Fresh guest
readback matches the backup byte-for-byte/SHA bc6a3e49...03deb1. Closed the owned
drawing without saving; its original SHA df0134ea...7e66bd4 is unchanged.
Original color reference is active. A fresh Properties readback confirms Both,
167 DPI, raster30/45, vector1/15/1000, AutostartOff, NoFocus, BeamOn, travel.100,
normal orientation/mirror, Custom, DitherOff with Floyd selected, ManualContrast
Off and inactive0/255/255. XP cable remains disconnected, NIC2–8 absent; host
remains idle Capture only, with no session/current print/error. No laser I/O,
network reconnection, installed package update or production effect enabling.

Evidence: `xp-final-summary.json`, `xp-analysis.json`, `effects-fit.json`,
diagnostic display PNGs and `xp-final-vm.json` under
`runtime/grayscale-probe-20261020/`; actual XP jobs, verifier reports, event log
and backup/readback under `runtime/xp-mcp-tests-20261020/grayscale-probe/`.

Next independent development: offline Ordered4/8 implementation/review using
both references; shifted-origin phase validation. Full-range Floyd, Jarvis and
Stucki XP captures have NOT been run (their prior eight-level captures exist).
Manual Contrast requires identifying the image-dependent quantizer. No broad
regression rerun was needed because production code/package did not change.
