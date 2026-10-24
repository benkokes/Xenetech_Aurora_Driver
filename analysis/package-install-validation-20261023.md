# Windows 10 installation/removal validation

The owner selected installer testing on this Windows 10 PC first, then closed
all Aurora JobServer windows and the CorelDRAW Print dialog. This is an existing
development-driver environment, not a clean Windows 11 installation.

Preview 6 passed a real administrator install → uninstall with `-RemovePrinter`
→ reinstall cycle. The application was left installed at
`C:\Program Files\AuroraJobServer\AuroraJobServer.exe`, with a Start-menu shortcut.
No receiver was started and no physical job/device connection was made.

The cycle verified all installed application hashes and the shortcut target,
printer identity and loopback port. Uninstall removed the application folder,
shortcut and selected printer queue while retaining the port as documented.
Reinstall recreated the application/shortcut/queue. The installed executable
passed its frozen offline GUI/codec/native-intake checks after each installation.
The existing machine certificate trust was used; no new signer was imported.

Before mutation, the existing queue metadata, print configuration, default
printer and exact global/per-user DEVMODE bytes were backed up. Global defaults
were restored during the elevated cycle and per-user defaults afterward under
the owner's original XPC\xws account. Both hashes match the originals exactly:
`a7a10520951e2a5d0d44e3d76f7e33a6c02a21fb6797f48f65e59a1fb43a0cb0`.
All 18 existing per-user JobServer files, including captures/history/settings,
retain identical paths and SHA-256 values. The queue is empty and the installed
application remains closed at completion.

Evidence is immutable under `runtime/package-install-validation-20261023/`:

- `install-cycle-result.json` and `administrator-transcript.txt`
- `installed-self-check-first.json` / `installed-self-check-reinstalled.json`
- `devmode-backup/`, `devmode-after/`, printer/default-printer snapshots
- `user-data-verification.json` and `final-verification.json`

The owner previously verified the unpacked preview's real CorelDRAW capture and
enabled startup, with old captures staying local and no delivery jobs created.
A fresh capture through the newly recreated queue/installed application is the
next quick functional check. Actual Windows 11, a clean-driver environment and
public release signing remain outstanding. There is no need to repeat the
per-color physical acceptance test merely because the identical bytes were installed.

The installed executable was subsequently opened as normal xws with
`--capture-only`; process-path and status readback confirmed Program Files,
pipeline 4, Capture only, and no error. The owner was asked for one fresh local
CorelDRAW print and a Properties check. The owner confirmed "Properties opens;
print shows Captured locally." New capture `2b5e7fe9-99f2-447a-8bd8-9454952b45e3`
was independently checked for receipt/source integrity and readable settings.
The installed Program Files process remains Capture only, pipeline 4, no error.
Evidence is `installed-corel-capture/verification.json` under the test directory.
The Windows 10 existing-driver installation/removal/reinstallation and installed
Corel Properties/capture checks are complete. No physical job was sent.
