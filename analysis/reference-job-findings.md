# First captured Aurora job: decoded raster and vector output

## Result

The captured `.prn` is empty. The actual engraving content is present in
`jbs/Default.jbs` and its transformed counterpart `jbs/Convert/Default.jbs`.
The original job contains two raw grayscale rasters and vector outlines spelling
“SOARING TO NEW HEIGHTS.” A decoder and separate vector preview were implemented
and run against these files. No job was transmitted or executed.

The owner confirmed that the recovered letter panels match the artwork printed
as `PP_ver5`. The raw/converted files can therefore be treated as reference
output from that print, rather than an unidentified historical job. The exact
editable source artwork and per-print UI settings have not yet been collected.

## Collected evidence

The new files were found under the Downloads capture folder, with the DBI beside
that folder. Copies in the project were verified against their source bytes.

| Source relative to `C:\Users\xws\Downloads` | Bytes | Meaning |
| --- | ---: | --- |
| `capture-14978-28204/PP_ver5.prn` | 0 | Empty; no engraving commands |
| `capture-14978-28204/jbs/Default.jbs` | 3,952,606 | Raw mixed raster/vector job |
| `capture-14978-28204/jbs/Convert/Default.jbs` | 92,759 | Same job with transformed raster sections |
| `capture-14978-28204/jbs/Capture/ETCBootLog.txt` | 230 | Controller startup text |
| `laserDB20240317.dbi` | 86,016 | Jet-format machine database |

The zero-byte `.prn` agrees with the previously observed file-handoff design:
the driver writes a separate inbox file instead of putting its engraving stream
into the ordinary spooler output. This file alone would not have helped decode
the job language. It does not indicate that the `.jbs` capture failed.

Raw JBS SHA-256:
`1d1e0fdf5790f4330280cf5f8ddf315b8f87902d847d18d62abcd62be295660e`.

Transformed JBS SHA-256:
`87d6b138e34ddcf20b58f5fb1355c40a7700a35362c7da8dfa167d3a5ec4a28f`.

DBI SHA-256:
`df0041a75e2073067acc6822e08782ccffe9e1f8c48f358a8ebbd9df58e9d0d5`.

## Raw raster structure validated

The observed `PICT-UL\r` command is followed by this 20-byte little-endian header:

| Offset from binary header | Size | Observed field |
| ---: | ---: | --- |
| 0 | 2 | Magic bytes `C3 58` (word `0x58c3`) |
| 2 | 4 | Width in pixels |
| 6 | 4 | Height in rows |
| 10 | 4 | X-resolution field |
| 14 | 4 | Y-resolution field |
| 18 | 2 | Format/flags, `0x0041` in both captured rasters |

Each row contains exactly `width` grayscale signal bytes, followed by `00 FF`.
Rows have no BMP-style four-byte padding. Alternate rows are stored in reversed
horizontal order. The preview unsnakes those rows and converts zero exposure to
white and maximum exposure to black. It does not apply physical machine
orientation or calibration.

This layout is supported independently by the installed driver's WriteBitmap
routine: the header construction starts near VA `0x00407b6b`, grayscale
conversion near `0x00407d56`, and row writes near `0x00407da9`.

| Raster | Header file offset | Dimensions | X/Y resolution fields | Following text begins |
| --- | ---: | --- | --- | ---: |
| 1 | 196 | 3731 × 554 | 167 / 167 | 2,068,298 |
| 2 | 2,068,345 | 3202 × 578 | 167 / 167 | 3,920,277 |

All 1,132 row trailers validated. Decoded previews were visually inspected;
they contain letter panels, including rotated letters in the second raster.

Generated local artifacts:

- `captures/decoded/original/Default.json`: offsets, dimensions, hashes, and
  non-raster command segments.
- `captures/decoded/original/Default-raster-01.png`: first raster preview.
- `captures/decoded/original/Default-raster-02.png`: second raster preview.
- `.pgm` counterparts preserve full decoded grayscale pixel values.

Only this observed raw encoding and flags value are currently accepted by
`tools/inspect_job.py`. Unsupported formats must not be guessed from a file
extension or silently treated as uncompressed pixels.

## Vector section validated across both files

The 32,329-byte vector tail starts at offset 3,920,277 in the raw job and 60,430
in the transformed job. It is byte-for-byte identical in both. It begins with:

```text
1000. speed
15.00 power
1000. set_vppi
```

