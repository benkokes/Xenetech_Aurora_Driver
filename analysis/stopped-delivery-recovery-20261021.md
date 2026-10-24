# Stopped delivery recovery — October 21

The owner reported the unresolved-delivery popup while attempting a vector
print. The marker identified job f42edf1d-14d3-49c9-87ca-ef1bfe97c572,
delivery b62dcac0-faaa-4b44-a984-1706de462861, print
b7db8268-4f0b-4c1d-b2aa-2d91d79608be, in desktop session
9ef98780-b031-4e7a-92e3-6a2a2b95e1f0. This BayBridge submission was received
October 20 at 21:42:20 Pacific. It uploaded once and returned channel-5 E1,
without a successful completion report. Its pending marker correctly blocked
subsequent delivery. The later 21:44:27 print was captured locally, never sent.

The owner specifically confirmed: “21:42 job was stopped; machine is idle.”
Added an explicit `stopped` physical-outcome choice to the store, CLI, and
desktop dialog. It records delivery_failed with operator_outcome=stopped,
retains earlier E1/error events, and clears only the matching controller marker.
Resolution neither sends nor enables printing. Desktop resolution also removes
the matching transient error, preserving unrelated errors. The guard popup now
points to Record physical outcome instead of giving only a filesystem path.
These desktop UI changes load on the next ordinary JobServer restart.

Resolved this exact delivery locally using the confirmed stopped outcome.
Marker cleared; no physical connection, probe, resend, queue retry, live enable,
or XP network change occurred. Capture-only mode retained. The running window
may retain its earlier footer error until a new live session or restart; the
durable job record and delivery guard have been reconciled.

Evidence is immutable in runtime/delivery-incident-20261021/investigation.json,
the original marker/status/transcripts, and resolution.json. The actual RX was
replayed both whole and byte-fragmented: E1 remains uncertain with no
host_terminate request. Sixteen sender tests passed, including stopped recovery
without network calls, no resend, history preservation, and preservation of an
unrelated desktop error.

The source XPS for this job contains black stroked paths and no recognized red
cut paths. Intake produced one raster and zero cuts, although the selected
output mode was Both. The snapshot had raster 88.73%/30 ips, vector25.35%/1ips,
167 DPI, Autostart On. These were owner-selected settings, not the earlier
54% calibration settings. Do not silently replace them or reinterpret E1 as
an empty-vector success.

The owner described XP's desired behavior: vector outlines that are too thick
yield a harmless empty job; changing them to hairline permits the next print.
The replacement does not yet match that full behavior. Production Vector Only
remains held; the currently validated transfer requires a CG raster job.
Production cut detection currently selects red thin strokes. A future change
must explicitly address vector-only line classification, empty/no-cut outcomes,
and native vector transfer rather than suppressing delivery uncertainty or
silently sending raster output. Empty vector work should be a recoverable
“nothing to cut” outcome, with no blocking unresolved delivery record.

The earlier normal CorelDRAW sheet (print17d81e98, job
1fc84fe2-8d77-401e-9236-19c0670324cf) did complete: one upload, TX exactly
matching its wire plan, end0, job_time62.45 seconds, known set_xyup_feed warning.
Snapshot54%/30ips, vector15%/1ips/1000PPI,167DPI,AutostartOff. Owner confirmed
starting it and selecting Capture only, but final visual appearance has not
been separately confirmed for that normal-path run.
