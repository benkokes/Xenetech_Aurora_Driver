# CorelDRAW 11 comparison preparation

The owner confirmed that XP uses CorelDRAW 11 and supplied `H:\test.cdr`.
`H:` maps to `\\arkhive\Hardware`. A read-only snapshot is preserved in ignored
`reference/artwork/test-source.cdr`; SHA-256
`ef75b5b4355059f4605bbf3416ff229d3d3633bbd45e3ea3b55fc8b4f13cfefd`.

Installed CorelDRAW X7 17.2.0.688 COM automation opened the separate snapshot,
saved with `StructSaveAsOptions.Version = 11` and overwrite disabled, reopened
the output, then restored the owner's existing document tab. No source artwork
edits or printing occurred. Official API references:

- https://community.coreldraw.com/sdk/api/draw/17/e/cdrfileversion
- https://community.coreldraw.com/sdk/api/draw/17/m/document.saveas
- https://community.coreldraw.com/sdk/api/draw/17/m/application.opendocument

Output `reference/artwork/test-corel11.cdr` is 20,282 bytes, RIFF/CDRB, SHA-256
`faac877b41d4d496d9657ae9433f2db1d83ac9a91017aece90edfc5df6c37b69`.
Reopening it in X7 preserved the 30 x 18 inch page, 1 x 1 inch square's exact
position, 0.003 inch red RGB(255,0,0) outline, and Arial Bold 24 pt `TEST` text
with identical bounds. The rectangle became a curve and its color lost an
internal GUID. Comparing physical geometry, RGB, text and style succeeds;
the closed path has the same four nodes in the same order and four straight
segments. Detailed before/after reports are alongside the ignored artwork.

The package is at `C:\Users\xws\Downloads\Aurora-XP-Reference` for the existing
XP Downloads share (`Z:\Aurora-XP-Reference`). It contains compatible artwork,
reports, a manifest, instructions and two copy-only XP command helpers. They
preserve the inbox before closing JobServer (whose EmptyOnExit=1 can clear it)
and snapshot new output after printing. They never delete/move files, change
settings, start JobServer, print or connect to the controller.

Pending operator action: disconnect XP's virtual network cable, keep JobServer
closed, print the compatible artwork through the XP driver at 100% with raster
30 ips/30%, vector 1 ips/15%/1000 PPI, flatbed 30 x 18 inches, zero offsets,
no focus, no color settings and Autostart off. Copy the new raw inbox output
with the helper; keep XP offline and JobServer closed until test jobs have
been removed from the watched inbox. No new physical transfer is authorized
or performed by this preparation.

Compare the reference with the marked draft for raster grid, origin, exposure
and vector scale. The saved CDR outline is 0.003 inch while XPS/GDI capture
reports 0.5 DIP; distinguish application quantization from encoder differences.
