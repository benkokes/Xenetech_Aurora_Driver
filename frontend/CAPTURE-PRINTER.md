# Windows 10 / CorelDRAW X7 capture printer

The development target is confirmed: CorelDRAW X7, version 17.2.0.688, on Windows
10 Pro for Workstations build 19045, x64. The Windows 11 24H2 virtual-printer API
cannot run here. A local capture path using the installed Microsoft XPS Document
Writer v4 has instead been installed and tested.

## Installed queue

| Setting | Value |
| --- | --- |
| Printer | `Aurora Capture (Preview Only)` |
| Driver | `Microsoft XPS Document Writer v4` |
| Port | `AuroraCapture_LPR_Loopback` |
| Protocol | LPR with byte counting |
| Destination | `127.0.0.1:515`, queue `aurora-capture` |
| SNMP | Disabled |
| Default/user media | 30 by 18 inches, custom size, no rotation |
| Receiver | `python -m aurora_jobserver.print_capture` |
| Files | `runtime/print-capture/UUID/` |

This queue captures documents on this computer. It does not connect to the laser,
generate JBS or perform engraving. The receiver binds exclusively to IPv4
loopback. Setup adds no driver, service, startup task or firewall rule. The
mechanism avoids the 24H2 API dependency; Windows 11 installation and printing
still need validation, including that system's print policies.
The receiver writes a `captured` receipt to its console and saves the files;
there is currently no per-print popup or automatic JobServer JBS entry. A
successful Print click can therefore return quietly to CorelDRAW.

## Use

Double-click `launch-print-capture.cmd` and leave the receiver running while
printing. A second receiver cannot bind the same port. If it is stopped, Windows
can retain jobs and retry when it returns. In CorelDRAW choose **Aurora Capture
(Preview Only)**. For the first application test, print at original size / 100%,
with a known-size RGB red hairline square and black text or filled artwork.
Reopen the Print dialog or CorelDRAW if its printer list is cached.
Confirm that its media is 30 by 18 inches too. An existing CorelDRAW document or
dialog may retain older settings even after the queue defaults change. Keep the
application at 100% / original size; the driver does not expose a validated
PageScalingFactor override.
For this tested X7 setup, select **Page → Use printer default** on General and
**Layout → As in document**. Fully restart CorelDRAW after initially changing
the capture queue's media; the owner confirmed that this cleared the warning.

The driver supplies OpenXPS by default. The intake uses the native Windows XPS
Object Model to normalize it to Microsoft XPS for WPF, retaining the original
bytes and source format. No machine-wide XPS format policy is changed. A native
conversion error fails visibly instead of flattening the document to an image.

Each completed receive session publishes a new UUID directory with `source.bin`
(exact print bytes), `control.lpr` (exact control metadata), `received.json`
(durable file metadata saved before the final file ACK), and `capture.json`
(completed receipt with hashes and sizes). Directories starting `.receiving-`
are incomplete and must not be treated as ready input. Failures retain
`failed.json`. The receiver accepts either file order, requires nonzero byte
counts, bounds documents to 64 MiB and control files to 64 KiB, and ignores
client filenames when choosing local paths. Repeat prints get separate captures.
The prototype supports one control and one data file per LPR connection.

Inspect a capture using a fresh output directory:

```powershell
.\frontend\build.ps1
.\build\frontend\Aurora.XpsIntake.exe runtime\print-capture\CAPTURE-UUID\source.bin runtime\my-preview --cut-color '#FF0000' --max-cut-width-mm 0.2
```

The explicit red/0.2 mm rule is diagnostic. CorelDRAW hairline semantics need
checking before selecting cutting rules for engraving. With no rule, all artwork
remains in the image. This stage does not encode power, speed, PPI or calibrated
machine coordinates into new Aurora jobs.

## Actual Windows print probe

`frontend/test-windows-capture.ps1` builds and prints one synthetic GDI page to
the exact capture queue after checking its driver and port names. It does not
use the default printer. On this host it produced:

- Capture `596198b5-5361-4dd1-8529-8e49b51b94b8`: 82,874 bytes of OpenXPS,
  delivered without a Save As dialog.
- A US Letter page, 816 by 1056 DIP, or 215.9 by 279.4 mm.
- A vector rectangle at (24,24)..(120,120) DIP: a 25.4 mm square at (6.35,6.35)
  mm, matching the requested geometry, plus a black fill and glyph run.
- No remaining capture-queue print jobs after receipt.

The nominal 0.001-inch GDI pen became 0.5 DIP (about 0.1323 mm) in this output.
That explains the diagnostic 0.2 mm threshold; it is not evidence about
CorelDRAW's hairlines. Native normalization and intake succeeded; artifacts are
in ignored `runtime/windows-gdi-capture-preview-native`. The CorelDRAW print
test is pending.

The first owner CorelDRAW capture arrived on a blank landscape Letter page while
the artwork used a 30 by 18 inch page. Queue defaults are now corrected, and a
fresh GDI capture confirms the actual 30 by 18 inch output with unchanged
one-inch geometry. A remaining legacy paper-ID conflict was corrected too.
After a full CorelDRAW restart, the owner confirmed the warning cleared.
The resulting `test.cdr` capture contains a 30 by 18 inch page, an exact one-inch
RGB red vector square and the `TEST` glyph run. Intake separated the square and
retained the text for engraving, with no review warnings. Artifacts are in
`runtime/coreldraw-bed-capture-1a0f`. This validates application capture and
layer separation for this test; it does not yet validate new laser jobs.
See [the findings and correction](../analysis/coreldraw-capture-20261017.md).

## Setup, removal and tests

Setup uses the existing Microsoft driver and refuses conflicting queue/port
settings. Administrative print-management access may be needed:

```powershell
.\frontend\install-capture-printer.ps1 -WhatIf
.\frontend\install-capture-printer.ps1
.\frontend\install-capture-printer.ps1 -Remove
```

Installation configures 30 by 18 inch media and backs up prior settings.
To inspect or reapply that configuration separately:

```powershell
.\frontend\configure-capture-printer.ps1
.\frontend\configure-capture-printer.ps1 -Apply
```

Configuration updates both PrintTicket and legacy GDI defaults. Explicit width
and length take precedence over the generic paper ID, which otherwise reports
Letter despite a 30 by 18 inch printable area. Prior native DEVMODEs are saved
alongside the PrintTickets. Verify the same interface X7 uses with:

```powershell
.\frontend\inspect-capture-printer.ps1
```

It should report custom paper at `3000 x 1800` hundredths of an inch and the same
printable area. Add `-Forms` to list the driver's advertised standard forms.

Removal refuses outstanding jobs and a port used by another queue. Stop the
receiver with Ctrl+C; files are retained. Eight Python loopback tests cover file
order, fragmentation, repeat jobs, invalid queue/length, truncation, abort,
duplicate files and exclusive loopback binding. Nineteen frontend checks include
native XPS/OpenXPS conversion with pixel and cutting-path comparison.

References: Microsoft [Add-Printer](https://learn.microsoft.com/en-us/powershell/module/printmanagement/add-printer),
[Add-PrinterPort](https://learn.microsoft.com/en-us/powershell/module/printmanagement/add-printerport),
[MXDW configuration](https://learn.microsoft.com/en-us/windows/win32/printdocs/mxdw-configuration-settings),
[native XPS output conversion](https://learn.microsoft.com/en-us/windows/win32/api/xpsobjectmodel_1/nf-xpsobjectmodel_1-ixpsompackage1-writetofile1),
and [RFC 1179](https://www.rfc-editor.org/rfc/rfc1179).
