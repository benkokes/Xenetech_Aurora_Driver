# JobServer completion time and duration — October 22

Added Completed and Duration columns to the normal desktop print history and
the corresponding completion information to the selected-job details. Existing
queue records already store the needed data; no database migration or timestamp
backfill is required. Completion uses the saved delivery.updated time when the
successful controller report was received. Duration uses result.job_time, not
received-to-finished or connection elapsed time, which can include manual Start
waiting. Times use the computer's local timezone. Duration retains milliseconds
and supports hours. The window is wider and has horizontal scrolling.

Waiting, unsent, failed, and no-cut work shows dashes. An operator-confirmed
completion without a controller report also shows dashes: the reconciliation
time is not evidence of the actual physical finish. Missing or invalid timing
values do not crash the history display. Existing settings/status columns and
delivery behavior are unchanged.

Six timing tests pass, covering report-versus-queue timing, operator resolution,
pending/error/no-cut states, missing duration, minute/hour rounding, and invalid
values. A hidden Tk window using saved real rows passed its layout check with
all seven columns and horizontal scrolling. No real backend was constructed or
controlled and socket creation was prohibited. Real JobServer stayed live.

The native Tk preview required execution outside the restricted environment to
load Tcl. Its initial stub lacked endpoint and was corrected; no product code
defect resulted. The first timing test used a pre-1970 local date that Windows
could not convert with astimezone; short timestamps now use local fromtimestamp
directly and the timing fixture uses a modern epoch. All final checks pass.
Reports: runtime/jobserver-history-timing-20261022/timing-tests-final.log and
layout-check.json. No physical print, probe, settings change or replay occurred.

Saved real history renders:
- Aurora-Mixed-Test.cdr: completed10/22 18:16:01, duration1:36.946.
- BayBridge: completed10/22 18:01:22, duration0:50.214.

The owner has been asked to restart JobServer and check that both columns are
visible. No new test print is required. Restart defaults to Capture only; the
owner can enable laser printing for subsequent prepared work as usual.


The owner subsequently restarted JobServer and confirmed both columns are
visible. The UI check is complete; no physical print was required.
