# First integrated CorelDRAW-to-Aurora physical print

On October 18, 2026, the owner approved one live print from CorelDRAW X7 through
the installed **Aurora JobServer (Test Capture)** printer. The receiver was
switched from local capture to the automatic PrintService using a fresh root,
`runtime/direct-print-live-test-20261018-01`, with `--once --require-empty`.
The Windows queue and new service root were empty before arming. Earlier
capture-only prints were preserved separately and were not submitted.

The owner clicked Print once. The replacement automatically captured the
document, read its native job-attached settings, rendered/encoded it, queued it
and transferred it to `192.168.1.244`. There was no second software Send action.
The owner reports pressing the machine's Start button and confirms:
"I pressed Start; it completed and looks right".

The captured settings were raster 30 ips / 45 percent, vector 1 ips /
15 percent / 1000 PPI, laser resolution 167 DPI and Autostart off. The page was
30 x 18 inches. Raster samples, placement, vector paths and commands match the
earlier accepted 45-percent calibration after ignoring only the job title.

- Capture: `2fab6107-2985-479e-9516-d8f225e59286`.
- Job: `0fe75927-907f-4ec3-96e6-750cc35fd894`.
- Delivery: `b58f2434-18c5-4a7b-800a-66064dc96dd0`.
- Controller result: completed with warning, end code 0, job time 9.798 seconds.
- One upload; the complete 1,288-byte main-channel transmission matches the
  generated wire plan exactly. The durable unresolved-delivery marker is clear.
- Prepared 942-byte job SHA-256:
  `017ef99c4264cfa59fce02c45251788000e0f8dfdf7e9f4e7806b1c459e5ca12`.
- Main TX SHA-256:
  `bc85b90398c1193cbd1e6c5d913043da49c4c961a2a874bee464f31dcfacf4c1`.
- Main RX SHA-256:
  `6705a5c9cb52229349211d13b2e7d0956f620389bb785ebc0d65bc4ad9fe13a4`.

The known `set_xyup_feed` token warning remains. The owner accepted the finished
engraving. Separate axis/bed-origin measurements were not supplied for this run.
The controller report and the owner's physical observation are recorded
separately in `runtime/direct-print-live-test-20261018-01/live-validation-summary.json`.
Full transcripts, queue history, per-print settings and the offline comparison
are retained under that root.

The live host stopped after this job and exited. The capture-only receiver was
restored on loopback port 515; current prints to the test printer save locally
and cannot reach the laser. The one-job root must not be reused as a new test
root. No service/startup task or continuously enabled physical bridge was
installed. Routine JobServer launch/status/startup packaging, broader artwork
coverage and a separate Windows 11 installation remain to be completed.
