# One offline comparison at 100 DPI

The 167-DPI reference and both geometry reports are preserved in the project.
XP and X7 read the same square coordinates, but XP's raw print output is shifted.
The driver allocates 5000 x 3000 pixels for the 30 x 18 inch bed at nominal 167
DPI, while nominal DPI times page inches gives 5010 x 3006. At 100 DPI, those
two counts agree (3000 x 1800). This capture tests whether that discrepancy
affects CorelDRAW's placement. It does not run the engraver.

1. Keep XP's virtual network cable disconnected and JobServer closed. Leave
   `test-corel11.cdr` active in CorelDRAW 11, with no artwork edits.
2. Open Print > Xenetech printer Properties > Advanced. Record the current
   **Resolution** (expected 167 DPI), then change only that setting to **100 DPI**.
   If 100 is unavailable or more than one resolution control is shown, stop
   before printing and report what the controls show.
3. Check that the job still uses Both Raster and Vector, raster 30 ips/30%,
   vector 1 ips/15%/1000 PPI, plate 30 x 18 inches, zero offsets, no focus,
   color settings off and **Autostart off**. Keep CorelDRAW Layout As in document
   at 100%, with no centering. Print once. The earlier Default.jbs has already
   been preserved; this test may replace the driver's inbox copy.
4. Run the existing `xp-reference-collect.cmd` in this shared folder. It copies
   the new inbox file to a fresh `after-print-*` directory. Reply "100 DPI
   captured". If printing fails while JobServer is closed, report the failure
   and keep it closed.
5. Restore the Resolution value you recorded, without printing again. Keep XP
   offline and JobServer closed: the helper leaves the test job in the watched
   inbox. The test must be moved out before restoring normal operation.

Expected evidence, to be checked rather than assumed: raw raster resolution
fields 100/100, `10.000 set_gspot`, and a one-inch vector span near 1000 job
units. A different square position will help distinguish application handling
of printer capabilities from driver coordinate offsets. This comparison alone
does not establish physical calibration.
