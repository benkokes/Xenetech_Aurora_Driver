# Next offline XP capture: 500 DPI

This is a read/compare test. Keep the XP VM's network cable disconnected and
JobServer closed throughout. Do not send this job to the engraver.

1. In XP, leave `test-corel11.cdr` open in CorelDRAW 11. Run the existing
   `Z:\Aurora-XP-Reference\xp-reference-backup.cmd` before printing to preserve
   anything already in the watched inbox.
2. Open the original Xenetech printer Properties. Use Both Raster and Vector,
   raster **30 ips / 45%**, vector **1 ips / 15% / 1000 PPI**, No Focus,
   **Autostart off**, 30 × 18 inches, zero offsets, color settings off, normal
   plate/engraving orientation. Keep the existing bitmap settings unchanged.
3. Change Advanced → Resolution to **500 DPI**. Keep CorelDRAW Layout
   **As in document / 100%**, with no centering, and print the unchanged drawing
   once. Printing writes the XP inbox file; JobServer must stay closed.
4. Run `Z:\Aurora-XP-Reference\xp-reference-collect.cmd`. It copies the new
   inbox file into a fresh `after-print-*` folder and leaves originals intact.
   Reply **500 DPI captured**.
5. Restore **167 DPI**, without printing again. Keep XP offline and JobServer
   closed; the captured test job remains in its inbox.

Expected, to verify rather than assume: raster header 500/500, `2.000 set_gspot`,
and approximately 1000 job units for the one-inch square. Compare absolute
placement as well as size. This is not physical calibration.

If the source settings differ or printing fails, report that instead of
submitting a second print. The replacement remains capture-only on the host.
