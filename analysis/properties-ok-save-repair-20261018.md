# Properties OK save repair — r9

The owner confirmed that all three expanded r8 pages display their controls.
Clicking OK displayed **Object reference not set to an instance of an object**
in the window footer. No print was submitted. R8's generic footer discarded
the stack trace, so the precise throwing line in that original attempt is not
known.

The previous save path wrote the new parameter, called NotifyXmlChanged, then
looked up and dereferenced native feature/option wrappers without null checks.
The validated request was also inspected through such wrappers. R9 removes this
dependency from the complete-settings path:

- It keeps the caller's ticket reference and reads initial selections/options
  from bounded XML, with namespace-aware names.
- It writes all nine carrier features and the full snapshot into one live DOM
  update, verifies the values, then notifies Windows once.
- Validation results are compared using their XML and fully resolved qualified
  names. No feature-wrapper lookup is needed after mutation or validation.
- Existing private-namespace prefixes are reused, avoiding another alias when
  one is already declared.
- Missing tickets, capabilities, asynchronous operations and validated results
  produce explicit messages. Failures retain their stage and complete exception
  in `%TEMP%\AuroraPrinterProperties.log`; the window stays open for retry/Cancel.
- Cancel retains the established S_FALSE behavior that returns directly to
  CorelDRAW's Print dialog.

The actual Save/Validate/Commit sequencing now has a managed COM-interface test
where feature wrappers are deliberately unavailable. Full 46.25/16.25/777
settings reach Commit unchanged. Five missing-operation, failed-validation or
failed-commit cases keep the request unsaved and retain safe cancellation.
These are fault-injection tests, not a claim that every injected condition was
observed in Windows. The earlier enumeration-only COM probe could not provide
a settings ticket outside an active preference request and was not used as proof.

The **same complete-ticket writer** passes four actual installed-provider
MergeAndValidate → DEVMODE → PrintTicket roundtrips. Native defaults remain
167 DPI with 45/15 powers. The existing Properties regression test also passes.
The backend and driver setting identifiers/limits/hold policy are unchanged;
the previously passing 124-test backend run remains applicable.

R9 **0.5.1.0** is installed from `build/printer/AuroraV4-0.5.1-r9`.
Its catalog SHA-256 is
`1814bda077badbb5a7f07e452ee1b0dba2846119e8fd316f2f4f5463df25700e`.
Signing reused the already trusted development certificate. Inf2Cat reports no
warnings/errors and all GPD feature definitions are unchanged from r8e.
Installation and its four native conversions succeeded; no queue-default
change, print submission or laser I/O was performed. JobServer remains Capture only.

Evidence: `runtime/printer-properties-r9-install.json`,
`runtime/classic-native-roundtrip-20261019-023644`,
`runtime/native-printer-inspection-r9`, and
`runtime/printer-properties-r9-verification.json`.

The owner reopened the updated window and confirmed **OK returns to Print without
an error**. The original failure is therefore resolved in the real CorelDRAW
Properties request. The subsequent capture-only Corel print was received as
`2e31e91b-d6ee-48f8-a239-b7dd4dd26fa1`. It carries the requested **46% raster /
16% vector** powers, unchanged speeds/PPI, 167 DPI and Autostart off, plus all
42 snapshot fields and 16 color rows. Receipt hashes/lengths validate.

The actual captured document passes offline intake/encoding. Its raster pixels,
raster origin, vector paths and process settings exactly match the existing
46/16 reference output. Full-snapshot SHA-256:
`134eac3dce6c1f6c99257c45aa70d0439af23625356098de4bd8c6c8555e0dbf`.
See `runtime/r9-coreldraw-46-16-check/verification.json` and its comparison report.
The owner confirmed restoring 45/15 without submitting another print.
No new live test is authorized and laser delivery remains disabled.
