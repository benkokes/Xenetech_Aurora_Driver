# VirtualBox MCP setup — October 20, 2026

Installed `mb85/mcp-virtualbox` v0.4.1, the latest published release at setup,
as the enabled Codex MCP server `virtualbox`.

## Installation

- Binary: `runtime/virtualbox-mcp/v0.4.1/mcp-virtualbox.exe`.
- Windows AMD64 release archive SHA-256:
  `b161528b3b2ffc422deee420f9e2a5aded6bca8e1c360ed5ce2dc57651756afb`.
- The archive matched both GitHub's asset digest and the release's
  `checksums.txt` before extraction and execution.
- Version output: `mcp-virtualbox 0.4.1`.
- Pinned source, release README, license, checksums, and archive are retained
  alongside the executable under the ignored `runtime` directory.
- Registration is in `C:\Users\xws\.codex\config.toml`. The preceding config is
  backed up at `runtime/virtualbox-mcp/codex-config-before-setup.toml`.

The server is registered with an absolute executable path, the explicit
`VBoxManage.exe` path, a project screenshot directory, a 30-second operation
timeout, and `VBOXWEB_AUTOSTART=true`. It is not placed in read-only mode in
the persistent configuration. Existing Codex entries remain configured.

## Verified

An MCP stdio client initialized the installed executable, discovered all 41
tools, listed the registered VMs, queried `LaserLaptop`, and received a PNG
screenshot through `vm_screenshot`. The image was inspected and shows the XP
screensaver at 1110 × 725. The verification used `VBOX_READONLY=true` only for
the smoke-test process.

- Installed VirtualBox: 7.0.14 r161095.
- Target: `LaserLaptop`, UUID `86b4c234-1ba8-4bf6-b47b-49f93e525f24`.
- Target state: running.
- Guest Additions: 7.0.14 r161095.
- NIC 1 cable: disconnected.
- Other registered VM: `Win10_64`, powered off.

Artifacts: `runtime/virtualbox-mcp/verification.json`, `tool-catalog.json`,
`xp-vm-info.json`, and `screenshots/setup-xp.png`.

No print, guest command, guest file transfer, VM power change, or network change
was performed. A pointer movement was verified after the owner's explicit
approval. Guest execution and copying still require valid XP credentials
and have not been verified. No guest password was requested or changed.

## Mouse service approved and verified

The server uses `vboxwebsrv` for mouse events. Its default autostart changes
VirtualBox's global web-service authentication to `null` and starts a service.
Automatic approval review rejected that persistent authentication change and
detached service launch. The rejected command did not run. Authentication was
subsequently confirmed to remain `VBoxAuth`, and there was no listener on
port 18083.

The owner subsequently explicitly selected **Enable localhost mouse control**.
After that approval, the service was started in a hidden window, bound only to
`127.0.0.1:18083`, with anonymous authentication and a 300-second session timeout.
The listener address was verified. A real MCP `vm_mouse_move` call succeeded at
`(640, 400)` without clicking, typing, or printing. The XP VM remained running
with NIC 1 disconnected. VirtualBox web-service authentication is now `null`,
as approved; local programs can also access this control service.

Codex registration now has `VBOXWEB_AUTOSTART=true` and the explicit loopback
endpoint, so the upstream server can restart the service on demand for mouse
operations. No Windows sign-in startup entry was added. The manual setup check
continues to use `VBOXWEB_AUTOSTART=false` so it verifies an existing service
without silently changing authentication or starting one.

## Client refresh

The new server was confirmed by `codex mcp get virtualbox --json`. Its tools
are not present in this already-running chat's tool inventory. Restart the
Codex app to load the updated MCP configuration; no VM restart is needed.

Sources:
- <https://github.com/mb85/mcp-virtualbox/releases/tag/v0.4.1>
- <https://github.com/mb85/mcp-virtualbox#requirements>
- <https://learn.chatgpt.com/docs/extend/mcp?surface=cli>
