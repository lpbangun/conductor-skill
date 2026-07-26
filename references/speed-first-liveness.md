# Speed-first scheduling and completion liveness

## Objective

Useful throughput is the scheduling objective. Resource policy is an admission constraint and circuit breaker; it is not the quantity Conductor minimizes. Given a reconciled ready graph, choose the largest safe set of productive, ownership-disjoint lanes that fits the approved process and weighted capacity. Break equal-width choices by Beads priority and stable task ID.

A process is productive only when it advances declared mission acceptance. Duplicate broad suites, unchanged-SHA verification, speculative work, and workers contending for the same mutable seam do not count.

One active worker is valid only when the evidence shows one of:

- no second productive dependency-ready lane exists;
- every possible second lane conflicts with a current owner or unstable shared seam;
- process or weighted capacity blocks every second lane;
- current valid pressure signals block new admission.

Record that concrete reason. “Conserving resources” is not sufficient.

## Deterministic scheduling decision

Build one JSON snapshot from authoritative Beads, Herdr, mission contract, and current pressure data, then run:

```bash
python3 scripts/scheduler_decision.py snapshot.json
```

The snapshot contains:

- `ready`: every dependency-ready task, not only the first result;
- `active`: live mission-owned workers;
- task `productive`, `slotCost`, `ramReserveGb`, `priority`, non-empty `ownershipKeys`, and optional `conflictsWith` fields;
- approved worker/weighted/pressure budgets;
- fresh available-RAM, PSI-full, active-swap-out, and sample-age measurements;
- non-launch `pendingControlActions`, such as artifact harvest or pane cleanup.

Cumulative swap occupancy is not an admission input. Invalid or stale required measurements fail closed for new launch while control actions continue; `sampleAgeSeconds` must be at most the approved `resourceSampleSeconds`. For a simultaneous dispatch set, the sum of newly admitted `ramReserveGb` values must leave strictly more than `minAvailableRamGb` in the live post-active `availableRamGb` snapshot.

The planner is advisory control-plane code: Conductor still verifies claims, paths, ownership, and evidence before performing actions. Do not hand-edit its selection to serialize a safe lane. If its output is wrong, stop and fix the snapshot or planner test.

## Completion wake contract

Delegated continuation requires an actual wake path. For every worker, launch a separate watcher process after the full-attempt lifecycle identity is verified. `WORKER_PID` below means the stable process whose lifetime covers every mutating provider attempt: a direct worker PID for a direct launch, or the launcher PID for a fallback-capable wrapper. Never bind to the first provider child when the launcher may replace it after 401, 429, timeout, or another retryable failure:

```bash
python3 "$CONDUCTOR_SKILL_DIR/scripts/watch_worker_completion.py" \
  --worker-pid "$WORKER_PID" \
  --worker-start-ticks "$WORKER_START_TICKS" \
  --task-id "$TASK_ID" \
  --result-json "$RESULT_JSON" \
  --marker-key completionMarker \
  --marker-value "$EXPECTED_MARKER" \
  --conductor-pane "$CONDUCTOR_PANE" \
  --conductor-session "$CONDUCTOR_SESSION_ID" \
  --receipt "$MISSION_DIR/watchers/$TASK_ID.json"
```

Before launch, resolve one canonical result-artifact path and put that exact absolute path in both the worker brief and watcher command. Launch the watcher via the exact absolute package script path (not a basename-only copy). Record the watcher PID, exact lifecycle identity, launcher command, actual accepted provider/model after fallback, exact per-attempt artifact path, dispatch-unique completion token, conductor pane, conductor session, and receipt path in Beads (`conductor_session` metadata must match the live controller session). Do not assume the worker worktree and control worktree share `.hermes/conductor/results`; if a worker writes only inside its own worktree, retire the mismatched watcher, inspect the exact artifact and candidate SHA, copy the artifact into durable control evidence, and only then review/reconcile. Generate the token with at least 128 bits of randomness (for example `secrets.token_hex(16)`), place it in the worker brief, and never reuse it across retries or tasks. The watcher accepts only a hexadecimal token of at least 32 characters. The per-attempt result path must not exist at watcher attachment; any pre-existing file or symlink is replay/ambiguous evidence and requires manual reconciliation. On pidfd-capable hosts, verify PID/start-ticks identity again after opening the pidfd so PID reuse cannot cross the check/open boundary. Verify the watcher process is live before the Conductor turn may become idle. A receipt bound to a replaced child PID is non-qualifying even if the eventual fallback writes the expected artifact; its exit timestamp and latency do not describe end-to-end completion.

The watcher:

