# Visible-agent review recovery

Use this when a Conductor lane runs in a dedicated Herdr worktree with a visible Droid/OMP reviewer.

## Dispatch invariants

1. Create the review brief **inside the agent's exact worktree**. Controller-local `.hermes/conductor/briefs/` files are not present in detached worktrees unless copied or recreated there.
2. After launch, verify `herdr pane get <pane>` reports the expected agent and `working` within 30 seconds before claiming the Bead `in_progress`.
3. For a worker-created completion artifact watcher, persist all fields that `controller_idle_watchdog.py` qualifies against:
   - `conductor_pane`, `conductor_session`
   - `process_pid`, `process_start_ticks`
   - `watcher_pid`, `watcher_start_ticks`
   - absolute `result_json`, absolute `watcher_receipt`
   - a 32-character hexadecimal `completion_token`
4. Invoke `watch_worker_completion.py` with **absolute** artifact and receipt paths. Relative paths cannot satisfy the watchdog's exact-path qualification.
5. Ask the visible agent to write the artifact before its worker process exits, with the exact token. Verify the artifact's candidate SHA and verdict separately; do not treat a bare Herdr `done` event as a certified review outcome.

## Recovery

- If the pane is `done`/`blocked` but Beads says `in_progress`, reconcile pane output, Git diff, artifact, and watcher receipt immediately. Clear or reclassify the claim; do not leave an unqualified in-progress lane.
- If a review returns `PASS_WITH_NOTES`, record actionable findings and return the task to a plan-amendment/review state rather than dispatching implementation prematurely.
- If an agent is blocked only on its own scoped read-only command approval, approve that command and verify it returns to `working`; this is not a human-product-decision boundary.
- If a verified plan amendment is uncommitted and policy/user authority requires a commit decision, mark the mission/task `waiting_user` or `blocked` with the exact authority boundary. Do not leave it `ready`, which creates a wake-guard loop.
