# Vector Only candidate — October 21

The latest owner print, fc02bdb3-10a9-4972-bb2c-9f6f7ea360da, reached desktop
session dd689b2e-8ebe-4ab0-a1b1-a109983d2aff at 08:00:34 Pacific. Its settings
selected Vector Only, which production still holds before conversion or send.
No job was accepted into that session's queue. The earlier stopped-delivery
marker has been cleared using the owner's verified observation; it is not the
cause of this new hold. JobServer returned to Capture only after the hold.

The owner clarified that XP selects cuts by hairline width, regardless of
color. Black hairline lines and curves are ordinary vector work. The original
prototype's red-only classification is not full XP parity.

Added explicit offline intake options `--cut-color any` and
`--cut-paths-only on`. The latter captures paths without rasterizing fills,
text, or bitmaps, retaining clipping/transparency/dash review checks. Candidate
hairline limit is 0.13229266666666667 mm: the observed X7 hairline output of
0.5 DIP plus numeric tolerance. This is an observed X7 print threshold, not a
claim that all applications encode hairlines with the same width. A 0.5-point
outline (2/3 DIP) is excluded. Effective width includes ancestor scaling.

Built the candidate converter separately under
runtime/vector-only-dev-20261021/frontend. The production converter in
build/frontend was not replaced, and production Vector Only remains held.

Actual latest X7 source yielded 12 eligible paths. Derived source copies with
black and blue outlines produced exactly the same candidate bytes as red.
Thicker outlines and filled-only variants produced Nothing to cut and no JBS
file. The original source was preserved. These are saved-source offline
transformations, not new X7 print submissions or XP tests. Evidence:
classification-validation.json and per-case review folders under that runtime.

The native vector-only wire envelope is still unverified. Instead of guessing
its jobtype, the candidate encoder uses the established CG mixed-job envelope:
one 1x1 zero-exposure picture with explicit raster power 0%, followed by the
requested vector paths and their original speed/power/PPI. It discards all
source raster artwork. Autostart is forced off for this measurement. This
requires a physical validation before production activation. Ordinary candidate
exports carry the draft marker and cannot be sent. The explicit measurement
stager can create an unmarked reviewed file, but never sends it.

38 native frontend tests passed, including color-independent hairlines,
thick outlines, transformed widths, transparency, and original behavior.
Three candidate Python tests passed: byte-level blank/zero-power carrier,
scene immutability and invalid inputs, and one exact-wire upload to a loopback
simulator with a cleared test-only guard. The initial candidate unit assertion
used the wrong diagnostic dictionary key (`paths` versus `vector_paths`); it
was corrected and all three passed. No physical equipment was contacted.

Prepared one familiar square-and-circle measurement from the saved normal X7
sheet. Queue runtime/vector-only-dev-20261021/calibration-measurement/
measurement-queue has one READY job caf37d9d-bb79-4e02-965e-e19326690d8b.
Title VectorOnly167Test; SHA256
05b70c64d8aa7e24897a4df38a5d7fa615a779d13d056d8e4dd4ec730dc5c065.
Autostart off, vector1ips/15%/1000PPI,167DPI, raster carrier0%/zero exposure.
Square bounds1062,2886..2064,3888 units; circle4002,3126..4506,3630 units.
Upload1658 bytes. Material guide x0.9–4.7in, y2.7–4.1in from bed left/top;
the zero-power carrier also moves to0,0. It has NOT been sent. Wait for fresh
operator readiness, keep XP offline/JobServer closed and host Capture only,
then send this one candidate once using the shared guard, without retries.

After successful physical validation and owner inspection, integrate this
route and a durable Nothing to cut result into normal Print/desktop history,
enable the width-based classification in production, and verify the installed
normal print path. Do not claim these production steps already completed.
