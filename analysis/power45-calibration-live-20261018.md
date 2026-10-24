# 45% raster-power physical calibration test

The owner explicitly authorized the prepared 45% test and reported starting
the engraving manually. The controller reported completion in 9.800 seconds,
end code 0, with the previously observed `set_xyup_feed` token warning.
The owner subsequently reported, "everything is as expected'". This accepts
the completed test and raster darkness. Separate width/height measurements,
measurement precision and bed-origin offsets were not supplied; their fields
remain empty. The earlier 30% test's reported one-inch size is retained as a
separate observation rather than copied into the 45% test's measurement fields.

The drawing and raster exposure samples are unchanged from the first physical
square-and-TEST job. Raster settings are 30 ips / 45%; vector settings remain
1 ips / 15% / 1000 PPI. Autostart is disabled. This is the requested 50% relative
increase from the first test's 30% raster power.

## Delivery evidence

- Evidence directory: `runtime/calibration-physical-test-167-power45`.
- Queue job: `dcbdb4be-a790-4760-97ed-925d4e03801a`.
- Delivery: `d07245f3-ea23-4951-8dd3-3000c9ddcc9d`.
- Prepared CG: 943 bytes, SHA-256
  `1c0915fe73473ae92991e13d62ecd628fc52c2f95093139ea621dba3b91fe806`.
- Main TX: 1,289 bytes, SHA-256
  `d2bf10aabcac950b46ab3911c309853a75b26784d287583c09d0cc48a50a05d8`.
- Main RX: 925 bytes, SHA-256
  `3c5149e660e2696c404a3bf4d9b2f4cf6b34aaf71f11db4f0147abdd11c488c4`.
- Exactly one upload; the complete main TX matches the wire plan byte for byte.
- Controller features 5459 and 330476101; startup status transitioned from
  `ffe1010000120200` to `ffe1010000020200` before upload.

The same previously verified legacy connection sequence was used. Port 99
refused its connection; all three job channels and preflight then succeeded.
The controller echoed commands during startup and the upload preamble, unlike
the first test's no-echo replies. The existing transport accepted both forms.
No controller command or transport implementation was changed for this test.

The delivery guard was cleared after the completed result was saved. Full
channel transcripts, authorization, manual-start observation and the immutable
settings snapshot are retained with the queue. `live-validation-summary.json`
and `physical-delivery-result.json` record the result. `measurements.json`
contains the owner's accepted result, with unreported dimensions left empty.
The assessment is also preserved as an append-only job event. No general production
or Windows 11 validation is inferred from this controller completion.
