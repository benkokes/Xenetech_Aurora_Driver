# Actual Windows CorelDRAW color capture tests

**Follow-up:** the edge loss described below is now fixed in the separate
semantic review reader. It reconstructs all original RGB channels exactly and
recovers 333 matched edge samples. A third actual mixed-artwork host capture
also passes extraction checks. Production colors remain held; see
[the October 20 results](semantic-color-coverage-20261020.md). The original
diagnostic reports below are retained unchanged.

At the owner's explicit request, the agent performed two host prints through
Corel X7's document/print API. `tools/CorelCapturePrint.cs` verifies the reference
hash, queue/driver/loopback LPR port, media, placement and idle Capture only state
before each single submission. It uses owned CDR copies, closes them and
restores the previous active document. No Windows default-printer change,
laser connection, live enable or XP networking change occurred.

The typed print interface came from Corel's installed VGCore interop assembly.
The supported [PrintSettings API](https://community.coreldraw.com/sdk/api/designer/25/c/printsettings?lang=cli)
also documents destination selection; exact X7 interface types and enum values
were inspected locally rather than assuming current-version signatures.

Both complete captures are preserved under
`captures/host-color-preferences-20261019/`:

| Drawing | Capture ID |
| --- | --- |
| Filled colors | 05c1fad7-ff76-4ed8-8b28-eaa63c75fb32 |
| Vector colors | 7af52dce-c37c-4e02-909e-8be60fee743a |

Both have the expected 167 DPI, raster 30 ips/45%, vector 1 ips/15%/1000 PPI,
Autostart OFF, full-color/As in document settings. They carry scalar defaults;
these are not new full classic Properties-snapshot tests. The comparison
identification palettes are supplied explicitly offline. The native experimental
reader preserves RGB and extracts paths for review; it remains outside production.

## Vector findings

All five actual X7 paths and RGB identities match XP exactly. Derived global,
unsorted, sorted, paused and disabled-color output matches all vector commands,
process values and nonpicture bytes. The X7 black marker retains 41 antialiased
samples that differ from XP, in accordance with the owner's preference to keep
X7's appearance. Exported drafts retain these native samples; they are not
claimed to be completely byte-identical to XP picture payloads.

## Raster finding requiring a fix

The filled drawing produces a 355 x 105 RGB crop with **21 RGB values** from
four original fill colors. X7's rendered edges blend with the white background.
Exact RGB classification drops those samples: diagnostic Black becomes 20 x 20,
Red/Blue become 187 x 20, with some origins displaced by 6 native units.

Of 795 unmatched samples, 400 are pure orange and 395 are blended edge samples.
Some edges also belong to the intentionally omitted orange artwork. Assigning
nearest palette colors or keeping all unknown samples would not establish parity.
Original fill-brush identity must be retained through rendering to produce
coverage layers with the X7 edge appearance. The actual source has flat geometry
fills, no images or gradients, so this can be addressed semantically without
inventing a generic bitmap quantization rule.

The immutable verification report and marked diagnostic artifacts are in
`runtime/xp-color-raster-preferences-20261019/host-capture-verification-r2/`.
The reproducible verifier checks inputs and comparisons with sockets denied.
The earlier model's four exact XP file comparisons remain valid for explicitly
classified binary inputs; this real render demonstrates why those inputs cannot
yet be obtained by simply matching flattened RGB samples.

JobServer remains **Capture only**, queue empty, no live session. Production
UseColors remains held. The tests are complete; color-layer rendering is the
next implementation task. Existing product regression remains 184 Python and
31 native tests passed; no physical per-color result is implied.
