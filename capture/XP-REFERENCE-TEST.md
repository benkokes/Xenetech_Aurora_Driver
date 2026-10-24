# Offline reference from CorelDRAW 11

The prepared `test-corel11.cdr` is a separate version 11 copy of the owner's
`H:\test.cdr`. The source remains unchanged. It has one 30 x 18 inch page,
one 1 x 1 inch RGB red outlined square, and Arial Bold 24 pt `TEST` text.
Corel saves the old-format rectangle as a closed curve; all four corners,
straight segments, outline width/color and text geometry match on reopening.

This package captures the XP driver's file for comparison. It does not require
running the laser. The two `.cmd` helpers only copy files and list the inbox;
they never print, move/delete jobs, connect to the machine or start JobServer.

1. In XP, open the shared Downloads folder (previously `Z:\`) and its
   `Aurora-XP-Reference` subfolder. Run `xp-reference-backup.cmd` **before closing
   JobServer**. Stop if it reports failure. The existing JobServer configuration
   may empty its inbox when it exits.
2. Disconnect XP's virtual network cable using VirtualBox's network-adapter
   menu. The shared Downloads folder should remain available through Guest
   Additions. Close JobServer and leave it closed. Do not reconnect for capture.
3. Open `test-corel11.cdr` in CorelDRAW 11. Select the existing Xenetech laser
   printer. Use the following settings, then print once at 100% / original size
   with no fit-to-page or centering:

   | Setting | Value |
   | --- | --- |
   | Output | Both Raster and Vector |
   | Raster speed / power | 30 ips / 30% |
   | Vector speed / power / PPI | 1 ips / 15% / 1000 |
   | Plate | 30 x 18 inches |
   | Offsets | Horizontal 0, vertical 0 |
   | Focus | No Focus at Start |
   | Autostart | Unchecked |
   | Use Color Settings | Unchecked |
   | Invert / Bottom-Up / Cylindrical | Unchecked |
   | Horizontal / Vertical Plate Center | Unchecked |
   | Beam Constantly On | Leave as in the supplied screenshot (checked) |

   Preserve the saved red outline width. Do not redraw, reposition, resize or
   convert the text. If a font substitution or page-size warning appears,
   stop before printing and report it. If the driver refuses while JobServer
   is closed, report that rather than starting JobServer or reconnecting.
4. Run `xp-reference-collect.cmd`. It copies the inbox to a new `after-print-*`
   folder beside itself. The driver's actual output is expected under
   `C:\xfiles\etherin`, independently of Windows' Print to file option.
5. Reply that the reference is captured. **Keep XP offline and JobServer closed**
   until the newly generated job has been identified and moved out of the
   watched inbox. The collection helper leaves originals there. Restoring
   connectivity or restarting JobServer could otherwise queue that test.

The reference will be checked against the replacement's draft for raster sample
dimensions and placement, vector coordinates, speed, power and PPI. This is not
an instruction to engrave the new artwork.
