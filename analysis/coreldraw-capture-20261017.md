# First CorelDRAW X7 capture and media correction

The owner printed the requested test drawing from CorelDRAW X7 to the local
`Aurora Capture (Preview Only)` queue. Capture UUID:
`7e368819-c1ca-456f-87ac-4eb602462424`, received 2026-10-17 23:37:42 UTC.
The 5,394-byte document SHA-256 is
`6c8dd2ddcfbb6a91c10f4ebf77ebb0dc7683737fab4219c2f8b0e734ca2e3332`.
Raw control metadata names `Untitled-1`.

## Observed problem

The owner's screenshot shows a 30 by 18 inch CorelDRAW page, with a red outlined
square and black `TEST` label. CorelDRAW warns that output does not fit the media.
The captured OpenXPS has a 1056 by 816 DIP FixedPage (11 by 8.5 inches), with no
Path, Glyphs or other artwork elements. It is blank. This is not a successful
application-artwork validation, and no dimensions or cutting semantics can be
inferred from its absent objects.

The capture queue had been installed using the Microsoft driver's Letter media
default. The document/media mismatch explains the warning; cropping or placement
outside the smaller output page is the likely reason for the blank print.
The output was not submitted to JobServer or the laser.

## Corrected capture queue defaults

Added `frontend/configure-capture-printer.ps1` and its restricted C# helper.
The tool verifies the exact preview queue, driver and port, saves previous
default/user PrintTickets plus capabilities, validates a custom 2880 by 1728 DIP
page (30 by 18 inches) without rotation, and commits only if the driver retains
those dimensions. A failed apply attempts to restore the prior tickets.
The install script now invokes this configuration after queue creation.

Inspection accepted the custom page. The applied settings and backups are in
ignored `runtime/capture-printer-settings/e0ce61baff9b46c184d2c5b7f25965b1`.
Both default and user tickets report 2880 by 1728 DIP and Portrait. The driver's
validated ticket drops the unsupported PageScalingFactor property; application
100% / original-size printing remains required. This is not a driver-level
guarantee overriding an application's scaling choice.

A new explicit local GDI probe yielded capture
`e21897a8-b83e-449e-b80f-0aa0a98fd273`, 82,582 bytes, SHA-256
`0e5047348d0a2087e0127c7532c4da547d05bd545b100aa11e59b4558c01a5eb`.
Its actual OpenXPS page is 2880 by 1728 DIP. The rectangle remains at
(24,24)..(120,120) DIP, a 25.4 mm square at (6.35,6.35) mm. The fill and glyph run
are present. Native normalization and intake passed, producing a 762 by 457.2 mm
page with one extracted red path in `runtime/aurora-bed-capture-preview`.

## Blank-page detection and next check

The intake now reports `engraving_nonwhite_pixels` and `has_visible_artwork`.
It flags a page with neither rendered nonwhite pixels nor extracted cutting
paths for review. Cutting-only pages with a white engraving image remain valid
visible artwork. The original blank CorelDRAW capture was reprocessed and
correctly flagged in `runtime/coreldraw-first-capture-review-v2` (zero nonwhite
pixels and no cuts). A fractional last-pixel-row rendering artifact initially
looked nonwhite in the first review output; the renderer now paints the entire
rounded-up raster white before clipping artwork to the true page. The blank-page
test includes this fractional-DPI case.

Nineteen frontend tests pass, including the new blank/cutting-only check.
The unchanged Python suite previously passed 57 tests. These are offline/local
print checks; no further physical laser job was sent.

The owner has been asked to reopen the Print dialog, reselect the capture queue,
confirm 30 by 18 inch media and original-size printing, and repeat the drawing.
CorelDRAW may retain a prior per-document or session DEVMODE; the new queue
defaults do not establish that an already open dialog has refreshed them.

## Legacy paper-size mismatch fixed

The owner still saw the warning, including after choosing CorelDRAW's
`Use printer default`. A new read-only diagnostic, `inspect-capture-printer.ps1`,
found a real mismatch: System.Drawing's GDI paper-size query returned User
Defined Size at 850 by 1100 hundredths of an inch, while the printable area was
3000 by 1800. Native DEVMODE had width 7620 and length 4572 (0.1 mm units), but
also selected generic paper ID 256 and retained the Letter form name.

The configuration tool now backs up the native global/user DEVMODEs, selects
explicit custom width and length without the stale paper-ID/form-name flags,
validates through DocumentProperties, and commits both defaults. It checks GDI's
returned paper dimensions after committing and attempts rollback on failure.
A separate fresh diagnostic process reports custom paper, raw kind 0, 3000 by
1800 hundredths of an inch, with a matching printable area. The stale Letter
string may still exist in inactive DEVMODE bytes; its field flag is cleared.

Current setup evidence is under ignored
`runtime/capture-printer-settings/f98282a1e63640f09b785d6da1545704`.
A fresh GDI probe captured as `7226905f-0d50-40fa-8502-fd2134dc7d1f`
(82,525 bytes, SHA-256
`cde8cbcb65f6232f6012d5ed9a1f0bb1fa111ddd9f1744e768041517f5ef72c4`)
retains the 2880 by 1728 DIP page and unchanged one-inch square.
No named Windows form is required or retained by this fix.

After saving the drawing and fully restarting CorelDRAW, the owner confirmed
that the warning cleared. The owner has been asked to print the same test once
with `Use printer default` and `As in document`; geometry validation is pending.

## Successful CorelDRAW print

The next print arrived as `test.cdr`, capture
`1a0f7e91-725d-4daa-a037-3e822b54806e`, at 2026-10-17 17:10:13 PDT
(2026-10-18 00:10:13 UTC). Its 74,090-byte OpenXPS document has SHA-256
`3946206c02d2504eab9b436b2c217ab468072bf39f134b0e59d0bbb68af07870`.
It contains one 2880 by 1728 DIP page, one red stroked Path and one Glyphs
element with Unicode text `TEST`. Unlike the first print, its artwork is present.

The square's coordinates are (87.2,118.08)..(183.2,214.08) DIP: exactly 96 by
96 DIP, or **25.4 by 25.4 mm**. Its upper-left is approximately (23.071667,
31.242000) mm from the page's upper-left. The path explicitly returns to its
starting point. There is no need to infer a closing segment from the image.
The emitted color is opaque RGB red (`#ffff0000`), with stroke thickness 0.5 DIP
(0.132292 mm), matching the converter's observed thin-stroke behavior. These are
print-document units, not a physical measurement at the laser.

Native OpenXPS normalization and intake succeeded in
`runtime/coreldraw-bed-capture-1a0f`. The resulting manifest reports:

- Page 762 by 457.2 mm; engraving image 5010 by 3006 pixels at 167 DPI.
- One extracted cutting path under the explicit red / maximum-0.2-mm rule.
- One glyph drawing retained for engraving, 2,844 nonwhite engraving pixels.
- Visible artwork present and no review reasons.

The engraving PNG was visually inspected: `TEST` remains and the red square
has been removed into the cutting SVG. The owner reported that clicking Print
appeared to do nothing; the local receiver had in fact received the document.
The current background receiver has no confirmation dialog, and no physical
print is expected from this preview-only queue. New JBS generation and hardware
calibration remain separate steps. This print was not sent to the engraver.
