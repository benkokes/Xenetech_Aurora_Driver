# Xenetech Aurora Windows 11 investigation

Status: installer extracted and initial static analysis complete. No Windows 11
replacement driver has been built or validated. No vendor installer, driver DLL,
firmware updater, or job sender has been executed. No connection to the engraver
has been attempted.

Update: the owner supplied XP diagnostics in `capture-14978-28204`. Both installed
driver DLLs exactly match this archive's XP variants. See
`xp-capture-14978-28204.md` for the confirmed folders and connection configuration.
Its next-evidence section supersedes the initial diagnostic request below.

## Requirements confirmed by the owner

- Engraver: Xenetech Aurora, connected by Ethernet.
- An XP computer still successfully prints to this machine.
- Direct printing from applications is required. An import-only application would
  not fulfill the requirement.

## Source and extraction

Source: `\\arkhive\equipment\XenetechLaser\installer_6.39`.
Selected directories copied to `reference/installer_6.39`: DriverApps, Drivers,
EthernetUtil, xendocs, xgw32, plus readme.txt and autorun.ini. The local copy has
1,037 files totaling 496,066,631 bytes. `reference/source-inventory.csv` inventories
all 1,080 files in the original folder by relative name and size. The omitted
directories are not required for this first investigation. Original share files
were not modified. Local binary hashes are in `analysis/pe/index.json`; these are
identifiers, not a claim that every local file was hash-compared to the share.

Extraction used installed 7-Zip for the outer self-extracting CABs and portable
Unshield 1.6.2 for the nested InstallShield CABs. The downloaded Unshield archive
matched the SHA-256 in the Scoop manifest:
`662fefefc6988a3744ddc6b5b8d2e96ac21876d532f7d23a597c4ca797764a6b`.
Tool source: https://github.com/twogood/unshield . Package manifest:
https://github.com/ScoopInstaller/Main/blob/master/bucket/unshield.json .

- Laser driver payload: 56 files extracted.
- Driver CHM help: extracted to ordinary HTML and images.
- XGW32 companion software: 850 files extracted.
- Machine Tools suite: core programs and communication DLLs extracted. Three
  legacy DAO files in an exceptionally long archive group path failed extraction
  (`msjint35.dll`, `Odbcjet.cnt`, `Odbcjet.hlp`). A shorter-path duplicate of the DLL
  exists. This is a partial extraction of that suite, not a complete installable
  reconstruction. None of the three missing paths are needed for the static
  driver/protocol observations below.
- PE metadata, imports, exports, hashes, and ASCII/UTF-16 strings collected from
  178 binaries. Linear disassembly generated for three target modules. These
  reports cover the driver and tools suite, not every XGW32 binary.

## Findings established from local files

### 1. Version 6.39 labels the workstation software

`reference/installer_6.39/readme.txt` identifies XGW32 as 6.39 and the Laser Driver
as 2.003. `DriverApps/readme.txt` explicitly limits the laser print driver to
Windows 2000 and XP. These are separate version numbers.

`analysis/extracted/laser-driver/Common_Root_Files/XTLaser.inf` installs:

- `XTLASERGR.DLL`: graphics/rendering module.
- `XTLASERUI.DLL`: print configuration module.
- `XTLASER.CHM`: help file.

The extracted XP and Windows 2000 variants of the two DLLs are x86 PE binaries
(machine value `0x14c`). No x64 variant is present in this extracted driver
package. The XP graphics DLL's Microsoft plotter-driver version resource does
not supersede the vendor's package version; it appears to retain DDK sample
metadata.

### 2. Aurora is explicitly supported

The printer INF defines an `Aurora` model with `MaxWidth=7620` and `MaxHeight=4572`.
Its accompanying comment says 30 inches wide by 18 inches high. The numbers are
consistent with hundredths of a millimeter for these *configuration values*.
Do not assume these are also the on-wire coordinate units.

The `Drivers/Xen_Pci.inf` file describes a separate PCI board driver. Its presence
on this multi-product CD does not establish that the Ethernet Aurora needs it.

### 3. The graphics driver writes a watched-folder job file

Static code in the XP `xtlasergr.dll`:

- At image VA `0x00406394`, a routine walks registry keys ending in
  `Software\ExtraTech\JOBSERVER\HotWatch` and queries the value `InBox`.
- Its caller at `0x00404af3` first requests the required path size.
- At `0x00404be6` it reads the actual path, appends the job filename, and at
  `0x00404c45` calls a file-open routine.
- That routine at `0x0040733e` calls `_wfopen`.

This establishes a file handoff from the print renderer to JobServer. Ordinary
Windows "Print to file" must not be assumed to capture this path. Obtain the
actual inbox from the working user's registry on XP.

Installer defaults in `EthernetUtil/laser/Xenetech InstallOptions.reg` include
`c:\xfiles\etherin` and `c:\xfiles\jbs`, but those defaults have not been verified
against the owner's installed settings.

### 4. The job language is partly readable

