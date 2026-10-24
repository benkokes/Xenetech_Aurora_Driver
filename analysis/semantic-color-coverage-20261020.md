# Offline semantic color coverage and immutable job review

The owner's unattended authorization was used for offline development, local
Corel capture and loopback tests. Laser delivery was never enabled. XP cable 1
was read back as disconnected; NICs 2–8 are absent. A screenshot-only XP check
still failed with `FrameArrived timed out: timed out waiting on channel`.
No XP input, new XP capture or physical-equipment connection occurred.

## Edge coverage fix

`frontend/SemanticColorLayers.cs` identifies opaque flat source brushes before
WPF blends them into the RGB page. Each color is rendered as a grayscale
coverage layer, with other geometry retained as white occluders. This preserves
clipping, transforms, drawing order, glyphs and partly covered edge pixels.
Dropping other colors' geometry would incorrectly expose hidden artwork.

On the actual saved filled-color Corel X7 print, the coverage reconstructs
**all 111,825 original RGB channels exactly**. The fix recovers **333 matched
edge samples** lost by exact flattened-RGB matching: 2,000 becomes 2,333.
The deliberately unmatched orange contributes 462 omitted samples, including
its own edges. The owner's choice to preserve X7 appearance is respected;
native gray edge samples are not replaced with XP's binary picture samples.

White paint remains excluded. Images, gradients, transparent brushes/groups
and masks report unsupported content. These are explicit review limitations,
not a general bitmap quantization implementation. The experimental reader uses
schema 3 and remains outside the installed production Scene/print path.

Evidence under `runtime/semantic-color-layers-20261019/`:

- `host-filled-intake/`, `host-vector-intake/`: new extraction of saved sources,
  not new application prints.
- `host-filled-review/verification.json`: exact reconstruction and raw/CG
  sample preservation across four marked draft cases.
- `composition-campaign-1729/verification.json`: 64 seeded synthetic native
  compositions with overlapping/rotated/clipped fills and pens, glyphs and white
  occlusion. Worst reconstruction error **1/255**, no held cases or source
  mutations. These are **not 64 XP captures**.
- `ordinary-reader-regression-r1/verification.json`: both actual saved host
  documents processed through the installed and experimental reader in ordinary
  mode. Source, engraving PNG, exposure and cut SVG bytes are identical;
  metadata matches ignoring absent/null fields. Both executable hashes remain
  unchanged. The installed reader was not replaced.

## Full job-attached settings review

`tools/review_color_job.py` is a standalone offline tool. It reads the source's
complete immutable PrintTicket snapshot, runs the separate experimental reader,
and writes marked `.jbs.draft` files and a hashed review report. It never reads a
mutable default palette and has no printer submission, hardware endpoint or
unmarked-output option. Ordinary preparation still rejects its drafts.

The current review requires UseColors at 167 DPI, Autostart Off, the established
flatbed profile and no other unresolved settings. It rejects scalar-only jobs,
conflicting snapshots, unsupported combinations, fractional palette powers,
malformed source/geometry and source or coverage hash changes. Native failures
and timeouts preserve a held report and logs. Production UseColors remains held.

Example, for a source that actually carries a supported full color snapshot:

```powershell
& 'C:\Users\xws\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m tools.review_color_job SOURCE.oxps NEW-REVIEW-DIRECTORY --intake-executable build/frontend-semantic-color-20261019/Aurora.XpsIntake.exe
```

`color_drafts.py` handles the independently observed single-raster marker to
vector boundary. With independent XP marker input, four complete original XP
color files match byte-for-byte except the mandatory draft marker. With actual
X7 input, commands and vector geometry still match; all 41 differing antialiased
marker samples are deliberately retained.

`per-job-review-campaign-r1/verification.json` records **eight synthetic full
ticket reprocessings** of the two saved host artwork documents. Enabled,
paused, disabled-color, sorted/unsorted and Raster Only cases pass. Seven cases
match independent XP commands, paths and raster processes. These are not eight
new host or XP prints, and do not validate the native Properties dialog again.

## One new actual mixed-artwork host capture

The agent created an owned CorelDRAW 11 document with six filled squares and
five thin colored outline squares in separate rows. Save/reopen preserves all
11 shapes, colors and geometry. The original CDR SHA-256 is
`699a9539c9677ed9257240050c287f7443e88411c49fc6141a4f70e2f8719cf7`.

Exactly **one** new print was submitted through the guarded Corel API to the
verified loopback Capture only queue. Capture:
`captures/host-color-mixed-preferences-20261020/6ef4b165-0e4c-4806-ad34-43fc6630db0c`.
Source SHA-256:
`f3674e101324c9432350df152049cea833bf98f2e2cc98ef7eaa5fd1a8f1bcb3`.
It carries scalar default settings, not a new full color Properties snapshot.

The mixed source produces exactly the same semantic fill layers and RGB as the
separate filled reference, plus all five vector identities shifted exactly
half an inch down. Exact RGB reconstruction still passes. With a clearly labeled
synthetic full snapshot, Raster Only exports the three raster regions and omits
all five paths. Both mode correctly **holds the unverified multiple-color raster
to vector boundary**, rather than guessing its pen/process/pause state.

Report: `host-mixed-verification-r1/verification.json`. A separate native
end-to-end test checks both the held and Raster Only cases.

## Verification and follow-up

Python full suite: **198 passed in 57.411s**, followed by **one additional passing
actual mixed-host integration test** added after that run. Do not call this a
199-test full-suite run. Native intake: **36 passed**, plus the 64-case synthetic
composition campaign. Relevant logs are in the same runtime directory.

Preserved diagnostic failures: the first per-job test compared JSON integer keys
with in-memory integer keys; its assertion was corrected, with a fresh passing
log. A default `unittest discover` invocation found zero tests and was corrected
to `discover -s tests`; only the successful 198-test run is counted. No product
failure remains from these diagnostics.

The next owner-present XP reference package is prepared and hash-verified at
`Z:\Aurora-XP-Reference\color-mixed-preferences-20261020`. It includes the Corel
11 document, instructions and copy-only collectors for enabled, paused and an
optional paused/disabled-blue case. **None has run in XP.** Their source package
and shared-copy verification are under
`runtime/xp-color-mixed-preferences-20261020/`.

The independent work has reached an evidence boundary. Additional broad repeats
of passing tests would not establish original-driver behavior. Owner choices
and the prepared next reference are recorded in the overnight handoff. JobServer
remains idle Capture only, the working default remains 167 DPI, and physical
color output/Windows 11 installation remain unverified.