The tail includes `PU`, `PD`, `1 RA`, `2 RA`, coordinate pairs followed by `V`,
and `END_PLOT`. These lines use carriage-return terminators. The header also
contains `autostart START`; these files should remain offline reference data.

The preview tool groups the observed `PU`/`PD`/`V` subset into 23 drawn polylines.
It counts 1,815 coordinate commands across the complete job's non-raster
segments (1,813 in the vector tail, including its final return move). The drawn
coordinates span X=4656..25524 and Y=9516..15438 in native job units. Physical
units and handling of other command types remain uncalibrated.

Artifacts:

- `captures/decoded/vector-preview.svg`: vector geometry in native coordinates.
- `captures/decoded/vector-preview.png`: rendered preview of the outlines.
- `captures/decoded/vector-preview.json`: path count and coordinate bounds.
- `captures/decoded/original/vector-tail.txt`: original readable command tail.

These previews demonstrate that both engraving and cutting information can be
recovered. They are not an implementation of the complete controller language.

## JobServer's raster conversion reproduced

Follow-up analysis established that the `63 47` picture headers use seven-bit
integer packing, not ordinary little-endian integer fields. The earlier values
7443 and 1066 were misinterpretations of packed header bytes; decoded correctly,
they are the original width 3731 and height 554. Likewise, the packed flag bytes
`41 01` mean `0x00c1`, not `0x0141`. This correction removes the earlier apparent
dimension change.

The converted raster payload uses an LZW variant packed into seven-bit bytes.
Both decompressed raster payloads match their raw counterparts byte for byte;
no resampling occurs in this captured pair. Resolution fields are encoded at a
scale of 1000: raw 167 becomes packed 167000.

`tools/convert_job.py` now independently reproduces the complete 92,759-byte
JobServer output, including both compressed rasters, header packing, whitespace,
and unchanged vector commands. Its output SHA-256 is identical to the captured
converted file. The implementation uses Python's standard library and does not
execute the vendor DLL. See `raster-codec.md` for the recovered algorithm,
reproduction command, tests, and supported scope.

This establishes the observed conversion stage, not Ethernet framing or Windows
printing. Neither reference file is a network packet capture, so TCP framing,
locking, and acknowledgment behavior remain to be verified separately.

## Machine database and startup log

The `.dbi` starts with the Jet database signature. It was read using
`access-parser==0.0.6` and exported without executing vendor code or importing
anything into the controller. Exported tables are:

| Table | Rows |
| --- | ---: |
| `DBI_Version` | 1 |
| `Machine` | 210 |
| `Modules` | 0 |
| `HTML` | 0 |

The database version is 3.9. The machine rows have parameter-number keywords such
as `PARAM559` and numeric values, rather than descriptive labels. Their semantic
mapping still needs work; no values were applied to the machine.

The startup log reports `MCIF V4.25c`, `DSP V1.24`, `KDM V4.25c`, and
`Version (H40172)`. These are controller identity clues. They do not by themselves
prove which factory firmware image should be used. The log also records a
startup feed-limit adjustment; no live machine condition was inferred or changed.

Parser source: https://github.com/claroty/access_parser . It documents format
limitations; successful export here is a useful inspection result rather than
a guarantee that every possible Jet feature is supported.

## Additional installer checked

The related `XenetechLaserEngraver2039.exe` already present in Downloads was also
copied locally and unpacked without execution. It contains later graphics/UI
variants for XP and Windows 2000, including multiple languages. All 16 extracted
`xtlasergr.dll`/`xtlaserui.dll` variants are x86. No native x64 print driver was
found in that package. It has not been installed on either computer.

## Validation and remaining work

- Verified copied capture files against Downloads originals.
- Validated every raw raster row trailer and the end-of-payload offsets.
- Visually inspected both decoded raster strips and the vector preview.
- Compared the entire vector tail between raw and transformed files.
- Ran three decoder tests: explicit expected pixel order/footer, rejection of a
  damaged row trailer, and rejection of a truncated raster. All passed.
- Compiled the Python utilities for syntax checking.

Tools added: `tools/inspect_job.py`, `tools/preview_vectors.py`, and
`tools/dump_dbi.py`. Generated customer artwork, database contents, and vendor
binaries remain outside Git in ignored folders.

Next: establish physical coordinate and resolution rules beyond this reference
job. A Windows 11 printer interface and validated Ethernet sender
are still required. No Windows 11 replacement has been built or hardware-tested.
