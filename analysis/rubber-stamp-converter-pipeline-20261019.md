# Rubber-stamp converter pipeline: static evidence

Source: `analysis/extracted/tools-suite/BmpPict2/bmppict2.dll`, SHA-256
`1a851b834b1ad4ed3f339093fed57659a8ac3e5f5a8c69d9eaccd6254ffd2238`.
The file was parsed as data, never loaded or executed. Its version has not been
independently matched to the installed XP converter. These findings describe
the archived code and a future comparison design; they do not establish output
parity. The complete stamp feature remains held.

An immutable report preserves 423 decoded instructions in twelve relevant
ranges, their machine bytes, and seven numeric constants:
`runtime/offline-preferences-dev-20261018/stamp-converter-pipeline-20261019.json`.
The extraction script beside that report refuses to overwrite it.

## Parsing and dispatch

`SetRubberStampParams` validates BasePixels, SplitPixel and SplitPower at
0x10001474–0x10001528. A zero BasePixels bypasses the other validation and
disables this processing branch; otherwise SplitPixel must lie between zero
and BasePixels, and SplitPower between zero and 100.

The input scanner accumulates digits, whitespace, decimal points and signs at
0x10001a4a–0x10001ad3. It then compares the following fixed command word. Thus
`3 1 60set_stamp_mode` is recognized without a space before the command.
The replacement's imported-job hold now covers that spelling too, outside
picture payloads. A reproduction showed it had passed the first guard version;
regression cases cover both raw and CG input plus `1set_stamp_action`.

When the stamp BasePixels global is nonzero, the PICT branch constructs the
converter object and calls 0x100053ff followed by 0x10006412. The latter calls
the stamp routine 0x10005e66. This is a different path from ordinary copying
and compression. Other image formats and skip-white-line settings have their
own paths and are outside the currently supported JBS dialect.

## Size and origin are part of the transform

The PICT initialization path emits a relative `ACR` coordinate adjustment when
stamp processing is active and the picture has an explicit origin suffix:

- `PICT-UL` selects branch value 1 and emits negative BasePixels / DPI offsets.
- `PICT-LL` selects branch value 2 and emits positive offsets.

The original formatting strings are ` -%.4f -%.4f ACR\r ` and
` %.4f %.4f ACR\r ` at 0x10017bec/0x10017c00. This calculation is at
0x10005615–0x100056de. The header resolutions are normalized to thousandths of
DPI first, then divided by 1000 for this calculation. This is an additional
placement dependency; adding a grayscale stamp filter alone is insufficient.

Inside 0x10005e66, the output width and height are enlarged by twice BasePixels
in one action branch (0x10006035–0x10006056). The other branch complements the
initial source row and toggles flags on both raster reader and writer objects
(0x1000605b–0x100060a6); those flags' complete effects still need following.
The scan loop spans padding rows from -BasePixels to height+BasePixels-1.
Later row selection/cropping also depends on the action branch. Preserve these
differences in future comparisons instead of normalizing all outputs to the
input bounds.

## Action selection has a non-obvious dependency

`set_stamp_action` stores an integer at 0x10019d7c. At
0x10005fd1–0x10006028, action 1 forces one branch and action 2 forces the other.
Other values inspect the **first source row**, selecting the latter branch if
any sample in that row is exactly zero. The condition is not simply whether
there is a dark pixel anywhere in the image. A future reference should put a
black sample in the first row, then in a later row, and include a nonzero dark
gray sample in the first row. These cases can distinguish the observed branch
selection without relying on UI labels whose mapping is not yet established.

Kernel initialization at 0x1000ce63 consumes the same three parameters, converts
SplitPower to a float using 255/100, allocates padded rows, and builds lookup
tables. The later `rubber-stamp-lookup-model-20261019.md` maps the edge,
narrow-gap and gray-source lookup arithmetic. The complete scan processing at
0x1000d23e is still unmapped. No full image algorithm or simulator has been
claimed from these partial observations.

## No-raster conversion return

The same converter initializes a converted-image flag to zero at 0x10001874.
Its PICT and RAST processing paths set it at 0x10001ca6 and 0x10001df0. At
0x10001fa2–0x10001fb2, a zero flag selects return code 9. This corroborates the
JobServer `Nothing to Convert` dispatch described in
`vector-transfer-static-followup-20261019.md`; it is not evidence for removing
the modern sender's Vector Only transfer hold.

## Next independent evidence

First match the installed XP converter hash to this archive using file reads.
Then capture stamp input **and the XP JobServer-converted output**, with all
execution directed to an isolated offline recorder. Merely printing while XP
JobServer is closed yields the input command and cannot verify this transform.
Use small asymmetric monochrome and gray samples, both origin suffixes, a known
profile, and separately controlled action values once their UI mapping is
verified. Record dimensions, relative coordinate adjustments, complete pixels,
compression and directive removal. Keep source and converted files immutable.

No such stamp capture was run overnight. No hardware or XP networking was
enabled, and none of this static evidence changes feature availability.
