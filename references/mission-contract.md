# Mission Contract

The mission contract freezes the user-approved decision envelope. Beads remains the runtime authority for task state; this file records policy that must not drift implicitly.

Default location in the integration checkout:

```text
.hermes/conductor/mission.json
```

Add it to `.git/info/exclude` when the project does not want local orchestration state committed. Workers receive the relevant contract fields in their brief; they do not mutate this file.

## Activation rule

A draft may use `mission.status: proposed` and leave approval/ledger IDs empty. Approval and activation are separate gates. After the user approves the envelope, run:

```bash
python3 "${HERMES_HOME:-$HOME/.hermes}/skills/autonomous-ai-agents/conductor/scripts/validate_mission.py" \
  .hermes/conductor/mission.json --require-approved
```

Then bootstrap/reconcile Beads, write the real epic ID, set `mission.status` to `active`, and run:

```bash
python3 "${HERMES_HOME:-$HOME/.hermes}/skills/autonomous-ai-agents/conductor/scripts/validate_mission.py" \
  .hermes/conductor/mission.json --require-active
```

`--require-approved` proves that the approved envelope is executable; `--require-active` additionally proves the contract has an active-capable status and non-placeholder ledger identity. Live Git/Beads/Herdr reconciliation remains required; the validator does not replace it.

## Required fields

### `mission`

- `name`: concise human-readable mission name.
- `objective`: measurable target, not “make tests pass.”
- `repo`: absolute path to the authoritative repository.
- `integrationBranch`: branch receiving serialized local integration.
- `milestone`: named stop/acceptance boundary.
- `status`: `proposed`, `approved`, `active`, `waiting_user`, `paused`, `complete`, or `aborted`.
- `supervisionMode`: `interactive`, `checkpointed`, or `delegated`.
- `inScope` / `outOfScope`: non-empty string arrays defining the decision envelope.
- `acceptance`: observable evidence required for mission completion.

### `authority`

- `approvedBy` and `approvedAt`: non-empty for approved/active missions.
- `localIntegrationAuthorized`: permits only reviewed local integration into `integrationBranch`.
- `integrationOwner`: stable identity allowed to acquire the Beads merge slot; normally `conductor`.
- `pushAuthorized`: defaults false.
- `authorizedPushTarget`: required when push is true, e.g. `origin feature/milestone`; it does not authorize another remote/branch.
- `destructiveOpsAuthorized`: defaults false. Even when true, the exact destructive action still requires an explicit task and pre-action state inspection.
- `releaseAuthorized`: defaults false. Permits a named release action only.
- `releaseTarget`: required when `releaseAuthorized` is true; an exact, non-placeholder target (e.g. `v1.2.3` or `origin tag v1.2.3`). Unauthorized releases must not be implied.
- `deployAuthorized`: defaults false. Permits a named deployment action only.
- `deployTarget`: required when `deployAuthorized` is true; an exact, non-placeholder target (e.g. `staging` or `prod-cluster-a`). Unauthorized deploys must not be implied.
- `cleanupAuthorized`: defaults false. Permits only the named cleanup scopes.
- `cleanupTargets`: required (non-empty) when `cleanupAuthorized` is true; an array of exact, non-placeholder scopes (e.g. `feature/<branch>` worktrees, named panes). Does not authorize destructive operations or deletion of unrelated state.

Authority does not transit: local commit ≠ merge, merge ≠ push, push ≠ release/deploy, release ≠ deploy, and any of those ≠ force/history rewrite or cleanup of unrelated state. Destructive operations remain separately gated by `destructiveOpsAuthorized`.

### `budgets`

- `maxWorkers`: emergency mission-owned process ceiling only, 1–6; template default 3. It is not a scheduling target, capacity model, or proof that capacity is available. Do not derive it from RAM size alone.
- `maxWeightedSlots`: approved workload-weighted capacity; template default 3.0. Mission fit is measured in weighted slots, not equal workers.
- `minAvailableRamGb`: absolute emergency available-RAM floor; template default 2. Admission must also satisfy the next workload class reserve; the effective RAM gate is `max(global floor, class reserve)`.
- `resourceSampleSeconds`: active pressure sampling window, 5–60 seconds; template default 10.
- `maxMemoryPsiFullAvg10`: maximum global memory PSI `full avg10`; template default 5.0.
- `maxSwapOutMiBPerSecond`: maximum active swap-out rate across the sampling window; template default 64.0.
- `workloadClasses`: required map of approved resource classes. Template defaults include at least `light`, `standard`, and `heavy`. Each class defines:
  - `slotCost`: weighted capacity consumed while the class is mission-owned (template: 0.5 / 1.0 / 2.0);
  - `minAvailableRamGb`: available-RAM reserve required before admitting that class (template: 1.0 / 2.0 / 4.0).
  Unknown class fields are rejected. Additional named classes are allowed when they use the same field shape.
