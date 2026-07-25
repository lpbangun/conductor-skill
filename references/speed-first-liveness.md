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

Cumulative swap occupancy is not an admission input. Invalid or stale required measurements fail closed for new launch while control actions continue. For a simultaneous dispatch set, the sum of newly admitted `ramReserveGb` values must leave strictly more than `minAvailableRamGb` in the live post-active `availableRamGb` snapshot.

The planner is advisory control-plane code: Conductor still verifies claims, paths, ownership, and evidence before performing actions. Do not hand-edit its selection to serialize a safe lane. If its output is wrong, stop and fix the snapshot or planner test.

## Completion wake contract

Delegated continuation requires an actual wake path. For every worker, launch a separate watcher process after startup identity is verified:

```bash
python3 scripts/watch_worker_completion.py \
  --worker-pid "$WORKER_PID" \
  --worker-start-ticks "$WORKER_START_TICKS" \
  --task-id "$TASK_ID" \
  --result-json "$RESULT_JSON" \
  --marker-key completionMarker \
  --marker-value "$EXPECTED_MARKER" \
  --conductor-pane "$CONDUCTOR_PANE" \
  --receipt "$MISSION_DIR/watchers/$TASK_ID.json"
```

Record the watcher PID, exact worker identity, exact per-attempt artifact path, dispatch-unique completion token, conductor pane, and receipt path in Beads. Generate the token with at least 128 bits of randomness (for example `secrets.token_hex(16)`), place it in the worker brief, and never reuse it across retries or tasks. The watcher accepts only a hexadecimal token of at least 32 characters. Verify the watcher process is live before the Conductor turn may become idle.

The watcher:

1. blocks on the external worker process, using Linux pidfd when available;
2. never creates or edits worker result evidence;
3. validates the worker-created completion artifact and exact marker;
4. verifies the actual Conductor pane exists;
5. sends a completion event to that pane through Herdr and presses Enter;
6. writes an atomic receipt with observed exit, artifact validation, wake delivery, latency, and any failure.

A background `process wait` handle, a lease, a heartbeat, or a watcher that only exits silently is not a completion-wake handle. Never return idle while an active worker is unwatched. If a verified watcher cannot be established, keep the Conductor turn in foreground supervision or downgrade to checkpointed/session-orchestrated behavior and state that automatic continuation is unavailable.

After a wake, reconcile the exact worker artifact and live Git/Herdr/Beads state before closure. Then immediately resample pressure, run the scheduling decision, and refill every admitted productive lane.

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
