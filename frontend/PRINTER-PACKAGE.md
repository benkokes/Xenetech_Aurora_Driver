# Aurora native printer package and automatic print pipeline

**Current installed build:** `build/printer/AuroraV4-0.5.3-r11`, version
0.5.3.0. Travel Speed now displays the established baseline as **0.100 ips**
and uses a versioned preferences snapshot. The native command remains 100.
Old accepted presets migrate without changing their laser process settings;
other old travel values remain held until explicitly reselected in ips. Other
travel speeds are still held, including the newly captured 1.000 ips value.
Lossless PNG capture from r10 is retained. The complete regression has 209
passing tests; 130 native snapshots, a real X7 capture and post-install checks
pass. The actual X7 capture exercised the updated reader/settings on r10's
unchanged transport before the r11 UI installation; no physical test is claimed.
See [units and collector repair evidence](../analysis/collector-travel-fix-20261020.md)
and the earlier [bitmap repair evidence](../analysis/bitmap-quality-fix-20261020.md).
Earlier package/test descriptions below are historical.

The prepared driver is **Aurora JobServer XPS Bridge**, an x64 v4 data-only
XPS passthrough driver with its own identity. It uses Windows' rendering and
configuration components; JBS conversion and Ethernet delivery run outside the
spooler. It does not reuse Microsoft's printer identity or edit its files.

Sources are in `frontend/driver`. Generate a new package directory with:

```powershell
python -m tools.build_printer_package build/printer/NEW-DIRECTORY
```

The installed build is now `build/printer/AuroraV4-0.4.1-r7` (driver version
0.4.1.0), printer **Aurora JobServer (Test Capture)**. It adds the XP tab names
and named material presets to the
[direct Properties window](PRINTER-PROPERTIES.md) with visible raster/vector
controls. Its GPD and all native defaults, including 167 DPI, are unchanged
from r6. Installed hashes, registry version, page and native tickets are verified;
the owner is checking the new tabs and presets in CorelDRAW. R6 remains available
for rollback. Build that window first and pass `--printer-ui build/printer-ui` to
the package generator to include it. The earlier r4 Advanced UI and integrated
print path have been validated. The owner confirmed the new first-screen window
and direct return to Print on Cancel. An actual CorelDRAW capture confirms OK
saves the selected 46/16 powers into the job and the encoded laser commands,
preserving its artwork and placement. The current receiver remains capture-only.
The underlying Properties
definition exposes raster power/speed, vector power/speed/PPI, laser DPI and
Autostart as standard Windows option lists. This is not yet the original XP
slider layout. Power is selectable in whole percentages; speeds are an explicit
list from 0.001 to 31 ips; PPI choices are 5, 10, 50, 100, 200, 250, 500, 750 and
1000. Laser DPI is 100 or 167, separate from the fixed 600-DPI application
rendering resolution. Initial defaults match the accepted test: raster 30 ips /
45%, vector 1 ips / 15% / 1000 PPI, 167 laser DPI, Autostart off.

This first profile supports a fixed 30 x 18 inch flatbed, zero offsets, no focus
command, raster-and-vector output, neutral engraving and thin pure RGB red
cuts (maximum 0.2 mm). Controls for rotary, autofocus, offsets, color settings,
arbitrary custom speeds and other output modes are not advertised. A vector-only
document is held because its controller transfer branch has not been implemented.

## Per-print settings and automatic processing

