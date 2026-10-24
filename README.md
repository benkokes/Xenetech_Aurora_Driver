# Xenetech Aurora JobServer

Print from CorelDRAW to a Xenetech Aurora laser engraver over Ethernet, using a modern Windows computer.

This community-developed replacement provides a Windows printer and a small **JobServer** application. You choose the engraving and cutting settings in the printer's Properties window, then use CorelDRAW's normal **Print** button. An XP computer or virtual machine is not needed for everyday printing.

**Current release: 0.6.0 development preview.** This is an independent project, not an official Xenetech release.

Jump to: [Download](#1-download-and-extract) · [Install](#2-install) · [First print](#4-make-a-first-print-without-running-the-laser) · [Everyday use](#everyday-use) · [Troubleshooting](#troubleshooting) · [Uninstall](#remove-or-update-the-preview)

## Read this first

- **Tested:** Windows 10, 64-bit, with CorelDRAW X7 and the project's Aurora engraver. Installation, removal, reinstallation, printing, and several engraving/cutting features have been tested.
- **Windows 11:** a target for the project, but installation and operation have not yet been verified on Windows 11. Other drawing programs and Aurora controllers also need testing.
- **JobServer normally starts with “Laser printing enabled.”** A new Print command can send work to the machine. Select **Capture only** whenever you want to check artwork without sending it.
- **Autostart is a separate printer setting.** With Autostart Off, use the laser's Start button when ready. With Autostart On, an arriving print may start the machine immediately. Use **Off** for your first test.
- Use material, speed, power, focus, and extraction procedures appropriate for your machine. Example settings from somebody else's test are not material recommendations.

The preview uses a development signing certificate. Installation requires an explicit trust decision, explained below. It is not yet a publicly signed production driver.

## What you need

- A Xenetech Aurora engraver connected by Ethernet.
- A 64-bit Windows computer and an administrator account for installation.
- CorelDRAW. X7 is the version tested so far.
- The laser's network address, also called its **IP address**.
- The ready-to-use Windows x64 ZIP from this repository's **Releases** section.

Python and other programming tools are **not required**. They are included in the ready-to-use package.

Only one JobServer should control the laser. Close other copies, including the old XP JobServer, before using this one.

## 1. Download and extract

1. Download the Windows x64 release ZIP. The current package is named:

   ```text
   AuroraJobServer-0.6.0-preview6-win-x64.zip
   ```

2. Right-click the ZIP and choose **Extract All**.
3. Open the extracted folder containing **Setup.ps1**. It should also contain an `app` folder, a `driver` folder, and `AuroraLocalTest.cer`.
4. Keep those files together. Do not run the installer from inside the ZIP or move just the application EXE out of its folder.

Download the release package, rather than GitHub's **Code → Download ZIP**, which downloads the project source code.

## 2. Install

Keep the laser disconnected or switched off during installation. Close JobServer and any open CorelDRAW Print/Properties windows.

### Open an administrator PowerShell window

1. In File Explorer, copy the full path of the extracted folder containing `Setup.ps1` from the address bar.
2. Open the Windows Start menu, search for **Windows PowerShell**, and choose **Run as administrator**.
3. Accept Windows' administrator prompt. If a password is required, enter it in Windows.
4. Change to the extracted folder. For example:

   ```powershell
   cd "C:\Users\YourName\Downloads\AuroraJobServer-0.6.0-preview6-win-x64"
   ```

   Replace the example path with the folder path you copied. Keep the quotation marks.

### Check the package

Copy and run this command:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Setup.ps1 -ValidateOnly
```

It should report:

```text
Package hashes, certificate identity and local printer configuration validated. No changes made.
```

If validation fails, stop and save the error message. Download a fresh copy of the release if a file is missing or changed.

### Install the preview

**This command explicitly trusts the project's development certificate on this computer.** It adds the certificate to Windows' machine-wide Root and TrustedPublisher stores so Windows can accept this preview's printer package. Only do this for a package you obtained from this project's release and intend to trust.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Setup.ps1 -TrustDevelopmentCertificate
```

The installer creates:

- **Aurora JobServer** in the Start menu.
- A printer named **Aurora JobServer (Test Capture)**.
- The application in `C:\Program Files\AuroraJobServer`.

Installation itself does not start JobServer or send work to the laser.

The commands above allow the script for that PowerShell invocation; they do not permanently change your execution policy. See [Microsoft's execution-policy documentation](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies?view=powershell-5.1) for details. A work computer may have additional administrator policies.

<details>
<summary>Development certificate details</summary>

- Name: **Aurora JobServer Local Development**
- Thumbprint: `2A5AC9C0A94B0B3AD79BD7C30EF897ADFD06F75F`
- Expiration: **January 16, 2027**

If the certificate has expired, obtain an updated package from the maintainer. The ZIP contains the public certificate, not its private signing key.

</details>

## 3. Set the laser's network address

1. Open **Aurora JobServer** from the Start menu.
2. Immediately click **Capture only** while setting things up.
3. Enter the laser's actual IP address in **Laser IP**.
4. With the laser connected and powered on, click **Check connection**.

The expected result is **Laser responded**. This check reads the machine's status; it does not submit an engraving job.

On a fresh installation, the address may be `127.0.0.1`. That refers to the computer itself. Replace it with the engraver's address before attempting live printing.

Use the address from your machine's network settings or your previous working setup. Ask the person who manages your network if you do not know it. The computer and engraver need to be on a network where they can reach each other.

Leave JobServer in **Capture only** for the next step.

## 4. Make a first print without running the laser

1. In CorelDRAW, open a small familiar drawing. Text and a one-inch square with a **hairline** outline make a useful first check.
2. Open **File → Print**.
3. Select **Aurora JobServer (Test Capture)**.
4. Open **Properties** or **Preferences** and check the settings below.
5. Accept the Properties window with **OK**, then use CorelDRAW's final **Print** button once.

| Setting | First-check choice |
| --- | --- |
| Plate size | 30 × 18 inches |
| Resolution | 167 DPI |
| Output mode | Both Raster and Vector |
| Focus option | No Focus at Start; focus the machine yourself before a real job |
| Autostart | Off |
| Use Color Settings | Off for this first check |
| CorelDRAW page selection | Use printer default |
| CorelDRAW layout | As in document, 100% size |
| Speed and power | Settings you already know are suitable for your machine and material |

Leave other advanced options at their defaults for this check.

The JobServer window should show the drawing as **Captured locally**. Nothing is engraved in Capture only. Select the job to inspect its settings.

**The printer's name includes “Test Capture,” but it is also the live-printing queue. JobServer's mode determines whether a new print is saved locally or sent to the machine.**

## 5. Print to the laser

1. Prepare the material, focus, and machine as you normally would.
2. Confirm the intended speed, power, output mode, and **Autostart Off** in printer Properties.
3. In JobServer, click **Enable laser printing** and accept its confirmation.
4. Submit **one fresh print** from CorelDRAW.
5. If the laser displays the job ready, press its normal **Start** button once when ready.
6. Check the finished piece and the result in JobServer.

The capture from the previous step is not automatically sent when you enable printing. Submit a fresh print to send a job.

If nothing appears to happen, check JobServer and the laser's display before printing again. Repeated Print commands can create additional jobs.

JobServer shows **Completed** and **Duration** when it receives the corresponding completion report. Duration is the time reported by the laser, rather than the time spent waiting in the computer's queue.

## Everyday use

1. Open **Aurora JobServer** from the Start menu. Normal startup enables delivery for new prints.
2. Prepare the machine and material.
3. In CorelDRAW, choose the Aurora printer, check Properties, and click Print once.
4. Use the machine's Start button if Autostart is Off.

Keep JobServer running while printing. You do not need to open it again for each job.

Click **Capture only** whenever you want to inspect a print without sending it. On the next normal launch, printing is enabled again. Old captured jobs are not replayed.

The optional **Open JobServer when I sign in** checkbox starts the application when you sign in to Windows. The same enabled-by-default behavior applies.

### Engraving and cutting

| Term | Meaning |
| --- | --- |
| Raster engraving | Engraves filled shapes, lettering, and supported image artwork by scanning across the surface. |
| Vector cutting | Follows eligible hairline outlines and curves. |
| Raster Only | Engraves the raster artwork and omits the cut paths. |
| Vector Only | Sends the eligible hairline paths without raster engraving. |
| Both Raster and Vector | Engraves the raster artwork, then follows the cut paths. |

**Hairline width determines which outlines become cuts. Color alone does not make a line a cut, and cuts do not have to be red.**

If an outline is too thick, change it to **Hairline** in CorelDRAW and print again. In Vector Only mode, a drawing without eligible paths shows **Nothing to cut — not sent**.

### Different settings for different colors

For supported per-color artwork:

1. In Properties, turn on **Use Color Settings**.
2. Open **Color Settings**.
3. Enable the colors you want to use and set each one's power, speed, and PPI.
4. Use exact RGB colors from that table in CorelDRAW. PPI applies to vector cutting.
5. Keep **Sort Color Vectors** On and **Pause Between Colors** Off for the tested workflow.

This preview supports per-color vector output and per-color raster/mixed output at **167 DPI**. Per-color raster artwork must use opaque solid fills or lettering. Bitmaps, gradients, and transparency are not supported in per-color raster mode.

A color row applies to both engraving and cutting that use that color. If they need different settings, give them different colors. Enter whole-number power percentages. The preview accepts selected raster speeds up to 31 inches per second and selected vector speeds up to 15 inches per second; these are software limits, not recommended operating speeds.

For predictable results, use colors from the table. Raster colors outside the table are omitted; an unmatched vector color uses the White row's settings if that row is enabled. Check every color used by the drawing before sending it.

Keep **Bottom-Up** and **Invert Raster Output** Off when using per-color raster or mixed output.

### Bottom-up engraving

At 167 DPI, **Bottom-Up Engraving** is supported for ordinary raster output with **Use Color Settings Off**. The image stays upright while the scan begins at its lower edge and progresses upward.

## What is supported in this preview?

| Feature | Current status |
| --- | --- |
| Normal raster engraving and mixed raster/vector jobs | Physically tested at 167 DPI |
| Vector Only, using hairline outlines regardless of color | Physically tested at 167 DPI |
| Per-color vector power, speed, and PPI | Physically tested at 167 DPI |
| Per-color raster and mixed jobs using opaque solid fills/text | Physically tested at 167 DPI |
| Bottom-up ordinary raster engraving | Physically tested at 167 DPI |
| Printer Properties and installed CorelDRAW capture | Tested on Windows 10 / CorelDRAW X7 |
| Installation, removal, and reinstallation | Tested on the Windows 10 development PC, which already had the development driver |
| Windows 11 or a clean-driver installation | Not yet verified |
| Cylindrical/rotary engraving | Not available for live printing; no rotary hardware validation |

Some Properties controls are present to match the original driver, but their output is not yet supported or physically validated. Use **167 DPI**, the **30 × 18-inch plate**, and the documented workflow. Leave automatic focus, plate rotation/mirroring, offsets/centering, rubber-stamp features, bitmap processing options, and other advanced changes at their defaults. A job using an unsupported combination may be held rather than sent.

## Troubleshooting

### “Running scripts is disabled on this system”

Use the complete `powershell.exe -NoProfile -ExecutionPolicy Bypass -File ...` commands in the installation section, rather than double-clicking the script or typing only `.\Setup.ps1`.

If your workplace still blocks the command, ask its administrator. Save the exact error message.

### The printer is missing, or the page still shows Letter

Close and reopen CorelDRAW's Print dialog and select the Aurora printer again. If necessary, save the drawing, fully exit CorelDRAW, and reopen it. Check **Use printer default**, **As in document**, and **100%** size.

### “Output doesn't fit on media”

Check that both the document and printer use the supported 30 × 18-inch page. Keep original size and verify the drawing is inside the plate. Do not use Fit to page to hide a size problem when dimensions matter.

### The drawing appears in JobServer, but the laser does nothing

Read the job's status:

| Status | What to do |
| --- | --- |
| Captured locally | This print was received in Capture only. When ready, enable printing and submit a fresh print. |
| Held / Conversion failed | Select the job and read its explanation. Correct the artwork or unsupported settings before submitting a fresh print. |
| Nothing to cut | Use hairline outlines, and check that the intended colors are enabled. |
| Nothing to print | Check that the intended artwork colors are enabled and have nonzero power. |
| At laser — awaiting report | Check whether the machine is waiting for Start. Do not submit another copy just because it is waiting. |
| Check physical outcome | Follow the instructions below before attempting another send. |

### “An earlier delivery is unresolved” / “Check physical outcome”

This can happen after an interrupted or stopped job. JobServer needs to know what happened before it can send more work.

1. Check the machine and the piece. Make sure the machine is idle.
2. Select **Capture only**.
3. Select the affected print in JobServer.
4. Click **Record physical outcome…**.
5. Enter the outcome that actually occurred:

   | Enter | Meaning |
   | --- | --- |
   | `completed` | The job finished. |
   | `not_started` | The job never ran. |
   | `stopped` | It started but was stopped before finishing. |

6. Describe what you observed.

Recording the outcome does not resend the job. If you are unsure what happened, leave it unresolved. Do not delete the delivery record to bypass this check.

### A second copy will not open, or the receiver address is already in use

Close other JobServer copies, including any unpacked or development copy. Use **Aurora JobServer** from the Start menu after installation.

### A `set_xyup_feed` token warning appears

This warning has appeared on the tested controller with both the original XP workflow and the replacement. Completed test pieces have been accepted despite it. Inspect the finished job; report missing work, different warnings, or unexpected behavior rather than assuming every warning is harmless.

### Where are settings, history, and logs?

Paste this into File Explorer's address bar:

```text
%LOCALAPPDATA%\AuroraJobServer\state
```

The application log is `jobserver.log`. Saved print files can contain your artwork.

When reporting a problem, include the package version, Windows version, CorelDRAW version, error text, JobServer mode, and relevant printer settings. Only share artwork or logs you are comfortable making public in a GitHub issue.

## Remove or update the preview

1. If enabled, turn off **Open JobServer when I sign in**.
2. Close JobServer and any printer Properties windows.
3. Open an administrator PowerShell in the extracted release folder, as described above.

To remove the application and its printer queue:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Uninstall.ps1 -RemovePrinter
```

To remove only the application while keeping the printer queue:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Uninstall.ps1
```

The uninstaller keeps your history/settings, the Windows driver-store package, the local printer port, and the trusted development certificate. It does not return the computer to a completely clean pre-installation state.

This preview does not automatically overwrite an existing installation. Follow the next release's upgrade instructions. If instructed to replace the application, uninstalling without `-RemovePrinter` keeps the existing queue for the next installation.

## Optional application check

From the extracted release folder, run:

```powershell
.\app\AuroraJobServer\AuroraJobServer.exe --self-check-report .\self-check.json
```

After a few seconds, open `self-check.json` in Notepad. A successful check contains `"state": "passed"`. Use a new report filename if that file already exists. This check does not start the print receiver or connect to the laser.

For startup directly into Capture only after installation, run this in PowerShell:

```powershell
& "$env:ProgramFiles\AuroraJobServer\AuroraJobServer.exe" --capture-only
```

Engineering history is kept separately in [DEVELOPMENT-NOTES.md](DEVELOPMENT-NOTES.md).
