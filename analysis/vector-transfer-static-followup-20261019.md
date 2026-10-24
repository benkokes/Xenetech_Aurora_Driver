# Vector Only transfer: static follow-up

This extends `runtime/xp-output-modes-20261018/vector-transfer-static-evidence.json`
using the same JobServer binary, SHA-256
`a82fd733518044c0f1cc856d0f5106a1318f06923c36deb33486a4b23c7cc76b`.
The binary was read, not loaded or executed. No controller connection occurred.

## Fresh no-raster conversion path

Function 0x00418ff0 sends `msg Preprocessing the job...` at 0x00419026, then
calls `BmpPict2!ConvertRasterJob` at 0x004190d5. Its dispatch table maps return
9 to 0x004190ef, constructing `ERROR: Nothing to Convert` and jumping directly
to its cleanup/return path at 0x004191c4.

That branch does **not** pass through the `ifexists jobtype 5 jobtype` send at
0x00419199. This is a narrower, useful conclusion: it establishes the local
branch behavior, not the complete network transfer profile or the controller's
previous jobtype state. Other caller paths can select cached conversions.

Caller code 0x0041a384–0x0041a3a6 recognizes the Nothing to Convert result,
restores the original source path as the returned selection and removes the
unused converted file. This is legacy behavior observed statically; no file was
removed during this analysis.

The HotWatch caller invokes that selection routine at 0x0040b985. Its ordinary
continuation at 0x0040b9f4 sends the clear/Please Stand By messages, formats
`JM_PATH` using the selected path at 0x0040ba2b, and formats
`HOTWATCH_CYCLE_START` using its basename at 0x0040ba74. This supports a candidate
flow using the original vector source path rather than the raster Convert
path. The exact source location must come from the working XP configuration,
not from guessing a hard-coded modern host path.

## Cached converted files can take a different branch

Selection code probes the converted filename at 0x00419f9f and the source at
0x00419fbb. It compares their last-write FILETIMEs at 0x0041a007. If the converted
file is at least as recent as the source and `FLUSH_CONVERTED` is false, it
chooses the existing converted path and emits a dynamic jobtype command at
0x0041a053–0x0041a070, bypassing fresh conversion.

Consequently, a future independent legacy Vector Only protocol observation
should use a fresh uniquely named source, or otherwise document the cache and
timestamps. Reusing Default.jbs with a stale converted file could observe the
cache branch rather than the fresh no-raster branch. Preserve existing jobs;
do not delete or purge the owner's conversion cache merely to obtain a trace.
The replacement's per-capture UUID and immutable hashes already avoid this
legacy naming/cache dependence.

## Remaining evidence

These findings refine the future capture and simulator design. They still do
not establish the full handshake, initial jobtype state, any controller-specific
vector framing, completion/report channel or physical behavior. No candidate
was added to `wire.py`, no sender guard was relaxed, and Vector Only remains
held. A complete original-sender trace against a prepared laser or a separately
isolated legacy-protocol recorder remains necessary.
