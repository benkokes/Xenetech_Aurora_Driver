# XP output-mode comparison and Raster Only integration

The owner completed the three offline captures and restored **Both Raster and
Vector**. Originals were copied, hashed and retained in
`captures/xp-output-modes-20261018`; decoded output is in
`runtime/xp-output-modes-20261018`. XP was not reconnected and no laser job was
sent by this work. Working resolution remains **167 DPI**.

| XP mode | Raw job bytes | Raster | Vector |
|---|---:|---|---|
| Both | 6,341 | TEST, 140 × 42 pixels at (978,720) | One closed square |
| Raster Only | 6,201 | Identical pixels, dimensions and origin | None |
| Vector Only | 286 | None | Identical square coordinates |

Raster signal SHA-256 is
`e4c7c9fbc0544ed6d949ce5a56e524d78934d1bebb3d648749aee9d29452176b`
for Both and Raster Only. The square vertices are
(876,1212), (1878,1212), (1878,2214), (876,2214), then closure. Raster Only
does **not** rasterize the omitted red hairline in this controlled reference.
Vector Only does **not** turn the filled TEST lettering into cutting outlines.
All initialization/finish commands remain identical. Raster settings are
30000/45; vector settings are 1000/15/1000 PPI; Autostart is off.

Source hashes:

- Both: `3824645713ed16417e8eab857a9fec569e2bcb673234acf3fdb91717b936ab34`
- Raster: `0ff1da58d78b41d194b43b961dbb3bcf6932c32e223ed0e419128fe9c3fcbb24`
- Vector: `a8055d08a77382df1420ab01f3f602f04a802561b28cded36f2b4190ec32941a`

## Implementation and checks

The encoder now explicitly selects Both, Raster Only or Vector Only while
retaining the original source scene. Raster Only omits the vector process/path
block; Vector Only omits the raster process/picture block. Empty selected
content is rejected rather than submitting a meaningless job.

Using the independently decoded **XP Both pixels and coordinates** as input,
all three encoder outputs exactly match the three captured XP jobs byte for
byte after removing the offline draft marker. This verifies output selection,
headers, settings and finish commands. It does not claim the X7 renderer's glyph
pixels equal XP's: the owner's earlier choice to preserve X7 appearance remains.

Raster Only is enabled in the complete-settings backend. It uses the existing
compressed-raster transfer profile; its output contains a validated raster and
no vector cutting commands. A native intake → encoder → exactly-once delivery
test passes against the loopback controller simulator. The JobServer details
now display Output mode, so configured but unused vector settings are clear.
The actual CorelDRAW X7 Raster Only capture also passed. Capture
`13039cc7-cb2d-461b-ace9-ac5055936486` contains the complete Raster Only settings
snapshot, 167 DPI, raster 30 ips/45%, and Autostart off. Offline conversion
preserves the accepted X7 TEST raster exactly (140 × 41 pixels, pixel SHA-256
`bf712adcea801b20ef978d188ceba676f71e05e931e88f89b90e9e8817ef17b5`), including
its position and process commands. Its finish section is only
`PU\r0. 0. V\rEND_PLOT\r`, with no vector power/speed/PPI block or cutting
paths. The capture receipt's source hash/length passed integrity checks.
Verification is in `runtime/coreldraw-raster-only-check/verification.json`.
The owner restored Both without printing again. JobServer remains Capture only;
this check did not connect to or operate the laser.

No native driver/UI package change was needed: r9 already carries mode choices
in its complete per-print snapshot and Custom carrier. Windows' installed
provider preserves both pure mode selections in DEVMODE roundtrips. Six total
native snapshot cases pass; queue defaults remain unchanged.

All **132 Python tests** pass, including eight new mode checks. They cover
independent XP byte equality, no unwanted content, source-scene immutability,
selected-content emptiness, exact-once loopback delivery, and Vector Only
remaining blocked before rendering or any socket connection. Report:
`runtime/output-modes-regression.log`. The idle desktop JobServer was reloaded
with the new backend in Capture only; captured history was not replayed.

## Vector Only delivery remains held

The offline vector job encoding is now verified, but its on-wire framing is
not. The current sender/wire planner still rejects jobs without a CG raster.
No guard was removed merely because the raw job is readable.

Static JobServer analysis corroborates a different conversion path. Its raster
converter returns 0/8 to the jobtype-5 branch at 0x00419199. Return 9 maps to
the Nothing to Convert handler, with the caller restoring the original input
path at 0x0041a384–0x0041a3a6. This does not establish the controller's vector-only
jobtype/envelope or completion exchanges. A legacy vector-only protocol capture
is still needed before enabling its delivery. The original binary was read,
never executed on the host. See
`runtime/xp-output-modes-20261018/vector-transfer-static-evidence.json`.

Current evidence/state:
`runtime/xp-output-modes-20261018/verification.json`,
`runtime/output-mode-native-roundtrips`, and the preserved capture manifest.
No new live-test permission has been requested or granted.
