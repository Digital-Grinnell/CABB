# Function 17: FAILED - Restore Metadata from Previous Version

## Status

**FAILED / BLOCKED**

Function 17 is no longer considered operational.

## Failure Reason

After multiple implementation attempts (API + Selenium MDE automation + manual-recording path),
Alma consistently blocks restore actions in the Versions UI (rows and restore controls remain
disabled/unresponsive in active workflows). This prevents safe, repeatable bulk automation.

Because Alma does not provide a reliable bulk restore API endpoint for this path, this function
is a dead end in CABB and has been marked failed.

## Current Behavior in CABB

- The Function 17 button remains visible for historical context.
- Running it returns a FAILED status message and does not execute restore automation.

## Recommendation

Use manual Alma workflows for one-off restorations, or request a supported bulk/API restore
capability through Alma product channels.

## Why This Function Was Attempted

Function 11 CSV overlay workflows can overwrite or remove metadata unexpectedly. Function 17 was
intended as a bulk recovery path when records needed to be rolled back to earlier metadata versions.

## Historical Notes

Previous attempts included:

- Alma API version-history endpoint usage (`/bibs/{mms_id}/versions`) which returned HTTP 404.
- Selenium-based MDE automation with login/DUO handling, iframe handling, and selector hardening.
- Selenium IDE-assisted manual capture to stabilize per-record actions.

All approaches converged on the same Alma-side block at restore interaction time.
