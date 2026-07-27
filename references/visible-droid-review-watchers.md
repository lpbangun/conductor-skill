# Visible Droid review and qualified completion watchers

Use this when a critical review must run visibly in a Herdr Droid pane while the controller idle watchdog enforces qualified completion supervision.

## Detached-worktree brief rule

A brief created under the integration checkout's ignored `.hermes/conductor/briefs/` is **not present** in a detached reviewer worktree. Before dispatch, create the exact brief at the same relative path inside the reviewer worktree (or use a deliberate absolute path that Droid can read). Verify it exists from the reviewer worktree before submitting the prompt. A Droid refusal caused by a missing brief is non-certifying; cancel the AskUser prompt, repair the path, and rerun the same read-only review.

## Qualified watcher contract

`controller_idle_watchdog.py` recognizes a watcher only when Beads task metadata exactly matches the live `watch_worker_completion.py` process.

1. Start `watch_worker_completion.py` **before** worker completion with an existing worker PID and verified `/proc/<pid>/stat` start ticks.
2. Use an at-least-32-character hexadecimal `--marker-value` token.
3. Pass **absolute** `--result-json` and `--receipt` paths. Relative paths do not satisfy watchdog equality checks.
4. Persist these exact metadata keys on the Bead:
   - `watcher_pid`, `watcher_start_ticks`
   - `process_pid`, `process_start_ticks`
   - `result_json`, `watcher_receipt` (absolute paths)
   - `completion_token`
   - `conductor_pane`, `conductor_session`
5. Instruct Droid before completion to create the result JSON with the exact marker key/value. The artifact must be worker-created; the controller must not synthesize it.
6. Verify the watcher process and worker process identities after attaching. If a watcher fails validation, preserve its receipt, terminate it intentionally if replacing it, and create a fresh watcher with corrected arguments/metadata.

## Minimal review artifact shape

```json
{
  "completionToken": "<32+ hex token>",
  "verdict": "PASS|PASS_WITH_NOTES|FAIL",
  "candidateSha": "<exact reviewed SHA>",
  "findings": "concise evidence"
}
```

This artifact validates completion delivery only; the controller must still inspect the visible Droid output, Git state, and artifact before accepting a review verdict.
