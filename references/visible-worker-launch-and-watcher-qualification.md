# Visible worker launch and watcher qualification

Use this reference when dispatching a visible OMP/Droid lane or repairing a wake-guard alert.

## Launch discipline

1. Do not mark a Bead `in_progress` merely because a Herdr pane/workspace exists. Start the actual agent command and require `herdr pane get <pane>` to report `agent_status: working` within 30 seconds. A bare shell, `unknown`, or `idle` is a failed dispatch; return the Bead to `open` with a durable `dispatch_failure` note.
2. A dedicated detached review/planning worktree does not inherit ignored/uncommitted `.hermes/conductor/` state from the integration checkout. Put the brief/result paths inside the worker worktree before launch, or use an absolute, verified shared evidence path. Confirm the worker can read the brief before treating its result as certifying.
3. Preserve a failed dedicated worktree for reconciliation; do not delete it while its Bead/evidence is active.

## Canonical completion-watcher contract

`controller_idle_watchdog.py` qualifies a completion watcher only when Bead metadata exactly matches the live `watch_worker_completion.py` argv and process identity. Record all of:

- `conductor_pane` and `conductor_session`
- `watcher_pid`, `watcher_start_ticks`
- `process_pid`, `process_start_ticks`
- absolute `result_json` and `watcher_receipt` paths
- `completion_token`: at least 32 hexadecimal characters

The worker-created result JSON must contain the marker key/value before the worker exits. Relative artifact paths and convenience metadata such as `completion_watcher_pid` do **not** satisfy qualification. If attaching a watcher late, verify that the result artifact does not predate attachment; otherwise fail closed and reconcile manually.

## Watchdog rebinding

A controller watchdog is session-bound. Before starting or reusing it, inspect `herdr pane get <controller-pane>` and bind `--session-id` to the current `agent_session.value`. If the pane session changes, stop the obsolete watchdog, record the mismatch durably, and rebind only after reconciling Beads/Git/process/artifact state.

## Plan-review handoff

A `PASS_WITH_NOTES` review is not implementation authorization when a medium finding changes the frozen plan. Record the artifact and exact required amendment, return the planning lane to `open`, then dispatch a verified plan-only worker. Do not silently reinterpret a plan-review pass as product implementation approval.
