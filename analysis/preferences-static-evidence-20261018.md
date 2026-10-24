# Original Preferences: additional static evidence

This work reads the matched driver/installer binaries without loading or
executing them. It adds evidence for later XP comparisons; no new feature was
enabled in the live backend. Full machine-byte snippets and SHA-256 source
identities are in
`runtime/offline-preferences-dev-20261018/static-preference-evidence.json`.

`tools/inspect_dialog_resources.py` now extracts standard and extended Windows
dialog resources, including control IDs, literal labels, fonts and dialog-unit
bounds. Six dialogs were recovered from XP `xtlaserui.dll` and four from the
rubber-stamp DLL. Their JSON reports are in the same runtime directory. The
parser follows Microsoft's [standard item layout](https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-dlgitemtemplate)
and [extended template layout](https://learn.microsoft.com/en-us/windows/win32/dlgbox/dlgtemplateex),
including alignment and the differing creation-data length conventions.

## Flags and output branches

The dialog's actual labels establish the control identities independently of
the owner's screenshots:

| Control | Resource ID | Private DEVMODE flag | Static output evidence |
|---|---|---|---|
| Beam Constantly On | 0x44f | 0x0100 | UI saves the bit at 0x00407f24; graphics selects `40 PWF` when set and `1 PWF` when clear at 0x004076f6. |
| Invert Raster Output | 0x47a | 0x1000 | UI saves at 0x0040804a; graphics complements the three input pixel bytes at 0x00407cc6 before signal conversion. |
| Bottom-Up Engraving | 0x47c | 0x2000 | UI saves at 0x0040807b; graphics chooses `PICT-LL` at 0x004079a1 and swaps row bounds at 0x00407a4b. |

For neutral grayscale, the inversion branch implies complementing signal
within the emitted picture. It does not establish picture extents: blank
margins, gaps, source bitmap bounds and the point where regions are selected
still need the prepared controlled XP reference.

For normal plate orientation, the bottom-up branch changes stored row order,
the picture's UL/LL label and the starting-row coordinate. A reversed preview
alone cannot establish whether the controller will mirror artwork. The new
comparison tool intentionally keeps pixel transforms, origins and labels
separate. Other plate orientations need their own comparison.

## Manual contrast compatibility issue to resolve before activation

Original UI helper 0x00403687 stores the manual-contrast color count in a byte
and clamps it to high minus low, at most 255. It also normalizes invalid
low/high and zero-count inputs. The replacement currently preserves 256 as an
inactive default/saved value; that value has already appeared in installed r9
snapshots and must not simply be rejected by a backend update.

ManualContrast is still held, so this difference has not affected a delivered
job. Before enabling it, use a controlled grayscale reference and design a
backward-compatible update for existing inactive 256 snapshots. This is not a
reason to change printer defaults or reinstall an untested UI overnight.

## Rubber-stamp subdialog recovered

The archive contains
`analysis/extracted/laser-driver/NewWorld_Files/XGWDlgRubberStamp.dll`, SHA-256
`f41f876c053bbad99a613105bb562a1e0d0ff96e9b14487f3991f5d3009c5f0d`.
Its dialog resource **11000** is titled **Rubber Stamp Settings** and includes
Depth, Split Power, Shoulder, Base and Base + Shoulder, along with profile
Save/Delete/Import/Export/Defaults controls. The strings and numeric positions
are recovered facts; their units, ranges, factory profiles and actual command
semantics are not yet established.

The DLL exports `CreateFactoryDefaults` at 0x10003980, which asks XGWRegistry
for QuickPick1 through QuickPick5 values. XGWRegistry exposes four related
properties: Scale, Base, Shoulder and Gradient. Their getters and command
builder are available for further static inspection in
`analysis/disassembly/XGWRegistry.dll.asm`. These names are not yet a proven
one-to-one mapping to the displayed controls. Do not add guessed parameters
to the production snapshot or remove RubberStamp's output hold.

This replaces the assumption that another screenshot is the only way to learn
the missing dialog. An owner screenshot can still confirm which variant is
used by the working XP installation.

Follow-up: [stamp defaults and command-builder recovery](rubber-stamp-static-model-20261019.md)
now establishes five built-in fallback profiles, serializer order and the DPI
adapter path. It also identifies required host-side BmpPict2 stamp processing;
imported JBS files containing those unimplemented directives are now rejected
before preparation. Full stamp raster behavior remains unverified and held.