1. blocks on the external full-attempt lifecycle process, using Linux pidfd when available;
2. never creates or edits worker result evidence;
3. validates the worker-created completion artifact and exact marker;
4. verifies the actual Conductor pane exists;
5. sends a completion event to that pane through Herdr and presses Enter;
6. writes an atomic receipt with observed exit, artifact validation, wake delivery, latency, and any failure.

A background `process wait` handle, a lease, a heartbeat, or a watcher that only exits silently is not a completion-wake handle. Never return idle while an active worker is unwatched. If a verified watcher cannot be established, keep the Conductor turn in foreground supervision or downgrade to checkpointed/session-orchestrated behavior and state that automatic continuation is unavailable.

After a wake, reconcile the exact worker artifact and live Git/Herdr/Beads state before closure. Then immediately resample pressure, run the scheduling decision, and refill every admitted productive lane.

## Controller idle watchdog

Worker completion watchers cannot recover a controller that identifies a ready frontier and then ends its own turn before dispatch. In delegated mode, run one transparent timer guard for the dedicated controller pane:

```bash
python3 "$CONDUCTOR_SKILL_DIR/scripts/controller_idle_watchdog.py" \
  --repo "$REPO" \
  --mission-id "$MISSION_ID" \
  --pane "$CONDUCTOR_PANE" \
  --session-id "$CONDUCTOR_SESSION_ID" \
  --state "$REPO/.hermes/conductor/controller-watchdog.json" \
  --interval-seconds 30 \
  --min-repeat-seconds 90
```

Before launch, query `herdr pane get` and bind `CONDUCTOR_SESSION_ID` to the current Hermes agent session; verify the exact controller cwd equals `REPO`. Run the watchdog as a tracked mission-owned process and record PID plus `/proc/<pid>/stat` start ticks. Verify it remains live after launch. A process-lifetime lock permits exactly one watchdog for the state path. Every 30 seconds it checks only enough evidence to decide whether an idle pane needs a wake. It queries the complete frontier with `--limit 0`, revalidates pane/session/cwd immediately before submission, and suppresses wake while the controller is working or while each in-progress task has a qualified live watcher. Qualification requires the exact package `watch_worker_completion.py` absolute path in the process argv, exact Beads metadata for watcher PID and watcher start ticks, lifecycle PID/start ticks, a hexadecimal completion token of at least 32 characters, absolute non-null receipt and `result_json` paths, current pane, and matching controller session on both argv (`--conductor-session`) and Beads `conductor_session` metadata. It rate-limits an unchanged frontier to one wake per 90 seconds and wakes immediately when the frontier fingerprint changes. A transient Herdr, Beads, process, or filesystem observation error is logged and retried on the next interval instead of terminating the daemon. The daemon exits cleanly when mission status is no longer `active`.

The guard does not schedule. It never claims/closes tasks, mutates Beads or Git, runs tests, chooses a lane, or invokes `scheduler_decision.py`; its only side effect is a verified `herdr pane run` to an idle controller. The dedicated Conductor remains the sole control-plane authority. A legitimate human-only boundary must durably transition `mission.status` away from `active` before the controller returns final; the guard then exits cleanly. Stop the guard on pause, controller handoff, mission closure, or pane retirement.

## Tight end-to-end liveness evaluation

The canary must use all of these real boundaries:

- an external worker process;
- a worker-created completion artifact;
- a separate watcher process;
- an actual Conductor pane or isolated Herdr canary pane;
- measured completion-to-wake latency;
- a reconciled graph that exposes two productive lanes after completion;
- observed two productive lanes selected/refilled when admitted.

Direct reconcile calls cannot satisfy this evaluation. A canary must fail if it directly invokes planner reconciliation to manufacture the wake transition, if the watcher writes the result artifact, if no pane receives the wake, if the completed task remains claimed, or if two safe lanes exist and fewer than two are selected.

Run the unit/e2e regression:

```bash
python3 scripts/test_scheduler_liveness.py -v
```

For release qualification, also run an isolated live-Herdr canary that starts a line-receiving disposable pane, launches the external worker and watcher, confirms the pane received the completion event, and cleans every owned process/pane. Preserve command outputs and digests. No live product repository may be used.

## Completion criteria

A scheduling transition is live only when:

- every active worker has a verified completion-wake handle;
- every completed worker is harvested into authoritative Beads state within the bounded wake interval;
- the whole ready queue is reconsidered after the transition;
- the largest safe productive set is dispatched;
- any sub-two-worker state has a concrete graph, ownership, capacity, or pressure reason;
- no mission-owned watcher or completed pane is leaked after pause or closure.
