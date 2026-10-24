# Independent raster conversion: exact match to XP JobServer

## Verified result

The owner confirmed that the recovered letter panels match the PP_ver5 artwork.
The associated raw and converted JBS files now supply a confirmed reference pair.

Running the independent converter on the 3,952,606-byte raw job produces all
92,759 bytes of the saved XP JobServer output exactly. The result includes both
compressed raster sections and the unchanged vector commands.

Output SHA-256:
`87d6b138e34ddcf20b58f5fb1355c40a7700a35362c7da8dfa167d3a5ec4a28f`.

No vendor binary was executed, no software was installed into Windows printing,
and no network communication with the engraver occurred.

## Header packing correction

The raw format uses magic bytes `C3 58` and ordinary little-endian fields.
The converted format uses `63 47` and stores seven payload bits in each byte:

```text
value = b0 + (b1 << 7) + (b2 << 14) + (b3 << 21)
```

The apparent increase in width and height in the initial notes was a decoding
error. In the first converted header:

| Bytes | Correct value | Interpretation |
| --- | ---: | --- |
| `13 1d 00 00` | 3731 | Original pixel width |
| `2a 04 00 00` | 554 | Original row count |
| `58 18 0a 00` | 167000 | Resolution field, scaled by 1000 |
| `41 01` | 193 (`0x00c1`) | Original `0x41` flags plus compression bit `0x80` |

Static routines at `BmpPict2.dll` VAs `0x1000b9fb` and `0x1000ba6b` implement
the packing and unpacking. The four-byte fields carry up to 28 bits.

There is no pixel-size change or resampling in the confirmed reference pair.
After decompression, the raster payloads, including every row trailer, match:

| Raster | Dimensions | Decoded bytes | Decoded SHA-256 |
| --- | --- | ---: | --- |
| 1 | 3731 × 554 | 2,068,082 | `6907ade9832c684ef2f0783a45565bb82944097d31d3bfbc8c75bb184768ca03` |
| 2 | 3202 × 578 | 1,851,912 | `bed2d8ec3bd487ff5d0256ccd93b7c621ba447155aee434b495ad3b0e1ca4b37` |

## Recovered compression rules

- Literal byte codes: 0 through 255.
- Clear/reset code: 256 (`0x100`).
- End code: 257 (`0x101`).
- First added dictionary entry: 260 (`0x104`); 258 and 259 are reserved here.
- Initial code width: 9 bits, growing through 10, 11, and 12 bits.
- Codes are packed least-significant-bit first into **seven-bit** bytes.
- The encoder emits a clear at the start and when the next dictionary entry
  reaches `0x0ffe`, preserving transport-bit alignment across dictionary clears.
- Encoder and decoder grow code width at their corresponding dictionary
  thresholds. The decoder's initial early-change threshold is `0x1ff`; the
  encoder's is `0x200`. Their tables differ by one pending entry during decoding.
- An end code is followed by zero padding to the next seven-bit byte boundary.
- The compressed source stream is the original scan-order raster data, including
  its `00 FF` row trailers. Compression does not unsnake or reorient the pixels.

Relevant static code is in `BmpPict2.dll`'s compression routines around
`0x10003bcf` (encoding), `0x1000410a` (code packing), `0x10004601` (code reading),
and `0x1000476c` (decoder dictionary growth). Their behavior was cross-checked
against the captured streams rather than inferred from a generic LZW library.

For the observed job, conversion also prefixes the `PICT-UL` command with two
spaces, scales the resolution fields by 1000, and sets the compression flag.
All other non-raster bytes are preserved. Reproducing these details is required
for the whole-file byte comparison to pass.

## Implementation and reproduction

- `tools/raster_codec.py`: seven-bit integer packing and independent LZW
  compressor/decompressor.
- `tools/convert_job.py`: raw raster JBS to the observed compressed CG format.
- `tools/inspect_converted_job.py`: header decoding, decompression, length
  validation, and row-trailer checks.
- `tests/test_raster_codec.py`: known header bytes, bounds, malformed input,
  dictionary transitions/reset stress, and the external JobServer reference.

With the bundled Python interpreter or another Python 3.10+ interpreter, from
the project directory:

```powershell
python tools/convert_job.py captures/capture-14978-28204/jbs/Default.jbs captures/decoded/reproduction/Default.jbs --compare captures/capture-14978-28204/jbs/Convert/Default.jbs
python tools/inspect_converted_job.py captures/decoded/reproduction/Default.jbs --output captures/decoded/reproduction/decoded
python -m unittest discover -s tests -v
```

The converter refuses to overwrite an existing destination; choose a new output
filename for another run. Keep these generated jobs outside any watched inbox.
Commands such as the captured `autostart START` are preserved, not made inactive.

The files already generated during verification are under
`captures/decoded/independent-conversion`. They remain ignored by Git.

## Validation and limits

All eight current tests pass. This includes an exact whole-file comparison with
the captured XP output, not only a compressor/decompressor round trip. The
reference streams exercise every code width and multiple dictionary clears.
A separate 100,000-byte deterministic incompressible sample tests further
dictionary resets. Truncation, output-size limits, and invalid seven-bit fields
are rejected.

The raw converter currently accepts the observed `C3 58` raster header and
`0x41` raw flags. The CG inspector accepts decoded flags `0xc1`. Other raster
types, monochrome-specific output, rubber-stamp processing, whitespace skipping,
and further device modes are not claimed as implemented. The whole-file match
is confirmed for one mixed raster/vector print; more reference cases will be
needed before treating this as a general replacement.

This is an offline conversion component. A complete Windows 11 solution still
needs application print capture/rendering, configuration UI, and validated
Ethernet delivery. The original XP driver binaries remain useful for recovering
those behaviors, but they have not been installed into Windows 11.
