# Reviewed square-and-TEST physical calibration test

The first physical run is now complete: the owner reports a one-inch square
and complete but too-light raster text. The controller reported 9.818 seconds,
end code 0 and the known token warning. The owner requested a 50% relative
increase in raster power, so the **next candidate is 45% power at 30 ips**;
vector settings stay 1 ips / 15% / 1000 PPI. It is staged at
`runtime/calibration-square-test-167-power45`. It was subsequently authorized
and delivered once; the controller reported completion in 9.800 seconds.
The owner reports everything as expected for that revised result. Separate
axis dimensions and bed offsets remain unreported. See
[the first live result](../analysis/generated-calibration-live-20261017.md) and
[the 45% test](../analysis/power45-calibration-live-20261018.md).

The owner chose to preserve the X7 lettering shown in the comparison. Both
measurement candidates use that exact 167-DPI exposure plane and the vector section
that matched XP byte for byte. This is one controlled calibration test, not a
production release of the new renderer.

`python -m aurora_jobserver.calibration CHECKED-INTAKE NEW-TEST-DIRECTORY`
stages it offline. The tool accepts only the exact reviewed source hash, exposure
hash, grid, dimensions, position, path, text mode and process settings. It builds
a new measurement job from the verified scene. It does not edit existing draft
files, expose a general draft-release option, submit to a queue or open a socket.
Ordinary `artwork.encode` and `artwork.build` retain their blocked draft marker.

First-test package: `runtime/calibration-square-test-167`. The settings, hashes
and simulator evidence below describe that original 30% test. To reproduce the
next 45% candidate offline in a new directory, add `--raster-power-percent 45`
to the staging command. This changes only the job title and raster power.

| Setting | Value |
| --- | --- |
| Artwork | One-inch design square, with TEST above it |
| Raster | 167 DPI, 30 ips, 30% power |
| Vector | 1 ips, 15% power, 1000 PPI |
| Page / origin | 30 x 18 inches, flatbed, zero offsets |
| Focus command | No Focus at Start |
| Autostart | Disabled (`normalstart START`) |

The old `set_xyup_feed` command remains, so its known token warning may recur.
The emitted square spans 1002 job units; the owner measured the result as one
inch. Separate axis measurements and bed offsets remain unrecorded.
The candidate contains no new controller-language comments or
unverified setup commands.

The native-coordinate content bounds are x=876..1878 and y=720..2214. Under
the approximate 1000-unit/inch model this is about 0.88..1.88 inches from the
left and 0.72..2.21 inches from the top. This is a guide for covering the test
area, not an already measured physical placement. Prepare material and focus
as for a normal job. Keep XP offline and its JobServer closed.

Sending is a separate operator-approved action. Although Autostart is disabled,
the first test required the owner's manual Start. Treat each new test as a
physical operation requiring material, focus and operator readiness.
There is no automatic send, automatic upload retry or production approval.
An uncertain upload retains the existing durable delivery guard.

The raw file is 6,208 bytes, SHA-256
`d4c6bb0d2af22ef88ef6ce5afb6527de0a6c787b4d2a6e652ec767ddd24898af`.
The compressed file is 948 bytes, SHA-256
`376affd16d87733d506de26618d0ac6105b797a3a98523bcd6afca34b7e0034a`.
`calibration-plan.json` records identity/settings, `preview.png` / `preview.svg`
show the native layout, and `measurements-template.json` has empty result fields.

The exact compressed file completed a loopback-only exchange on 127.0.0.1,
with fragmented/no-echo replies and the preserved token warning. Its 1,294-byte
main-channel request stream matched the wire plan exactly. The simulated job
time comes from the old fixture and is not an estimate for this job. Evidence
is in `runtime/calibration-simulator-validation`; the physical laser was not
contacted. Independent decoding also confirms that the staged vector command
section and process settings still match the XP reference. The full Python
suite passes 80 tests; the frontend retains its 24 passing checks.

For further calibration, obtain separate square width and height in mm or inches
and evaluate the revised text darkness. If practical, also record the square's left
and top offsets from the usual job origin. Retain those measurements with the
candidate hash and actual delivery transcript before deciding on broader
artwork tests or Windows print-flow integration.
