# Visible worker lanes (dispatch, watcher qualification, recovery)

Use this reference when dispatching a visible OMP/Droid worker or reviewer lane in a dedicated Herdr worktree, qualifying its completion watcher, or repairing a wake-guard alert. The canonical launcher contract, token generation, and dispatch record live in `worker-launch.md`.

## Dispatch invariants

1. Create the worker/review brief **inside the exact worker worktree** before launch. `.hermes/` state, including `conductor/briefs/`, is commonly untracked or ignored and does not follow a detached worktree. Alternatively use an absolute, verified shared evidence path the worker can read.
2. Verify the exact brief path from that worktree (`test -r ...`) before submitting the prompt. A missing or unreadable brief makes the result non-certifying; never infer a verdict from a different prompt. Cancel the AskUser prompt, repair the path, and rerun the same read-only review.
3. Record in Beads before dispatch: candidate SHA, review-worktree path, visible Herdr pane ID, model/routing, and read-only boundaries.
4. Launch the actual agent binary, not a help command. Require `herdr pane get <pane>` to report the intended agent and `agent_status: working` within 30 seconds before marking the Bead `in_progress`. A bare shell, `unknown`, or `idle` is a failed dispatch: return the Bead to `open` with a durable `dispatch_failure` note. Canonical tooling: `dispatch_worker.py --harness omp|droid --worker-pane <lane pane>` performs this verification (working status or harness PID proven in `/proc`) before qualification.
5. For an already-completed OMP pane, create a new Herdr workspace/pane for the next agent type; do not assume `pane run` replaces the finished agent session.
6. Preserve a failed dedicated worktree for reconciliation; do not delete it while its Bead or evidence is active.

## TUI pane discipline (OMP, Droid)

- A fresh OMP/Droid TUI can initialize after the first prompt injection. Inspect the visible composer after launch; if the brief remains staged, focus the pane and send exactly one `ENTER`, then require `agent_status=working` within 30 seconds. Text injected before the TUI is ready may be lost; treat that as a failed launch, preserve the worktree, and relaunch or resubmit from the initialized session.
- Persistent OMP/Droid TUI processes never exit at task end, so an exit-only watcher is not suitable. Launch the watcher with `--worker-pane <lane pane>` (plus `--idle-after-seconds`, default 600); after the idle threshold, three consecutive idle observations with no artifact produce a manual-reconcile wake. Every brief must name an absolute worker-created result JSON path plus the token-bound completion marker.
- If a legacy exit-only watcher is already attached and the worker-created artifact exists, kill only the exact watcher PID, record `manual_reconcile_tui_exit_unavailable`, independently parse the artifact, and advance to the appropriate review lane. Never synthesize a completion artifact.

## Completion watcher qualification

A plain `herdr wait agent-status ... done` is useful telemetry but is **not** a qualified Conductor completion watcher. `controller_idle_watchdog.py` qualifies a watcher only when Bead metadata exactly matches the live `watch_worker_completion.py` argv and process identity:

1. Start `watch_worker_completion.py` **before** worker completion, with a live worker PID and verified `/proc/<pid>/stat` start ticks, the current controller pane, and the current controller session.
2. Use an at-least-32-character hexadecimal `--marker-value` token.
3. Pass **absolute** `--result-json` and `--receipt` paths. Relative paths cannot satisfy the watchdog's exact-path qualification.
4. Persist these exact metadata keys on the Bead:

```text
conductor_pane
conductor_session
process_pid
process_start_ticks
watcher_pid
watcher_start_ticks
result_json          # absolute path
watcher_receipt      # absolute path
completion_token     # 32+ hex chars
```

5. The result JSON must be worker-created and contain the exact marker key/value before the worker process exits; the controller must never synthesize it. On retry, use a fresh token, result path, receipt path, worker PID/start ticks, and watcher handle.
6. After attaching, verify the watcher and worker process identities and that the result artifact does not predate attachment. Otherwise fail closed: preserve the receipt, terminate the watcher intentionally if replacing it, and attach a fresh watcher with corrected arguments and metadata.

Do not substitute approximate names such as `completion_watcher_pid`; the watchdog will classify the lane as unqualified.

## Completion artifact contract

The watcher validates the marker key/value given via `--marker-key`/`--marker-value` exactly; a missing or mismatched value produces no wake and a manual reconcile. `dispatch_worker.py` lanes use `--marker-key completionMarker`; the minimal review artifact shape names it `completionToken`:

```json
{
  "completionToken": "<32+ hex token>",
  "verdict": "PASS|PASS_WITH_NOTES|FAIL",
  "candidateSha": "<exact reviewed SHA>",
  "findings": "concise evidence"
}
```

The artifact certifies completion delivery only. Before accepting a review verdict, the controller must still inspect the visible pane output, Git state and diff, and the artifact, and must verify the candidate SHA and verdict separately. A bare Herdr `done` event is not a certified outcome.

## Controller watchdog session binding

A controller idle watchdog is session-bound. Immediately before starting or reusing it, read the controller pane's current `agent_session.value` via `herdr pane get <controller-pane>` and bind `--session-id` to that exact session, not a historical session stored in Beads. If the pane session changes, the watchdog still wakes with `controller_session_drift` carrying a rebinding instruction; retire the obsolete watchdog, record the mismatch durably, and rebind only after reconciling Beads, Git, process, and artifact state. A stale binding must never become a permanent non-wake.

## Kill hygiene

- Kill only exact watcher, launcher, or child PIDs recorded in the dispatch record or Bead metadata — never broad `pkill` patterns (launcher contract: `worker-launch.md`).
- On a controller handoff, retire watchers bound to the prior pane/session before dispatching.
- When a worker is done, clear its active claim and stop every watcher bound to that worker before reopening the lane, so the wake guard does not report stale `in_progress` state.
- A watcher that fails validation: preserve its receipt and terminate it intentionally when replacing it.

## Recovery

- If a worker or reviewer finishes without a qualified watcher, or could not read its brief, mark the attempt non-certifying in Beads, retain the pane transcript as evidence, repair the handoff, and rerun the read-only review. Do not start implementation based on that attempt.
- If a pane is `done` or `blocked` while Beads says `in_progress`, reconcile pane output, Git diff, artifact, and watcher receipt immediately. Clear or reclassify the claim; never leave an unqualified in-progress lane.
- A plan-review `PASS_WITH_NOTES` is not implementation authorization when findings change the frozen plan: record the artifact and the exact required amendment, return the planning lane to `open`/ready for a narrow plan-only amendment, and dispatch a verified plan-only worker. Do not authorize implementation until the amendment receives fresh review; never silently reinterpret a plan-review pass as product implementation approval.
- If an agent is blocked only on its own scoped read-only command approval, approve that command and verify it returns to `working`; this is not a human-product-decision boundary.
- If a verified plan amendment is uncommitted and policy or user authority requires a commit decision, mark the mission/task `waiting_user` or `blocked` with the exact authority boundary. Do not leave it `ready`, which creates a wake-guard loop.
