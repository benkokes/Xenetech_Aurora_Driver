# Normal CorelDRAW print-path sheet — October 20

Prepared AuroraSheet167P54-Print.cdr, now active in X7. The prior visual-only
document remains open. The printable file contains the accepted668x501 raster
samples without the preview's red lines, plus actual red vector paths for the
square and circle. Two vector shapes are combined as one curve with two
subpaths, so the page has one bitmap and one vector curve. Page30x18in;
bitmap4x3in at1in fromleft/top; full-color output; AsInDocument/printerdefault.
Source builder tools/CorelMakePrintableSheet.cs neither prints nor alters queue
defaults. The ordered panels are preprocessed artwork, global DitherBitmapsOff.

One actual X7 PrintOut to the capture-only test printer completed. The guarded
helper temporarily selected54% raster/30ips, vector15%/1ips/1000PPI,167DPI,
AutostartOff, then restored original per-user DEVMODE byte-for-byte and left
machine defaults unchanged. Actual received complete settings match expected.
Lossless PNG contains all668x501 source pixels exactly; no JPEG degradation.
Normal prepare_capture converts and encodes one raster plus two closed vectors.
No physical laser connection or send occurred during this capture check.

Capture db43e48e-f02c-4638-ace5-107b4b2dadf6; sourceSHA
005a73d3e436ab26019a848b9e99e0724f7fa763424315c4f653751ce6e4867a.
PrintableCDRSHA9f34802a08ee0fe5ef3a60d1cf4c25cba666d7b6c32298e9a078a250d9729246.
PreparedCGSHA7dbaec67e617fd2503073b348fa22c6bb78a9ce62c34e0157ac5d58abcf49fe7.
Rasterbounds966,978..4974,3984 native units, all within stated material coverage
x.9–5.3in/y.9–4.3in. Square1002x1002units; circle504x504units from Corel's
grid rounding (prior native staged circle500units). These are decoded sizes,
not newly measured physical dimensions. X7 owns artwork rendering/placement;
no offset is inserted to force equality with the separately staged native job.

Evidence runtime/normal-coreldraw-sheet-20261020/capture-verification.json,
capture-check/,prepared-capture/,source.json,printable source and CDR metadata.
Fresh VMmetadata confirms XP cable disconnected/NIC2–8none. Host recorded idle
Captureonly. UIJobServer process32748 is running from the project entrypoint.

Next normal live print is operator initiated: fresh material/focus, verify54%
in X7 Properties (the test helper restored previous defaults), JobServer Enable
laser printing, one final X7 Print to Aurora JobServer(TestCapture). Once newjob
is ready on the laser, selectCaptureonly to hold subsequentprints, thenStartonce.
Do not submit another copy if nothing appears. This is the standard desktop
JobServer path, not the separate native-sheet sender. Monitor the fresh session
capture and queue, native settings and completion; no native sender script should
be used for this integration run. Normal live print has not yet been submitted.
