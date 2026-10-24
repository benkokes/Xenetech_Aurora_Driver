Aurora JobServer 0.6.0 development preview — Windows x64

Development preview. Tested on this project's Windows 10 / CorelDRAW X7 host.
Windows 11 and clean-machine install/uninstall have not yet been validated.
This is not a publicly signed release. Do not redistribute it as a finished driver.

The app bundles Python and Tk. A separate Python installation or Codex is not
required to launch app\AuroraJobServer\AuroraJobServer.exe. Windows supplies
.NET Framework 4.x and the print spooler used by the native XPS intake/driver.
Keep the entire app folder together. Do not launch while the development
JobServer is running: both use the same local printer port. Device-lock records
in the development workspace and installed app are separate; do not mix senders.

Validation without installation (64-bit Windows PowerShell):
  .\Setup.ps1 -ValidateOnly
Offline application check (writes a new report, no receiver/device access):
  app\AuroraJobServer\AuroraJobServer.exe --self-check-report C:\path\new-report.json

Installation: review these scripts, close existing JobServer, and use an
administrator Windows PowerShell to run .\Setup.ps1. The driver uses the local
development certificate 2A5AC9C0A94B0B3AD79BD7C30EF897ADFD06F75F, expiring
January 16, 2027. If it is not already trusted, Setup stops. Only after deciding
to trust this development signer, rerun with -TrustDevelopmentCertificate;
this explicitly adds the public certificate to machine Root/TrustedPublisher.
No private key is included. A production public driver signature remains work.

Setup installs the application under Program Files\AuroraJobServer, adds a Start
menu shortcut and the Aurora JobServer (Test Capture) printer. Existing printer
and port names must match. It never starts laser delivery or prints a job.
Application history/configuration reside in %LOCALAPPDATA%\AuroraJobServer\state.
By owner request, normal launches enable laser printing for NEW submissions.
Existing captured jobs and old sessions are never replayed. If a prior delivery
is unresolved, the guard leaves printing held in Capture only for resolution.
Use the Capture only button for offline work, or launch with --capture-only.
On a fresh installation, enter your laser's IPv4 address in JobServer before
checking the connection or enabling laser printing; the initial address is
loopback, not a factory or discovered engraver address. Click Capture only to
change the address, then Enable laser printing when ready. Job-level Autostart
still controls whether the machine requires Start or starts on arrival.

Supported/accepted normal printing: global raster/mixed 167 DPI, Vector Only
167 DPI, per-color Vector Only 167 DPI, bottom-up global raster 167 DPI, and
per-color raster/mixed 167 DPI (three raster colors plus two vector colors
physically accepted October 23, 2026). Individual PPI/power measurements were
not calibrated; the owner accepted the completed appearance and placement.
Cylindrical output remains offline only: no rotary hardware validation exists.
Per-color raster currently requires opaque solid fills/text, 167 DPI, and Pause,
Bottom-Up and Invert off. Bitmaps/gradients/transparency in per-color output are
held; ordinary global bitmap printing is separate. Only selected hairline paths
become vectors, regardless of their RGB color. Palette PPI affects vectors.

Uninstall: first turn off Start with Windows in JobServer and close it. Run
.\Uninstall.ps1 as administrator; -RemovePrinter optionally removes the matching
queue. It retains user history, driver store, loopback port and certificate trust.
Preview updates do not overwrite an existing installation automatically.

Build tools: PyInstaller (https://pyinstaller.org/en/stable/), Python, Tcl/Tk.
Bundled notices accompany the package. The manifest records all shipped hashes
and the exact packaging wheels. Personal captures, saved controller configuration, XP
binaries and signing private keys are excluded from this distribution.
