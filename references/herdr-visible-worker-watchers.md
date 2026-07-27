# Visible Herdr worker dispatch and watcher qualification

Use this when a Conductor lane needs a visible OMP/Droid agent in a dedicated worktree.

## Preflight

1. Create the review/worker brief **inside the exact dedicated worktree** before launching the agent. `.hermes/` state is commonly untracked and does not follow a detached worktree automatically.
2. For an already-completed OMP pane, create a new Herdr workspace/pane for the next agent type; do not assume `pane run` replaces the finished agent session.
3. Launch the actual agent binary, not a help command. Verify `herdr pane get` shows the intended `agent` and `agent_status=working` within 30 seconds before recording the Beads claim.
4. Read the current controller pane’s `agent_session.value` immediately before starting a controller idle watchdog. Bind the watchdog to that exact session, not a historical session stored in Beads.

## Canonical completion watcher qualification

A plain `herdr wait agent-status ... done` is a useful notification but is **not** a qualified Conductor completion watcher. For `watch_worker_completion.py`, use:

- a live worker PID and its `/proc/<pid>/stat` start ticks;
- a worker-created JSON result artifact written after watcher attachment;
- a 32-character hexadecimal `completionToken` in the artifact;
- absolute `--result-json` and `--receipt` paths;
- the current controller pane/session.

The task metadata must exactly match the idle watchdog’s expected names and values:

```text
conductor_pane
conductor_session
process_pid
process_start_ticks
watcher_pid
watcher_start_ticks
result_json          # absolute path
watcher_receipt       # absolute path
completion_token      # 32 hex chars
```

Do not substitute approximate names such as `completion_watcher_pid` or relative artifact paths: `controller_idle_watchdog.py` will classify the lane as unqualified.

## TUI prompt and watcher discipline

- A fresh OMP/Droid TUI can initialize after the first prompt injection. Inspect the visible composer after launch; if the brief remains staged, focus the pane and send exactly one `ENTER`, then require `agent_status=working` within 30 seconds. Text injected before the TUI is ready may be lost; treat that as a failed launch, preserve the worktree, and relaunch/submit from the initialized session.
- Persistent OMP/Droid TUI processes do not exit when the task ends. Launch the pane-aware watcher with `--worker-pane <lane-pane>` and require every brief to name an absolute worker-created result JSON path plus a token-bound completion marker. An exit-only watcher is not suitable for a persistent TUI.
- If a legacy exit-only watcher is already attached and the worker-created artifact exists, kill only the exact watcher PID, record `manual_reconcile_tui_exit_unavailable`, independently parse the artifact, and advance to the appropriate review lane. Never synthesize a completion artifact.

## Completion/recovery

- If an agent finishes without a valid qualified watcher, reconcile its pane output, Git diff, and result artifact before changing Beads.
- For a plan-review `PASS_WITH_NOTES`, record actionable blocking findings and return the plan lane to ready for a narrow plan-only amendment; do not authorize implementation until the amendment receives fresh review.
- When a worker is done, clear its active claim and stop any watcher bound to that worker before reopening the lane, so the wake guard does not report stale `in_progress` state.
