# Offline XP reference collector

This replaces the first collector, which could archive a stable zero-byte
intermediate and incorrectly report CAPTURED. Preserve old captures and logs.

The collector never prints, changes printer preferences, launches programs or
connects to the laser. Before starting it in XP, disconnect the VM's network
cable and close XP JobServer. Normal mode checks for JobServer.exe and connected
network adapters each polling cycle and immediately before copying. These WMI
checks supplement the operator's/VirtualBox's cable and process checks.

1. Copy `collect-new-jobs.vbs` into a **new empty shared test root**. Keep the
   existing collector and evidence untouched. Run this script in XP after
   inspecting it. A Windows Open File security warning requires the owner to
   accept it directly.
2. On the host, arm a fresh case:
   `python -m tools.xp_reference_collector arm <host-test-root> <case-label>`.
   Wait for ARMED before submitting exactly one authorized XP file-only print.
   Labels contain 1–48 lowercase letters, digits or hyphens.
3. The script watches the existing `C:\xfiles\etherin\Default.jbs` without
   changing it. It waits for a changed file with a bounded nonempty size,
   `!ZX` header, final END_PLOT line, and matching complete binary snapshots
   one second apart. Existing destinations are never overwritten.
4. A copied file is called `candidate.jbs` and status is **CANDIDATE**, not a
   successful capture. Run:
   `python -m tools.xp_reference_collector verify <host-test-root> <case-label>`.
   The host independently decodes picture dimensions, full payloads, row
   trailers, commands and final termination. Autostart, draft and empty-artwork
   jobs are rejected. Only then are `Default.jbs` and `verified.json` published.
5. If validation fails, **do not print again**. Preserve the candidate. Inspect
   XP's completed inbox and copy it into a fresh case for verification. A new
   case is also required after interrupted publication; never overwrite a
   failed attempt to make a report pass.
6. To stop, create `stop-collector.txt` in the test root and wait for STOPPED.
   It also stops after 30 minutes. Stop before restoring XP's backed-up inbox.

`--snapshot <source> <destination>` is a host fixture-test mode: it performs
the bounded framing/stability/copy checks once without WMI or polling XP.
It still reports CANDIDATE ONLY and still needs host decoding. It must not be
treated as verification of XP's full watch loop or offline-state checks.

The fixture tests are in `tests/test_xp_reference_collector.py`. They require
no private files. Actual Windows Script Host cases run on Windows where
`cscript.exe` is available; other tests run with Python alone. Windows Script
Host must be able to read its existing per-user settings. No settings or
security policy changes are needed by the tests.
