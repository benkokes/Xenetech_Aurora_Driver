# Native Aurora printer: first CorelDRAW print

The installed **Aurora JobServer (Test Capture)** printer received the owner's
CorelDRAW X7 `test.cdr` print on October 18, 2026 at 20:52:12 UTC. No visible
notification appeared because the active receiver saves captures only.
The Windows print queue was empty after receipt. No physical laser connection
was made by this test.

Capture: `runtime/native-direct-capture-r4/c779a771-1c00-4ca2-a685-50f923149c52`.
The 72,743-byte OpenXPS document has SHA-256
`23863b1c6141d199d2c36c3f97ff783b3417f124a7527d63ae811aafff1f3077`.
Its native job-attached PrintTicket contains all nine expected Aurora features:
raster 30 ips / 45 percent; vector 1 ips / 15 percent / 1000 PPI;
167 laser DPI; Autostart off; combined output; no focus command.
These settings came from the captured job, rather than synthetic injection
or a read of the printer's current defaults.

`prepare_capture` completed locally in `runtime/native-direct-review-r4-c779`.
Its intake scene pages exactly match `runtime/coreldraw-compat-167-checked`.
Comparison with the physically accepted 45-percent calibration confirms:

- Initialization and vector commands match, after omitting only the job title.
- Square coordinates and path order match, with 1002-unit width and height.
- Raster position and all 5,740 exposure samples match exactly.
- Settings match, and Autostart remains off.

The generated CG job is SHA-256
`c03b427f2cfc6293efce70e80aadf2e68746048c5270b93b189cad7a65dc2237`.
Its raw job is SHA-256
`fb72a833525b7122cf4db0ed1a72e0d184249be976df77ea44854a96f9c6a375`.
The comparison is saved in `comparison-to-accepted-45/comparison.json`.

A private copy of the actual captured print also passed the complete automatic
PrintService conversion, queue and delivery flow against the loopback controller
simulator. The simulator validated the protocol preamble and exact CG bytes.
There was one upload and a completed-with-warning result, using the simulated
known token warning. Restarting the host did not replay the print.
Evidence: `simulator-verification.json` and the private `simulator-service` queue.
This simulated delivery is separate from the capture receiver and does not
enable delivery from the installed printer to physical equipment.

A second print was received as `5bf8cec9-96da-47db-afac-eef2233d6326`, with
SHA-256 `f4c0333a64dbb0174d91f2b37db815451eaa1c28211e60ae75f087ac0c5af555`.
Its native job-attached ticket and encoded commands both contain raster power
46 and vector power 16. All other selections match the defaults. Its raster
samples, vector paths and placement exactly match the first print. Evidence is
in `runtime/native-direct-review-r4-5bf8/settings-verification.json` and its
`comparison-to-default-print` directory. The owner was then asked to restore
45/15 without printing.

The bridge now supports `--once --require-empty` for the first live print test.
The first flag stops the host after one completed delivery; later captures
remain retained and unsent. The second rejects any existing service backlog
before creating the store or binding the receiver. A simulator test with two
captures verifies only the first is dispatched, and another verifies refusal
of an existing root without starting the service. The prepared live-test plan
is `runtime/native-direct-live-test-plan.json`; operator readiness is pending.
No automatic physical bridge is currently running. A future physical test must
use a fresh queue/capture root so these capture-only prints cannot become a
delivery backlog. Broader artwork and Windows 11 installation remain unvalidated.
