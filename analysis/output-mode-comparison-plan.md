# Next XP comparison: output modes at 167 DPI

Completed: the owner supplied all three captures and restored Both. See the
[results and implemented filtering](output-mode-results-20261018.md). Raster
Only now passes reference and loopback tests; Vector Only encoding matches XP
offline but delivery remains held. The text below records the original plan.

The owner confirmed restoring host raster/vector powers to 45/15 after the
successful r9 full-snapshot capture. Host JobServer remains Capture only.
VirtualBox reports LaserLaptop running, cableconnected1=off, NICs 2–8 absent,
and its Downloads share mapped to C:\Users\xws\Downloads. No VM configuration
was changed, no print was submitted and no controller was contacted.

Prepared helpers are in `tools/xp-output-mode-reference` and identical copies
were placed in the existing `Downloads\Aurora-XP-Reference` folder, visible as
`Z:\Aurora-XP-Reference` inside XP. The four files are ASCII/CRLF for XP.

The owner is asked for a controlled three-print batch using the unchanged
test-corel11.cdr: Both (control), Raster Only, then Vector Only. Run the matching
copy-only collector immediately after each print, preserving each inbox version
in an independently named folder. Restore Both without another print afterward.
Use 167 DPI, raster 30 ips/45%, vector 1 ips/15%/1000 PPI, No Focus, Autostart
off, color settings off and the existing 30-by-18-inch/normal-placement setup.
Keep XP disconnected and XP JobServer closed; host JobServer stays Capture only.

The original help's output-mode page establishes the intended filtering but
does not settle how individual Corel GDI primitives are treated. In particular,
do not infer whether the red hairline becomes raster content in Raster Only, or
whether filled lettering creates vector output in Vector Only.

When the three folders arrive, preserve each source and hash, verify the only
intended difference is mode, then compare headers, initialization/finish commands,
raster dimensions/pixels/origin, vector paths and settings. Inspect the Vector
Only transfer branch separately: the current encoder/wire planner requires a
raster and must not be enabled by simply removing that check. Mode selections
remain held in the replacement until their output path is implemented/verified.

Status: XP captures preserved and compared; owner restored Both. No higher-DPI
comparison is requested; the working resolution remains 167 DPI.
