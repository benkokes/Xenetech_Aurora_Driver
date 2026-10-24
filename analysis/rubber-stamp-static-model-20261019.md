# Rubber-stamp defaults and command builder: offline recovery

This follows the archived `XGWDlgRubberStamp.dll`, `XGWRegistry.dll` and
`NewWorld.dll` as data, plus the matched XP graphics driver. No vendor module
was loaded, no registry value was queried, and no laser communication occurred.
`tools/inspect_stamp_defaults.py` verifies source hashes, embedded float
instructions, virtual getter identities and adapter constants before producing
its report. Production RubberStamp remains held.

## Built-in fallback values

The dialog's factory initializer calls getters for QuickPick1 through
QuickPick5. The registry code provides these binary32 fallback values:

| QuickPick | Scale | Base | Shoulder | Gradient |
|---:|---:|---:|---:|---:|
| 1 | approximately 0.03 | approximately 0.012 | approximately 0.004 | approximately 0.60 |
| 2 | 0.0625 | approximately 0.02 | approximately 0.01 | approximately 0.30 |
| 3 | 0.0625 | approximately 0.02 | approximately 0.01 | 0.50 |
| 4 | 0.0625 | approximately 0.02 | approximately 0.01 | approximately 0.70 |
| 5 | 0.0625 | approximately 0.02 | approximately 0.01 | approximately 0.90 |

The report retains exact float32 bit patterns and instruction addresses. These
are built-in fallbacks, not the owner's current saved settings: registry
profiles can replace them. The archived helper versions have not yet been
independently matched to the running XP installation.

The recovered dialog labels are Depth, Split Power, Shoulder and Base. Mapping
the displayed depth and profile controls to all four registry properties still
needs the UI call flow or a controlled XP reference. In particular, Scale is
not read by this three-argument command builder; its effect cannot be recreated
merely by emitting the command below.

## Command argument order

`XGWRegistry!GetDlgRubberStampString` is at 0x10006020. Its getter table is:

| Virtual offset | Getter |
|---:|---|
| 0x40 | Gradient |
| 0x48 | Shoulder |
| 0x50 | Base |
| 0x58 | Scale |

Getter call order is not serialized argument order. Tracing the stack through
the three decimal `_ltoa` calls establishes:

```text
round((Base + Shoulder) / pitch)  max(1, round(Shoulder / pitch))  round(Gradient * 100) set_stamp_mode
```

The second value is clamped at 0x1000610d. It comes from entry-relative stack
offset -116 when passed to `_ltoa` at 0x1000617f. Gradient's rounded percentage
comes from offset -112 at 0x100061e2. The first argument comes from EAX at
0x1000611d. The additions of 0.5 followed by MSVCRT `_ftol` imply positive
half-up rounding, rather than Python's default rounding rule. There are
explicit binary32 stores in the pitch and scaled-gradient path.

## DPI adapter matters

The graphics driver does not pass the displayed nominal DPI directly. Helper
0x00406dea produces nominal DPI times 1000, substituting **166667** for 167000
and **333333** for 333000. `NewWorld!GetASCIIRubberStampString` at 0x100038b0
multiplies that integer by the binary32 value stored at 0x10005848, approximately
0.001, then stores the builder argument as binary32. At nominal 167 it becomes
**166.66700744628906**. The builder stores `1 / argument` as binary32 pitch.

The adapter also affects half-way cases: at nominal 250, its argument is
250.00001525878906, moving QuickPick2's Shoulder sample calculation just above
2.5, so the model predicts three rather than two. Avoid replacing this chain
with nominal-DPI multiplication or a generic rounding function.

The offline model predicts these commands at nominal 167:

| Built-in fallback | Predicted command |
|---:|---|
| QuickPick1 | `3 1 60 set_stamp_mode` |
| QuickPick2 | `5 2 30 set_stamp_mode` |
| QuickPick3 | `5 2 50 set_stamp_mode` |
| QuickPick4 | `5 2 70 set_stamp_mode` |
| QuickPick5 | `5 2 90 set_stamp_mode` |

These are explicitly **static predictions**, not independent XP output or
physical calibration. The tool produces JSON only, never a complete JBS job.
The helper's floating-point environment and full stamp raster processing also
remain outside this mathematical model.

## Evidence and checks

- Source registry SHA-256:
  `85beed95637d0372e6fdf3e91e5cbf3d14708d4df574a009ac8539d9ac31e7b8`.
- Adapter SHA-256:
  `7a5a98e96c6284bbeaac2abbf6d989a2ca6c7c379774ef9ef4b31b5aa81e66f4`.
- XP graphics SHA-256:
  `6aad6387df4d5e83008f17badeb8d284a9031d63d4ff61699c148a5913bc2c0d`.
- Immutable extraction report:
  `runtime/offline-preferences-dev-20261018/stamp-fallbacks-20261019-verified.json`.
- Five focused tests cover DPI conversion, numeric/serialization expectations,
  the minimum Shoulder count, Scale's absence from this command, source/version
  checks, all 45 nominal-resolution/profile predictions, and the active feature
  hold. No installed printer or preferences were changed.

## Converter dependency and imported-job guard

Further inspection found that BmpPict2 itself recognizes `set_stamp_mode` at
0x10001ad8, parses its three numbers and calls its exported
`SetRubberStampParams` at 0x10001b58. Its diagnostic names the arguments
**BasePixels, SplitPixel and SplitPower**, corroborating the serialized order.
It also recognizes `set_stamp_action` at 0x10001ba6. These directives configure
host-side raster processing; they are not sufficient evidence for passing a
stamp directive unchanged to the controller.

The replacement's current raw-to-CG converter reproduces ordinary compression,
but does not reproduce that stamp processing. The complete Preferences route
already holds RubberStamp, but a manually imported legacy JBS could previously
retain such a directive through ordinary compression. `jbs.prepare` now rejects
those two known host directives outside picture payloads, before preparing or
planning delivery. It identifies the missing rubber-stamp preprocessing in its
error. Binary pixels containing the same words are still treated as pixels.

Three regressions cover raw and CG imports, both directives (including mode
zero and LF-separated commands), embedded raster byte sequences, and import
queue failure before any prepared artifact or socket access. Ordinary reference
jobs and full-snapshot feature holds retain their existing behavior.

The follow-up `rubber-stamp-converter-pipeline-20261019.md` maps the command
scanner, origin adjustments, dimension/action dependencies and remaining
kernel work. The import guard also covers numeric-adjacent command words,
which the original scanner recognizes without a separating space.
