# Combined real-world sheet — prepared October 20

Owner requested real-world testing with several checks combined in one run.
Prepared one fixed native-grid calibration sheet, title AuroraSheet167P45:
grayscale/Ordered4/Ordered8 ramps and five-step patches, raster text/fine lines,
one1002x1002-unit design-inch vector square and a500-unit diameter circle.
The circle uses64 segments, closed once. Preview red lines are vector marks.

Raster167DPI/30ips45%, vector1ips15%1000PPI, NoFocus, normal orientation,
AutostartOff. Actual exposure668x501 at1002,1002 native units; extent is about
1.0–5.01in fromleft and1.0–4.01in fromtop. Recommended stock covers
x0.9–5.3in/y0.9–4.3in: a4.5x3.5in piece appropriately positioned. Operator must
prepare material and focus and explicitly confirm readiness before one send.
AutostartOff is not relied on to make an unprepared machine safe.

Source builder tools/stage_physical_sheet.py creates only this new artwork;
it has no arbitrary draft input/release or equipment connection option. It
stages an unmarked supervised calibration candidate, not a production feature
release. Dither conversion uses the implemented explicit-phase algorithm.
Production DitherBitmaps remains held. This evaluates encoder output, marking,
geometry and transport; it is not a new Corel application print or Win11 install
test. Existing Corel baseline end-to-end physical validation remains separate.

CandidateCG32081bytes SHA256
52826924f65207b89d94ec44d4f8217908b20276346b996c3d74bcd370b15d3b.
Raw337114bytes SHA256
304190f49319ce5c0397c055432d728b0d88794e4630b31b124ba12a992c8e45.

Independent decode validates dimensions, position, emitted settings, closed
paths, raw/CG pixel identity and unchanged samples outside the two processed
panel rectangles. One exact candidate completed against the local127.0.0.1
controller simulator, including the known warning. Saved main TX32427bytes
matches the wire plan exactly; one upload, no retries. Simulated job time is a
fixture, not a duration estimate. Two audit assertions used wrong conventions
(queue state prepared vs ready; wrapped upload vs bareCG); corrected using the
already-prepared queue and then the completed transcript. No simulation upload
was repeated to repair those assertions. Physical laser was not contacted.

Runtime package runtime/realworld-sheet-20261020:
- staged/preview.png, physical-sheet-plan.json and measurements-template.json.
- staged/sheet.raw.jbs and sheet.cg.jbs; original/processed exposure planes.
- ready-for-operator.json, simulator-main-tx.bin and simulator-queue transcripts.
- physical-queue has ONE ready job3d22cf85-c0d5-48c1-be46-cc2ffd9568cb.

Physical delivery is pending readiness, not yet performed. Host recorded mode
Captureonly, nullsession/currentprint/error. XP cable disconnected/NIC2–8none;
XP watcherSTOPPED. No installed package/preferences/defaults change.

After readiness: freshly verify candidate hash, unique ready queue job, host
Captureonly and XP offline, then use the existing single-job sender and shared
device guard. Send exactly once; do not automatically retry an uncertain upload.
Expected manualStart; ask owner about all three panels, text/lines, square width
and height separately and circle shape/diameter. Record results against the hash.

## Physical delivery completed

The owner replied “Ready—send one combined sheet,” confirming the stated
material area, focus and settings. Fresh VM metadata showed XP's cable still
disconnected; host recorded idle Capture only; the isolated queue had exactly
the reviewed ready job and hash. The one-shot sender retained its standard
shared device guard and refused repeat execution. No reset or retry was used.

One connection attempt and one upload to 192.168.1.244 completed. The owner
reported “Engraving—I pressed Start.” Controller end code0, job time59.064s,
with only the familiar set_xyup_feed token warning. The full32427-byte main TX
matches the staged wire plan exactly, SHA256
e7e23b9ec8b387383dacbf6313e9372d47f96e6ca3a1cdec2d8cfc792d870214.
Main RX941bytes SHA256
83b1005e05074d8f8e04b4050ea94f248b6529b7765bb24ae6da82c12e2a9728.
Delivery06f52a35-9aa4-49b3-bd79-190787832b8b; guard cleared after completion.
Host remains in Capture only. No normal production dithering setting enabled.

Saved operator-authorization.json, pre-send-vm.json, operator-start.json,
physical-delivery-result.json, live-validation-summary.json and complete
transcripts under runtime/realworld-sheet-20261020. Staging/readiness reports
above are historical snapshots; physical completion supersedes their pending
delivery state. Appearance, missing-mark checks, pattern comparison and physical
measurements are still awaiting the owner's inspection. Controller completion
alone does not establish those results.

## Owner inspection and darker comparison

Owner reports: “it looks pretty goo. I think the engraving needs to be darker
about 20% though”. Recorded the overall appearance as good with a request for
darker engraving. Individual element completeness, panel comparisons and physical
dimensions were not supplied and remain unreported in operator-inspection.json.

Prepared a 54% candidate as a 20% relative increase from45%, retaining30ips,
vector1ips/15%/1000PPI and AutostartOff. This does not assume a linear material
darkness response. The old candidate and its physical records remain unchanged.
See power54-comparison-20261020.md; that candidate has not been sent.
