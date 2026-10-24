# Per-color raster/mixed acceptance and standalone package

The owner accepted the three-color raster and two-color vector sheet on October
23, 2026: "All three raster colors and both cuts look correct." Normal 167-DPI
per-color Raster Only and Both now use the native semantic coverage reader and
the palette carried in each print's complete preferences snapshot.

## Evidence

- A new actual XP capture is archived at
  `captures/xp-color-mixed-preferences-20261022/inbox/Default.jbs`, SHA-256
  `e2aeadb8e62baaa4d988c6fd4da19abbee2f118e01b968a64bb34cde2d61aa5e`.
  The observed case has Blue omitted: two raster regions and three vector paths.
  It must not be described as the requested all-enabled case. The complete raw
  composition matches byte for byte, apart from the mandatory offline marker,
  using the independently saved CDR geometry and earlier measured vector paths.
  CG conversion preserves commands, geometry and samples. Report:
  `runtime/color-raster-mixed-integration-20261022/xp-boundary-r1/verification.json`.
- The owned X7 graphic is
  `runtime/color-raster-mixed-integration-20261022/acceptance-artwork-r1/Aurora-Per-Color-Acceptance.cdr`.
  It was printed once into Capture only. Its source has SHA-256
  `2a0562dedafb8e01f48963223f89c63f15ed4a0b9c42ed44fa78588e787d0560`.
  An explicitly synthetic ticket selected the test palette; this was not a claim
  about new Properties selections. Native reconstruction has zero channel error.
- Staged CG: 4,790 bytes, SHA-256
  `fd0857825e3477d707a586af984edd8655abff73303a2465f5cd5de554010014`.
  Black/Navy/Lime raster: 30 ips, 45/35/40%. Red vector: 1.5 ips/10%/750 PPI;
  Blue vector: 2 ips/5%/500 PPI. Three separate raster regions retain the blank
  rows between lettering and fills. Two hairline cuts follow them. Autostart off.
- The first physical attempt was denied by the sandbox before upload. It remains
  archived as delivery_failed/upload_started=false. It was not silently retried.
  The owner gave fresh readiness for a new recorded attempt outside the sandbox.
- Successful job `542d6d90-825a-457a-8607-1b8d8df78253`, delivery
  `f21ded58-827c-49e7-8d3b-67ea2dc18124`, title `Print_d1ccec9a`: one upload,
  end code 0, 28.39 seconds, known set_xyup_feed warning only. The full 5,136-byte
  transmitted stream exactly matches the reviewed wire plan, including the
  5,002-byte upload request. Shared guard cleared. The owner pressed Start and
  accepted the result. There are no calibrated individual power/PPI measurements.
  Immutable acceptance:
  `runtime/color-raster-mixed-integration-20261022/staged-mixed-test-r1/physical-test-r2/physical-acceptance.json`.

## Normal scope

Pipeline 4 enables per-color vector, raster and mixed at 167 DPI. Source brushes
must be opaque solid fills/text. Coverage is extracted semantically, rather than
guessing a color from antialiased RGB edges; appearance is independently checked
against the X7 raster. Raster output uses exact palette identities, omits
unmatched colors as XP did, and preserves selected power/speed. Vector PPI uses
the selected color. Hairline eligibility remains independent of RGB.

Color raster/mixed with Pause, Bottom-Up or Invert remains held. Bitmaps,
gradients and transparency in per-color mode remain held. Global bitmap and
global bottom-up support are unaffected. Selected raster speed is limited to
31 ips and selected vector speed to 15 ips. All-disabled/zero-exposure color
prints produce a durable local Nothing to print outcome with no device send.

## Package

`packaging/Build-Package.ps1` creates an x64 one-folder frozen application,
the existing signed r11 printer driver, a precompiled installer helper, public
development certificate, Setup/Uninstall scripts, hashes and dependency notices.
Python/Tk are bundled; Codex's runtime is not needed on the destination.
Resources and writable per-user state are separated. The owner's subsequent
request changes normal desktop startup to enabled for new prints. Old captures
and old live-session files remain held. An unresolved delivery guard leaves the
window in Capture only for resolution; `--capture-only` explicitly starts offline.
A fresh installation starts with loopback as its address and needs its laser IP
configured before printing. Job-level Autostart is unchanged.

Build 1 revealed sandbox Tcl/Tk discovery failure; it is not a valid distribution.
Build 2 failed before freezing due to workspace dependency read permissions.
Build 3 fixed Tk and passed the frozen offline dependency check from outside the
workspace, as well as Setup -ValidateOnly. Build 4 includes accepted color modes.
See runtime package build/check logs for the final artifact validation.

All 264 checks passed in the final outside-sandbox regression run, including WSH
fixtures; earlier failures were stale feature-hold expectations and sandbox WSH
initialization. Enabled-start lifecycle tests were added afterward and are
recorded separately. The owner restarted the source application, and readback
confirmed pipeline 4 / Capture only before requesting the new startup default.
The default-enabled change takes effect on the next launch; it does not force
the existing window into live mode or resend anything.

Final artifact: `dist/AuroraJobServer-0.6.0-preview6-win-x64.zip`, 14,514,447 bytes,
SHA-256 `794aa6498329fe48edf66194ec4fdb65bf108cc3ebb4b16a80518568fce52321`.
It includes the requested enabled-on-launch default. Seventeen desktop lifecycle
checks passed after that change, including startup routing/no replay and unresolved
guard behavior. The frozen executable's offline check from TEMP passed; the
extracted ZIP passed Setup -ValidateOnly. No actual package installation occurred.
Earlier preview ZIPs are superseded and should not be used.

This remains a development preview: clean installation/uninstallation and actual
Windows 11 validation remain. The development certificate expires January 16,
2027 and requires explicit trust on other PCs; it is not a public release signer.
No signing private key, XP binaries, private capture data or live configuration
is shipped. No package installation or further physical print is authorized or
performed by these build/validation steps.
