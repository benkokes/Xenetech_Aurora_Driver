# Per-color vector integration and physical acceptance

## Current status — October 22

The owner authorized the staged test, pressed the machine Start button, and
confirmed **all five paths finished with no unwanted marks**. The controller
reported end code 0, **15.648 seconds**, and only the known set_xyup_feed warning.
Job `f2eaf4a6-ad4a-4b27-9a99-e8b3d287b437`, delivery
`8e901ae8-614b-4b75-9b21-539f4c0c7b19`: one attempt/upload, all 3,621 main-channel
request bytes match the wire plan, and the shared guard cleared. The CG file is
3,275 bytes; its framed upload request is 3,487 bytes. Do not confuse those sizes.
Evidence: `staged-vector-test-r1/physical-test/physical-acceptance.json` under the
runtime directory below. No separate calibrated power/speed/PPI measurements
were supplied; acceptance is visual completion plus verified command bytes.

Normal 167-DPI Vector Only now supports UseColors. Decoder holds no longer flag
that specific combination, and the native capture, encoder, service, and desktop
use it by default. Other modes, resolutions and unresolved preferences remain
held. An explicit internal opt-out still applies to cached conversion; no old
held captures are replayed. The standalone draft APIs remain marked/blocked.
Desktop history shows Off/Per-color and the immutable palette instead of
misleading ignored global powers. Status reports pipeline 3 and
`per_color_vector_dpi: [167]`.

After rollout, full discovery again ran 252 tests (250 passed, two WSH sandbox
initialization failures); rerunning the two WSH fixtures outside the sandbox
passed. An added desktop/LPR/native/loopback per-color test passed separately,
as did seven history display checks including the new per-color display test.
These two additions were not part of that 252-test discovery invocation.
Logs: `rollout-regression-r1.log`, `rollout-wsh-fixtures-r1.log`,
`desktop-rollout-r1.log`, and `history-rollout-r1.log`.

The owner restarted JobServer; readback verifies pipeline 3, per-color vector
DPI 167, idle Capture only, and no error. No additional physical send occurred.
The fresh capture-only Corel Properties check is complete: capture
`a7263df0-84a6-4092-b295-4dfeb4c348b3` carries the exact requested Black/Red/Blue
power/speed/PPI values, Vector Only, UseColors, Sort on, Pause off, and 167 DPI.
Offline normal preparation produces all five paths and process commands exactly
as in the accepted staged job. The only command difference is Autostart On;
the owner explicitly confirms they left it On, so no save failure is indicated.
The selected On state was preserved, never silently changed. No new physical
send, mutable-default edit, or replay occurred. Evidence is
`native-properties-a7263df0/verification.json` and its operator confirmation.

## Historical pre-acceptance development

The owner's requested feature work now includes a complete native vector-only
color route behind an explicit validation gate. Ordinary JobServer printing
still holds UseColors. No printer installation, default change, desktop restart,
XP action, or physical send occurred in this development turn.

## Implementation

The normal capture/encoding/service functions accept an internal
`allow_color_vectors=False` parameter. A supervised staging caller or local
simulator test may explicitly opt in; there is no new live desktop or CLI switch.
The exception removes only UseColors for 167-DPI Vector Only jobs. Other modes,
resolutions, cylindrical/focus/bitmap settings, and unrelated holds still fail.
Resuming an existing prepared validation capture rechecks the gate, preventing
an unmarked test artifact from bypassing normal policy through cached conversion.

The full immutable PrintTicket supplies the palette; no mutable printer default
or saved material is read later. Native all-color hairline extraction retains
source RGB, and the color plan chooses independent power/speed/PPI for each path.
The existing color model supplies order, caching, unknown-color White fallback,
and established disabled-color/pause limitations. Global process values do not
replace palette values. The output uses the measured one-pixel zero-exposure,
explicitly zero-power carrier. The gated path preserves per-job Autostart;
ordinary public draft functions remain marked and normal-start only.

An all-disabled/zero-power palette now produces the existing durable local
Nothing to cut outcome, even though eligible hairline geometry exists. The
resume check recomputes that outcome from the attached palette and source.
It does not send, create a delivery guard, block a corrected fresh Print, or
replay on restart. The existing thick-line/no-hairline behavior is preserved.

## Verification

Seven new native pipeline tests pass: independent three-color process values,
default hold versus explicit test exception, cached-conversion gate checks,
immutable palette across consecutive captures, all-disabled then corrected
exactly-once loopback delivery, tampered outcome rejection, thick-line no-op,
per-job Autostart, and unrelated feature/mode holds.

The first new-test run failed because its ElementTree-generated PrintTicket
dropped declarations used by QName attribute values. The test fixture writer
now uses minidom for that ticket, preserving namespaces. Production parsing
correctly rejected the invalid fixtures; no parser relaxation was made.
Both initial and corrected logs are retained.

Full discovery ran **252 tests**: 250 passed and two local Windows Script Host
fixture checks could not initialize in the sandbox (Access denied). Rerunning
those two outside the sandbox passed both. There are no remaining test failures.
This is not a claim of a single clean 252-test invocation.

Evidence:

- `runtime/color-vector-integration-20261022/native-tests-r1.log` (fixture error)
- `runtime/color-vector-integration-20261022/native-tests-r2.log` (7 passed)
- `runtime/color-vector-integration-20261022/regression-r1.log` (252 discovery)
- `runtime/color-vector-integration-20261022/wsh-fixtures-r1.log` (2 passed)

## Exact staged job

`tools/stage_color_vector_validation.py` copies the saved accepted mixed-sheet
source into a new synthetic capture, attaches explicit validation settings,
updates its scalar carriers consistently, and runs the actual native pipeline.
This is **not a fresh Corel print** and does not claim an operator-selected
PrintTicket. The original source and printer settings remain unchanged.

Staged folder:
`runtime/color-vector-integration-20261022/staged-vector-test-r1`

- Title **Print_cbb31b27**, Autostart Off, 167 DPI, no raster exposure.
- Three black paths: 1 ips / 15% / 1000 PPI.
- One red path: 1.5 ips / 10% / 750 PPI.
- One blue path: 2 ips / 5% / 500 PPI.
- Cut bounds x=1.116–6.828 in, y=4.206–5.208 in from the left/top.
- Material guide x=1.0–7.0 in, y=4.1–5.4 in. The zero-power carrier moves to origin.
- CG SHA-256 `7c8ff392ecce98240c394d8d162ce677f422ea3d6bb20a83e2ad4018bf32aebe`.

`tools/verify_color_vector_stage.py` tested these exact bytes through one upload
to a controller bound to 127.0.0.1, with fragmented/no-echo replies. The retained
queue bytes match; another poll sends nothing. Evidence:
`runtime/color-vector-integration-20261022/staged-loopback-r1/verification.json`.
Its completion report is simulated, not a real laser result.

The owner has been asked to prepare material/focus and authorize this **one**
staged physical send. No send is authorized merely by the earlier “proceed”
software-development instruction. Normal UseColors remains held pending that
physical acceptance and subsequent deliberate rollout. Raster/mixed per-color
support remains separate unfinished work; cylindrical remains offline-only.
