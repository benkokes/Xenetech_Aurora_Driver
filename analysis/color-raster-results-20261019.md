# Colored raster XP evidence

The first actual filled-color XP reference is preserved at
`captures/xp-color-raster-preferences-20261019/color-raster-global-13630-23933/inbox/Default.jbs`.
SHA-256: `7390114e4b95b3501d78d67c80da322f3cb8ee164380d4e805051b000a1ae30b`.
Independent decoded metadata, sample previews and assertions are under
`runtime/xp-color-raster-preferences-20261019/global-13630-23933`.

Use Color Settings was OFF. Two 167-DPI raw regions appear, both at native
speed 30000 and 45% power, pitch 6, PICT-UL. The initial 21 x 21 black marker
at (966,978) matches the vector test marker exactly. The second 355 x 21 band
at (966,1476) includes five 21-wide solid squares with 62/63-wide zero gaps.
All 21 rows are identical. Signals by artwork position: Blue1 178, Red1 106,
Blue2 178, Red2 106, UnmatchedOrange 91. Preserve the measured values without
assuming a standard RGB-luminance conversion; color conversion/lookup inside
the original raster path is still to be established independently.

No vectors or pauses appear, and Autostart is off. All six squares are present.
The global baseline is the reference for the enabled-color capture below.

## Actual enabled-color output

Preserved file:
`captures/xp-color-raster-preferences-20261019/color-raster-enabled-24952-16211/inbox/Default.jbs`.
SHA-256: `4bdefd3ee534a5dd278f4ec0b00db549695c7910531119ba2886b1c8a289a2da`.
Length 8,883 bytes. Independent comparison and asserted region masks:
`runtime/xp-color-raster-preferences-20261019/global-vs-enabled/`.

With UseColors/Sort ON and Pause OFF, XP emits three regions in palette order:

| Color | Origin native units | Width x height | Native speed | Power |
| --- | --- | --- | --- | --- |
| Black | 966,978 | 21 x 21 | 30000 | 45% |
| Red | 1464,1476 | 188 x 21 | 1000 | 11% |
| Blue | 966,1476 | 188 x 21 | 2000 | 22% |

All are 167-DPI raw PICT-UL, pitch 6. Black is identical to baseline. Each
other mask combines both squares of that color: every row is 21 samples of
255, 146 zeros, then 21 samples of 255. Asserting mask positions against the
global-band source independently confirms exact selection of red/blue shapes.

Unmatched orange is **omitted**, whereas sampled unmatched vector output used
White's process. Matched solid-color raster samples become full signal 255;
they retain color-specific process power rather than global grayscale exposure.
No vector PPI, paths, pauses or Autostart appear. These observations establish
flat-fill masks and grouping for this sample only, not arbitrary bitmap
quantization, antialiasing, gradients, overlaps, sort-off behavior or physical
output. Production UseColors remains held.

## Actual paused-color output

Preserved file:
`captures/xp-color-raster-preferences-20261019/color-raster-paused-2195-25550/inbox/Default.jbs`.
SHA-256: `8d67cf4a88cc90181df66f3ec136869bbaf0be80227b5c637581740f37787fe7`.
Length 8,911 bytes. The comparison and exact byte assertions are in
`runtime/xp-color-raster-preferences-20261019/enabled-vs-paused/`.

Changing only Pause ON retains all raster samples and decoded fields exactly.
Pauses occur after Black/before Red and after Red/before Blue, with none after
the final Blue region. First boundary adds `PU\r0. 0. V\rPAUSE\r`; second
adds `0. 0. V\rPAUSE\r`. The final footer loses its initial PU. These are
the only byte changes, independently asserted against the full file. Raster
serialization must preserve pen-state caching as well as pause placement.
No vectors or Autostart, and no physical pause validation occurred.

## Actual disabled-Blue output

Preserved file:
`captures/xp-color-raster-preferences-20261019/color-raster-disabled-blue-20182-29314/inbox/Default.jbs`.
SHA-256: `bc6a3e4985fb4f7e0767197269356bb21ea1018d9fe784afc88b04739103deb1`.
Length 4,802 bytes. Black and Red are unchanged. Removing the Blue process
commands and entire Blue picture block from the enabled reference reproduces
the complete disabled-Blue file byte for byte. Orange remains absent, with no
vector output, pauses or Autostart.

The series now includes four actual XP captures. Independent omission and
series checks are in
`runtime/xp-color-raster-preferences-20261019/enabled-vs-disabled-blue/omission-verification.json`
and `capture-series-verification.json` in its parent directory. Region counts
are global 2, enabled 3, paused 3, disabled Blue 2. No physical job was run.

Original-profile/global-settings restoration has been requested after this
case; owner confirmation is pending. Flat-color raster grouping and command
behavior are established for the sampled layout. Arbitrary bitmap/edge color
quantization, overlapping colors, multiple vertical regions per color and
disabled/pause combinations remain separate evidence gaps. Production
UseColors remains held pending implementation and further validation.

The owner subsequently confirmed restoration. The
[offline model and experimental RGB intake](color-raster-model-results-20261019.md)
now reproduce these four files under the stated input assumptions. Actual
Windows X7 color-print rendering and live per-color output remain unverified.