- `staleAfterMinutes`: age that makes a claim a recovery candidate, never automatic proof of death.
- `maxRetriesPerTask`: total dispatch/recovery retries before the contract's human circuit breaker.
- `maxCorrectionCycles`: total implementer↔reviewer cycles before the contract's human circuit breaker. For delegated long missions, propose 5 by default and disclose it in preview. After a second materially similar FAIL, Conductor must automatically change strategy while still below this cap; see `correction-convergence.md`.
- `maxFullSuites`: broad-suite budget for the milestone.

Budgets are circuit breakers, not completion targets. Record each task's `resource_class` / `weighted_slots` / `ram_reserve_gb` in Beads metadata from the approved class profile.

Before every worker-consuming action (including worktree/workspace opening and dispatch), re-sample global available RAM, memory PSI, and active swap-out rate over `resourceSampleSeconds`. Require present, fresh, finite, real (not boolean), in-domain metrics; missing/malformed/stale evidence fails closed. Admit only when:

1. mission-owned active workers would stay at or below `maxWorkers`;
2. current mission-owned weighted usage plus the next class `slotCost` stays at or below `maxWeightedSlots`;
3. available RAM is above `minAvailableRamGb` and at least the next class reserve;
4. memory PSI `full avg10` is below `maxMemoryPsiFullAvg10`;
5. active swap-out MiB/s is below `maxSwapOutMiBPerSecond`.

Global pressure intentionally includes unrelated workloads, but Conductor never inspects deeply, counts as mission-owned, stops, pauses, or closes unrelated processes. Pressure blocks only new worker-consuming actions; it never auto-kills existing workers and does not block cleanup/recovery. Cumulative swap occupancy is sticky telemetry and never blocks by itself.

The structural validator proves schema/range correctness only. Operational fitness requires `resource-admission-validation.md` (live-host replay, concurrent unrelated load, bounded real-worker soak) before claiming qualification.

### `gates`

- `focusedTests`: commands used per candidate unit.
- `broadTests`: serialized milestone acceptance commands.
- `build` and `lint`: optional command arrays.

Commands must be concrete enough to run without model judgment. A changed command or acceptance threshold exits deterministic integration and requires contract review.

### `ledger`

- `missionId`: Beads epic ID; required once active.
- `actorPrefix`: stable prefix for Beads claim actors, normally `conductor`.

### `dashboard`

- `enabled`: whether sanitized material transitions are published.
- `path`: absolute dashboard implementation path.
- `publishOn`: subset of `mission_start`, `task_claim`, `task_blocked`, `test_verdict`, `review_verdict`, `integration`, `recovery`, `waiting_user`, `mission_pause`, `mission_complete`.

## State transitions

| From | To | Required evidence |
|---|---|---|
| proposed | approved | User-approved decision envelope and validated contract |
| approved | active | Mission epic/graph initialized and live state reconciled |
| active | waiting_user | Exact strategy/safety/budget decision requested; safe lanes exhausted or gated |
| active | paused | User pause or configured milestone stop; resource-closure sweep complete |
| active | complete | All in-scope work integrated/waived and acceptance evidence verified |
| active | aborted | Reason, preserved state, active-process cleanup, and user notification |
| waiting_user/paused | active | Explicit resume plus full reconciliation |

Never infer approval from silence, timeout, an old mission, or a dashboard state.

## Runtime ownership

- The contract owns policy.
- Beads owns live issue state and dependencies.
- Herdr owns live process/pane state.
- Git owns source/integration state.
- The dashboard owns no authority.

When they disagree, stop the affected transition, inspect all authorities, and reconcile explicitly rather than choosing the most convenient value.