In the XP graphics DLL, the routine at `0x00407507` emits the following beginning
in this order. The escaped terminators are significant:

```text
!ZX\r
JOB <job-name>\n\r
1 set_binary\r
1 == ?REPLAY\r
<spot> set_gspot\r
normalstart START\r     OR     autostart START\r
```

Conditional focus, table, or rotary settings follow. Later initialization includes:

```text
<value>. set_xyup_feed\r
0 PMC\r
1 PWF\r                OR     40 PWF\r
```

At `0x004077c8`, settings logic conditionally emits:

```text
<integer>. speed\r
<integer>.00 power\r
<integer>. set_vppi\r
```

At `0x004078e1`, another routine emits `END_PLOT\r`.
The graphics driver also references `PICT-UL`, `PICT-LL`, coordinate moves, and
binary raster data. `XGWJBSASCII.dll` references `PICT3-UL` and
`c:\xfiles\etherfile.jbs`. These are evidence of multiple related encodings, not
proof that they are interchangeable on the owner's controller.

These are observed output templates and call sites. Their physical units,
state transitions, raster layout, vector encoding, and required conditions are
not yet fully established. They are not a usable standalone job specification.

### 5. Network communication has its own implementation

`ETCComX.ocx` version 3.9.38.2 contains Winsock imports, control/real-time/main
channel labels, connection-locking logic, and a heartbeat. Its description refers
to the M2000 family of motion controllers.

Code near `0x1000ea07`, `0x1000eb66`, and `0x1000ec06` passes candidate port values
23, 29, and 30 into the corresponding connection calls. Discovery-related code
uses `ACKRONCE` and `CONQ    %s`. These ports and message roles need further
verification against a working session. Do not treat the device as an ordinary
raw-port-9100 printer on the basis of its Ethernet connector.

The separate DBI firmware files include Aurora H-board and Aurora K-board
variants. Their presence establishes controller variants in the archive, not
which board is installed in the owner's machine. Do not flash them as part of
driver analysis.

### 6. Two JobServer versions are present

| Location | Embedded file version |
| --- | --- |
| `reference/installer_6.39/EthernetUtil/laser/JobServer.exe` | 3.9.38.0 |
| `analysis/extracted/tools-suite/JSProgramFiles/jobserver.exe` | 3.9.40.0 |

The archive readme lists 3.9.40.0. Check the working installation before choosing
a binary as the reference implementation.

## Design direction

Preserve the application's Print workflow, including hairline vector cutting,
raster engraving, page placement, color-to-setting mappings, and power/speed/PPI.
First establish a reproducible file encoder matching the XP output. Then
validate the transfer protocol separately. Finally integrate both with a Windows
11 printer interface. A particular Windows driver model or helper-process design
has not yet been selected; it must preserve vector and raster information and
fit the target Windows installation.

A generic PDF-to-bitmap pipeline would lose vector-cutting semantics and cannot
be accepted as a complete replacement. Reusing legacy x86 user-mode components
inside a separate helper may be investigated, but loading them in the native x64
print-driver process is not a porting strategy.

## Next evidence needed

Run `capture/collect-xp-info.cmd` on the working XP computer as the normal printing
user. It only reads settings and copies the installed graphics/UI DLLs into a new
folder. It has been reviewed statically but has not been executed on XP.

Then follow `capture/README.md` to collect a few job files with the laser
disconnected and the inbox watcher closed. Controlled differences in position,
speed, power, PPI, and raster pixels will let us validate the recovered formulas.
Artwork source files and exact print settings must accompany the samples.

## Reproducing the static inspection

`tools/inspect_pe.py` and `tools/disassemble_pe.py` use local Python packages
`pefile==2024.8.26` and `capstone==5.0.9` in `tools/python`.

Example invocations with an available Python interpreter:

```powershell
python tools/inspect_pe.py analysis/extracted/laser-driver analysis/extracted/tools-suite reference/installer_6.39/EthernetUtil/laser/JobServer.exe
python tools/disassemble_pe.py analysis/extracted/laser-driver/XP_Files/xtlasergr.dll analysis/extracted/tools-suite/CommunicationActiveX/etccomx.ocx analysis/extracted/laser-driver/NewWorld_Files/XGWJBSASCII.dll
```

The disassembler is a linear code listing, not a decompiler. In particular, the
graphics DLL stores strings in an executable section, so some data is displayed
as nonsensical instructions. Only inspected instruction sequences reached from
actual routines support the observations above.

Key SHA-256 identifiers:

| Module | SHA-256 |
| --- | --- |
| XP `xtlasergr.dll` | `6aad6387df4d5e83008f17badeb8d284a9031d63d4ff61699c148a5913bc2c0d` |
| XP `xtlaserui.dll` | `b6fc2764110be158356cb5ca1a6e5f9f4e6765bc5f0d1b97309cad161899a942` |
| `ETCComX.ocx` | `dea0e62aa3c974cb5f0a2c14ca11b81b7488d798abae95ac5dfe12f64e5ba4fe` |
