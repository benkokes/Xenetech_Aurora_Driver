# Bottom-Up physical validation — October 22

The owner authorized one staged raster-only test, confirmed bottom-up engraving
after pressing Start, and accepted the final result: **complete, upright,
correctly positioned; no unexpected marks**. No separate dimensional
measurements were supplied. No vector cuts were included or performed.

The controller reported end code 0, **81.680 seconds**, and only the previously
known `set_xyup_feed` token warning. The sender finished successfully and cleared
the shared delivery guard. Its diagnostic text is preserved in full; the
warning's pre-process power/scale text was not used to override the actual
encoded 45% raster process.

## Test identity and settings

- Title `Print_927b0eb9`.
- Job `fa0f6ab6-29de-4206-b353-d214e2054e8d`.
- Delivery `3c690c22-2a3a-44cc-90af-50f859ad94fe`.
- Raster Only, Use Color Settings off, Bottom-Up on, Autostart off.
- 167 DPI, 30 ips / 45%, one 952 × 748 raster, zero vector paths.
- Normal baseline origin UL (1116,996); bottom-up origin LL (1116,5478).
- Samples are exactly the accepted mixed sheet's raster rows in reverse order;
  X7 artwork appearance and placement are preserved.
- Material guide x=0.9–7.1 in, y=0.9–5.7 in from left/top.

The copied source was given an explicit staged PrintTicket; this was not a new
Corel print or a change to the owner's printer defaults. Its exact bytes passed
one loopback simulation before the owner authorized the one physical send.
Fresh VM readback confirmed XP cable disconnected, NICs 2–8 absent. The owner
confirmed XP JobServer closed and material/focus readiness. Host remained in
Capture only; no extra live printing was enabled.

## Delivery evidence

Runtime folder: `runtime/bottom-up-physical-validation-20261022`.

The CG job is **52,727 bytes**, SHA-256
`33d1736c41cbae251a009a9a920327d69cbbdf502258e927f5dd40a2db335008`.
Its framed upload request is **52,939 bytes**. All **53,073 main-channel request
bytes** match the wire plan, SHA-256
`ad6333435896448d5249e6b837245ba2b932125f3bc264bedd17699404e5b983`.
One attempt and one upload are recorded, with no reset or retry.

Evidence under `staged-test-r1/physical-test` includes the operator authorization,
queue and transcripts, raw completion result, `controller-completion.json`, and
`physical-acceptance.json`. The latter records both operator reports and the
controller/byte verification. `send-once.py` has already run and must not be
rerun. Sender process/session 72149 has completed.

## Product status

The existing normal 167-DPI Bottom-Up implementation is now physically validated;
no encoder change, printer installation, preference/default edit, or restart is
needed. Inversion and other resolutions are not established by this test.
Per-color Vector Only at 167 DPI is separately accepted through the real Corel
Properties path. Per-color raster/mixed support remains unfinished. Cylindrical
setup remains offline-only without rotary hardware.