The driver maps its private options into the job's PrintTicket namespace,
`urn:aurora-jobserver:print-schema:1`. Windows prefixes these DOC_PROPERTY
feature names with `Job`: for example, `AuroraRasterPower` becomes
`JobAuroraRasterPower`. Native default-ticket inspection confirmed this mapping;
the reader and generated test tickets use the native names. Microsoft documents this
[GPD-to-PrintTicket mapping](https://learn.microsoft.com/en-us/windows-hardware/drivers/print/configuration-modules-based-on-gpd-or-ppd-files).
The package uses the documented
[v4 setup model](https://learn.microsoft.com/en-us/windows-hardware/drivers/print/v4-driver-inf)
and [XPS passthrough rendering](https://learn.microsoft.com/en-us/windows-hardware/drivers/print/v4-driver-rendering).

`printer_settings.py` reads the complete laser settings from the PrintTicket
attached to the actual fixed document sequence. It does not substitute current
defaults, accept orphaned settings parts, or guess conflicting page/document
options. Unknown/missing options, foreign namespaces, malformed XML, DTDs,
external relationships and oversized packages stop conversion.

`print_pipeline.py` snapshots a completed `aurora-direct` capture, reads those
settings, invokes the native intake, validates the scene and encodes JBS. This
experimental printer route uses the software-checked Corel flatbed profile
whose square-and-TEST job passed the owner-observed physical tests. Broader
artwork/material and precise placement validation remain. Ordinary offline
artwork drafts retain their marker and remain rejected by queue delivery.

`print_service.py` connects that conversion to `DirectPrintBridge`: receive,
convert, queue and send automatically, with no second software Send action.
It retains print order, snapshots and delivery history, and stops on failed or
uncertain delivery. Both LPR queues can share standard loopback port 515 while
publishing to separate directories; preview captures cannot enter the direct
print pipeline. This host is implemented but has not been started against the
physical laser. It is not yet registered as a Windows service/startup task.

## Verification completed

Windows installed r4 successfully on October 18, 2026. Native inspection confirms:

- 30 x 18 inch paper and full printable area, portrait, source resolution 600 DPI.
- All nine Aurora features and every option in the generated definition.
- Default raster 30 ips / 45 percent, vector 1 ips / 15 percent / 1000 PPI,
  laser DPI 167, Autostart off, combined output and no focus command.
- Normal queue status, loopback LPR port, and no laser sender started.

Evidence is in `runtime/native-printer-inspection-r4` and
`runtime/native-printer-install-result.json`. A sanitized native default ticket
is retained as `tests/fixtures/aurora-v4-default-printticket.xml`.

Earlier r2/r3 queue creation failed with `0x800703eb` / 1003. R3 added the required
InputBin feature and vendor-defined media selection command, but still failed.
Offline comparison isolated two additional problems: missing raster/cursor
command definitions and percent signs in literal power labels. R4 supplies empty
commands for XPS passthrough and spells out "percent" in UI strings. It preserves
all numeric settings, option identifiers and the fixed portrait profile.
References: [standard features](https://learn.microsoft.com/en-us/windows-hardware/drivers/print/standard-features)
and [vendor-defined paper](https://learn.microsoft.com/en-us/windows-hardware/drivers/print/supporting-vendor-defined-paper-sizes).

All **102 Python tests pass**. The native pipeline test passes a copy of the
actual CorelDRAW capture through a real loopback LPR session, native Windows XPS
conversion, JBS generation and automatic controller-simulator delivery. The
driver settings are injected into the copied PrintTicket for that test; it
does not establish that CorelDRAW's Print dialog has submitted them. Native
PrintConfig now independently confirms the installed driver's defaults and
capabilities. A real CorelDRAW print now also passed capture, native per-job
settings decoding, conversion and exact comparison with the accepted 45-percent
calibration's commands, pixels and placement. The actual capture completed the
automatic service flow against the loopback simulator exactly once, without
replaying on restart. See [native print evidence](../analysis/native-coreldraw-print-20261018.md).
The owner's screenshot now also confirms CorelDRAW's Advanced Document Settings
shows raster power/speed, vector power/speed/PPI, laser resolution and Autostart,
with every displayed value matching the expected defaults. The controls are in
Properties → Advanced → Document Options → Printer Features. No custom UI
extension is needed to expose these controls for the current test.
Generated bytes match the independently checked scene/encoder output. Restarting
the bridge does not repeat the completed print. Further tests verify that changed
Properties values reach the actual speed/power/PPI/Autostart commands and that
preview captures or missing properties cannot send jobs.

Microsoft WDK/SDK 10.0.26100.6584 tools were downloaded into the ignored workspace
tool directory, without installing a system SDK. The new
`tools.validate_printer_gpd` wrapper requires successful native enumeration of
every declared feature and a compiled BUD. Exit code zero or BUD creation alone
is insufficient: earlier invalid definitions passed those weaker checks.
R4's native cache is 49,212 bytes and all 15 declared features enumerate (plus
Windows' implicit RESDLL feature). A hash-bound report is required by the installer.
Run the checker against a temporary copy with the shared ntprint include files:

```powershell
python -m tools.validate_printer_gpd build/printer/NEW-DIRECTORY/Aurora.gpd --checker PATH/TO/gpdcheck.exe --shared-files PATH/TO/ntprint/Amd64 --report build/printer/NEW-DIRECTORY/native-validation.json
```

Inf2Cat passed signability checks for `10_VB_X64` and
`10_GE_X64` with no errors/warnings and generated the catalog. Basic InfVerif
reports valid with the no-service warning for this printer definition. Its
modern `/w` isolation/service rules report errors for this legacy v4 layout;
this is not a claim of modern Windows Driver/WHQL certification. Spooler
installation, PrintCapabilities and CorelDRAW Properties/Print passed. A second
capture confirms native per-job power changes (46/16) reach both the ticket and
the encoded commands while preserving the artwork. A separate Windows 11
installation remains to be tested.

The installer helper compiles with the existing Framework compiler. Trust and
installation scripts have passed syntax checks and non-mutating dry runs.

## Local test signature and installed capture queue

A development catalog signature is prepared. Its public certificate is:

- Subject: `CN=Aurora JobServer Local Development`.
- Thumbprint: `2A5AC9C0A94B0B3AD79BD7C30EF897ADFD06F75F`.
- Expiry: January 16, 2027 (UTC).
- Public file: `runtime/printer-test-signing/AuroraLocalTest.cer`.
- Signed catalog SHA-256:
  `009376c0326e46b47eb01f17fef3bfe89f00b10cbdf67f909319582a2c9e65b7`.

R4 uses the same approved certificate and its catalog verifies as Valid.
The updated administrator launcher selects r4.

The owner approved machine-wide trust and a separate capture-only printer.
Certificate trust is now applied and Windows reports the catalog signature as
Valid. The installer helper uses verified package-API exports in `winspool.drv`.
Its encrypted private-key file and Windows-profile-protected
password are kept only under ignored `runtime/printer-test-signing`.
This is a local development signature without a timestamp, not a public release.

Windows' [Driver Store requires a trusted signed package](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/driver-store).
The owner explicitly approved adding the specific development signer to
LocalMachine Root and TrustedPublisher and installing the separate
**Aurora JobServer (Test Capture)** printer. Installation completed through the
Windows administrator prompt. The desktop launcher,
`Install-Aurora-Test-Printer.cmd`, can be rerun as administrator. The public
certificate thumbprint is pinned by the trust script; removal supports that
same exact thumbprint. No boot security or driver-signature enforcement is changed.

The test printer uses `127.0.0.1:515`, LPR queue `aurora-direct`, port
`AuroraDirect_LPR_Loopback`. Installation starts no receiver, sender or service.
The running receiver is capture-only, so the owner can test CorelDRAW
Properties and Print without contacting the Aurora. The old preview receiver
was replaced after checking that it was idle; both `aurora-capture` and
`aurora-direct` now share its loopback port and publish to separate folders.
That receiver's earlier captures remain in `runtime/native-direct-capture-r4`.
The new normal [JobServer window](../JOBSERVER.md) now owns the loopback receiver,
initially capture-only, and saves new captures under
`runtime/desktop-jobserver/capture-only`. Existing Microsoft XPS
and Aurora Preview queues remain unchanged. After native settings transport
passes, the automatic bridge can be enabled separately for a prepared laser test.

The first separately authorized integrated laser test has now passed. CorelDRAW
Print automatically captured, encoded, queued and delivered the job, carrying
the restored 45/15 powers. The owner pressed the physical Start button and
reported a complete correct engraving. The one-job host stopped and the
capture-only receiver was restored. See the
[integrated live-test record](../analysis/integrated-print-live-20261018.md).
