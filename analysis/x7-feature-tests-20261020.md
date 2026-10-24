# Actual X7 preference tests — October 20

**Follow-up:** the JPEG bitmap defect below is now repaired by installed r10
(0.5.2.0). Two fresh actual X7 prints preserve every source bitmap pixel;
see [fix and verification](bitmap-quality-fix-20261020.md). The campaign below
remains the immutable record of the original 16 prints.

The owner asked to run the next feature checks on X7 before asking for more XP
captures. **Sixteen real CorelDRAW X7 PrintOut jobs** were submitted exactly once
each to the existing loopback Capture only queue. No captured ticket was edited
to manufacture these results. No XP print, equipment connection, laser send,
driver installation or production encoder change occurred.

## Results

| Cases | Actual X7 captures | Current backend result |
|---|---:|---|
| Normal bitmap + red vector marker baseline | 1 | Local conversion succeeds: one raster and one vector path; Autostart Off. Image fidelity issue below remains. |
| Ordered 4x4, Ordered 8x8, Floyd–Steinberg, Jarvis, Stucki | 5 | Each complete snapshot arrives correctly; held on DitherBitmaps before rendering. |
| Manual contrast 64–192 / 128 levels; full range / 4 levels | 2 | Both snapshots arrive correctly; held on ManualContrast. |
| Mirror; plate left 90, right 90, upside down | 4 | All snapshots arrive correctly; held on Mirror or Orientation. |
| Manual focus, material thickness 0.125 inch, autofocus | 3 | All snapshots arrive correctly; held on Focus. |
| Beam Constantly On unchecked | 1 | Snapshot arrives correctly; held on BeamConstantlyOn. |

All jobs retain 167 DPI, raster 30 ips/45%, vector 1 ips/15%/1000 PPI,
30 x 18 inches and Autostart Off. Their immutable snapshots match independent
expected native XML exactly. Every receipt, source/control hash and unique
capture ID is checked. These are **settings-delivery and hold tests**; the 15
non-default engraving effects remain unimplemented and were not demonstrated.

The verifier calls the production conversion path. It renders/encodes the
supported baseline locally. All 15 unsupported cases stop before invoking the
native renderer or opening a socket, and create no deliverable JBS. The normal
JobServer remains idle Capture only; no test output is enqueued for delivery.

Evidence:

- Actual preserved jobs: `captures/host-x7-preferences-20261020/`.
- Aggregate: `runtime/x7-feature-tests-20261020/backend-review/verification.json`.
- Each case's `verified.json` records the actual received settings, hashes and
  exact preference restoration. `run-campaign.py` refuses duplicate case prints.
- The existing 198-test full regression plus one later mixed-host test were not
  repeated. These 16 actual print checks are separate from those counts.

## New finding: bitmap fidelity is lost in the X7 print path

The original asymmetric bitmap contains eight grayscale values. Exports of the
bitmap stored inside **both** the original Corel 11 file and the owned X7 test
file match the original BMP pixel-for-pixel. Document saving did not degrade it.

Every one of the 16 actual captured print files instead contains the same
167 x 167 **JPEG**. It has **153 grayscale values**, and **3,996 of 27,889 pixels
differ** from the original bitmap. This establishes loss in the print path,
before the replacement's raster encoder. It would contaminate dithering and
contrast comparisons even after their algorithms are implemented.

Reports: `bitmap-source-fidelity.json` and `embedded-image-audit.json`. The stored
bitmap exports were made from owned CDR copies through Corel's document API,
without printing or resampling. The original BMP and CDR were not modified.

The existing XP baseline was reused for a comparison, not recaptured. Its
raster is 145 x 140 at (1068,1332); the X7 baseline is 152 x 145 at (1044,1302).
Speed/power/DPI agree. Cropping/placement differences and JPEG noise need to be
separated before claiming raster-placement parity. The added red outline is
intentional and accounts for the extra vector path.

Microsoft documents [lossless PNG output](https://learn.microsoft.com/en-us/windows/win32/printdocs/mxdw-configuration-settings)
for its XPS converter and [image-quality mappings in v4 manifests](https://learn.microsoft.com/en-us/windows-hardware/drivers/print/v4-driver-manifest).
The source manifest already requests PNG for Normal/High, but the installed
provider does not retain an explicit High output-quality request. A bounded
quality probe stopped **before printing** and restored preferences exactly.
No extra seventeenth print occurred. The next fix is a verified lossless bitmap
capture configuration; no fix or driver update is claimed by this report.

## How the real X7 cases were exercised

Corel's typed automation API can print an owned document but does not expose the
Aurora-specific fields. Its exported print style contains application settings,
not the private DEVMODE. A direct Properties call stalled with the extension
hidden; screenshots still time out. Accessibility text works, but click geometry
is unavailable. Both stalled test requests were cancelled, owned documents were
closed, and the original `H:\test.cdr` was restored. A separate, unregistered
callback experiment timed out without changing settings or printing.

The successful helper, `tools/CorelScopedDefaultPrint.cs`, backs up the local test
printer's per-user preferences, applies one complete native snapshot, opens a
fresh owned CDR copy and submits one real PrintOut. It immediately restores the
saved per-user DEVMODE using Windows' [PRINTER_INFO_9 interface](https://learn.microsoft.com/en-us/windows/win32/printdocs/printer-info-9).
Machine defaults and the Windows default printer are not changed. This tests the
actual X7 spool path, but does not claim a successful automated Properties UI test.

The first generic PrintTicket restoration normalized a single DM_FORMNAME flag;
all laser settings already agreed. Exact native restoration corrected that byte
before the remaining cases. All subsequent jobs restore the original ticket
byte-for-byte. A final read-only audit matches the very first saved snapshot,
and the capture queue is empty. Failed approaches and their source are archived
under `development-approaches/`; no such harness was installed or left running.

Next development: fix lossless bitmap capture, then implement and test the
selected bitmap effects offline. Independent XP references will still be needed
for original-driver equivalence; these X7 tests do not replace that evidence.
