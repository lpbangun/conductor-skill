# Beads and Herdr Recipes

The installed binaries are authoritative. Run `bd <command> --help` and the relevant `herdr` command group if syntax differs. Use `--json` for parsing and `--silent` only when an ID is the intended output.

## Initialize and create a mission

```bash
# Copy templates/mission-metadata.json into .hermes/conductor/ and replace every placeholder first.
# Some Beads versions resolve -C only after discovering an existing project, so first-time
# initialization must run with the shell cwd set to the repository.
(
  cd "$REPO"
  bd init --skip-agents --skip-hooks --setup-exclude --init-if-missing --non-interactive
)

# Once .beads exists, -C is safe for every later command.
bd -C "$REPO" metrics off

MISSION_ID=$(bd -C "$REPO" create "$MISSION_TITLE" \
  --type epic --priority P1 \
  --labels "conductor,mission,mission:$MISSION_SLUG" \
  --metadata @.hermes/conductor/mission-metadata.json \
  --acceptance "$MISSION_ACCEPTANCE" \
  --silent)

bd -C "$REPO" merge-slot create
```

Write the returned opaque ID into `mission.json`; never construct or predict an ID.

## Create units and dependencies

```bash
TASK_ID=$(bd -C "$REPO" create "$TASK_TITLE" \
  --type task --priority P2 --parent "$MISSION_ID" \
  --labels "conductor,mission:$MISSION_SLUG,risk:standard,milestone:$MILESTONE" \
  --description "$DESCRIPTION" \
  --acceptance "$ACCEPTANCE" \
  --silent)

bd -C "$REPO" update "$TASK_ID" \
  --set-metadata risk_rationale="$RISK_RATIONALE" \
  --set-metadata escalation_triggers="$ESCALATION_TRIGGERS"

# BLOCKED depends on BLOCKER.
bd -C "$REPO" dep add "$BLOCKED_ID" "$BLOCKER_ID"
bd -C "$REPO" dep cycles --json
bd -C "$REPO" ready --parent "$MISSION_ID" --json
bd -C "$REPO" blocked --json
```

Priority is urgency. Risk remains in labels/metadata.

Preserve graph width. Create one Bead per plan-declared disjoint lane and add only evidence-bearing dependencies. Do not collapse parallel lanes into one task or add a convenience dependency merely to express preferred order. When the mission permits at least two workers but `bd ready` exposes fewer than two productive units, compare the ledger to the approved/frozen plan and split oversized units or remove false edges without changing scope or acceptance.

## Atomic claim and evidence identity

Use a stable actor so `--claim` assigns the intended worker identity:

```bash
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
LEASE=$(date -u -d "+${STALE_AFTER_MINUTES} minutes" +%Y-%m-%dT%H:%M:%SZ)

bd --actor "$WORKER_ID" -C "$REPO" update "$TASK_ID" --claim \
  --set-metadata worker="$WORKER_ID" \
  --set-metadata worker_role="$WORKER_ROLE" \
  --set-metadata branch="$BRANCH" \
  --set-metadata worktree="$WORKTREE" \
  --set-metadata base_sha="$BASE_SHA" \
  --set-metadata resource_class="$RESOURCE_CLASS" \
  --set-metadata weighted_slots="$WEIGHTED_SLOTS" \
  --set-metadata ram_reserve_gb="$RAM_RESERVE_GB" \
  --set-metadata claim_lease="$LEASE" \
  --set-metadata last_heartbeat="$NOW" \
  --set-metadata retry_count="$RETRY_COUNT"
```

A failed claim means do not launch. Re-query the Bead and scheduler state.

After Herdr starts the worker, record returned IDs; do not predict them:

```bash
bd -C "$REPO" update "$TASK_ID" \
  --set-metadata herdr_workspace="$WORKSPACE_ID" \
  --set-metadata herdr_pane="$PANE_ID"
```

## Heartbeat, blocker, evidence, close

```bash
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
bd -C "$REPO" update "$TASK_ID" --set-metadata last_heartbeat="$NOW"

bd -C "$REPO" update "$TASK_ID" --status blocked \
  --set-metadata blocker_type="$BLOCKER_TYPE" \
  --set-metadata blocker_summary="$BLOCKER_SUMMARY"
bd -C "$REPO" note "$TASK_ID" "$BLOCKER_EVIDENCE"

bd -C "$REPO" update "$TASK_ID" \
  --set-metadata candidate_sha="$CANDIDATE_SHA" \
  --set-metadata tests="$TEST_SUMMARY" \
  --set-metadata review_verdict="$REVIEW_VERDICT" \
  --set-metadata reviewer="$REVIEWER"
bd -C "$REPO" note "$TASK_ID" "$DETAILED_EVIDENCE"

bd -C "$REPO" update "$TASK_ID" \
  --set-metadata merge_sha="$MERGE_SHA" \
  --set-metadata integration_tests="$INTEGRATION_TEST_SUMMARY" \
  --set-metadata push_parity="$PUSH_PARITY"

python3 "${HERMES_HOME:-$HOME/.hermes}/skills/autonomous-ai-agents/conductor/scripts/check_close_evidence.py" \
  --repo "$REPO" --task "$TASK_ID"
bd -C "$REPO" close "$TASK_ID" --reason "Integrated at $MERGE_SHA; acceptance verified."
```

Do not force-close unsatisfied gates.

## Reopen and recovery

```bash
bd -C "$REPO" show "$TASK_ID" --long --json
bd -C "$REPO" history "$TASK_ID" --json
bd -C "$REPO" reopen "$TASK_ID"
bd -C "$REPO" update "$TASK_ID" \
  --set-metadata retry_count="$NEXT_RETRY" \
  --set-metadata escalation="$RECOVERY_REASON"
```

Reclaim only after process/worktree evidence satisfies the stale-claim policy. Preserve the old branch/worktree and continue from inspected state.

## Herdr topology

Use the canonical project workspace as primary. Each mutating branch gets a worktree; the default path is:

```text
~/projects/<project>-worktrees/<branch-slug>/
```

Operators may override the default path when their layout differs. From outside a managed pane, use an explicit named session or `HERDR_CONFIG_PATH`; never target another client’s focused pane. Inspect before mutating:

```bash
herdr session list
herdr api snapshot --session "$SESSION"
herdr workspace list --session "$SESSION"
```

Create the worktree with the policy path explicitly; Herdr's default path is not acceptable without an explicit override:

```bash
WORKTREE="$HOME/projects/${PROJECT}-worktrees/${BRANCH_SLUG}"
HERDR_CONFIG_PATH="$HOME/.config/herdr/sessions/$SESSION" \
  herdr worktree create --cwd "$REPO" --branch "$BRANCH" --base "$BASE_REF" \
  --path "$WORKTREE" --label "$BRANCH_SLUG" --no-focus --json
```

Parse the returned opaque workspace ID. Before submitting work, inspect the workspace/pane and verify its actual cwd equals the claim metadata's absolute `worktree`; a label is not proof of cwd, branch, or SHA.

For role-routed noninteractive Hermes workers when a visible TUI is unnecessary, a default companion launcher is:

```bash
~/.local/bin/spawn-agent "$ROLE" "$TASK" --workdir "$WORKTREE" --background --json
```

Install or configure the companion launcher when this route is used; the path is a default, not a universal machine fact.

Record the returned process/session handle in Beads and verify that exact process is live before marking the task working. If no stable handle is returned, use a visible Herdr pane instead.

For Standard/Critical review, prefer a visible Droid `/review` against the exact integration base. If unavailable, run an `advisor` worker read-only with the evidence contract.

## Resource and cleanup checks

Use live system output before every worker-consuming action, including overnight dispatch. Read and enforce the approved contract values in `budgets`:

- classify the next task with an approved `budgets.workloadClasses` entry (`light` / `standard` / `heavy` or another validated class); record `resource_class`, `weighted_slots` (`slotCost`), and `ram_reserve_gb` in Beads metadata;
- count only mission-owned active workers and enforce `budgets.maxWorkers` as an emergency process ceiling (1–6), not as proof of capacity;
- enforce workload-weighted capacity: current mission-owned weighted usage + next `slotCost` must stay at or below `budgets.maxWeightedSlots`;
- re-sample available RAM, `/proc/pressure/memory` `full avg10`, and `pswpout` across `budgets.resourceSampleSeconds`; convert the page delta with the live system page size to MiB/s;
- fail closed when evidence is missing/malformed/stale/non-finite, available RAM is at or below `budgets.minAvailableRamGb` or below the next class reserve, PSI is at or above `budgets.maxMemoryPsiFullAvg10`, active swap-out is at or above `budgets.maxSwapOutMiBPerSecond`, weighted capacity is exhausted, or the emergency process ceiling would be exceeded;
- cumulative swap occupancy alone never blocks; global pressure includes unrelated workloads, but never inspect deeply, stop, pause, or manage unrelated processes;
- defer only new workspace opening/dispatch under pressure; do not kill existing workers, and continue cleanup/recovery;
- one full suite and one merge/integration lane at a time;
- focused tests are not broad suites and do not consume the broad-suite budget; they may overlap with independent work when files, databases, ports, browser profiles, and generated artifacts do not conflict;
- classify workload from measured execution cost, not task risk: a Critical read-only review with focused tests is normally Standard, while a broad suite or measured high-memory run may be Heavy;
- when two safe, ready, non-overlapping lanes fit the approved envelope, keep two productive workers active rather than filling capacity with duplicate verification;
- metadata-only changes or an unchanged product SHA receive focused metadata/schema validation and reuse exact-SHA product evidence; they do not trigger a broad suite;
- close completed or paused mission-owned panes promptly;
- preserve Git branches/worktrees unless cleanup authority is explicit;
- never inspect or close unrelated/user-owned Herdr workspaces;
- structural schema tests are not operational qualification; follow `resource-admission-validation.md` before claiming fitness.

## Serialized integration slot

Refuse this lane unless `localIntegrationAuthorized` is true and `$INTEGRATION_OWNER` exactly matches the contract's `integrationOwner`.

```bash
bd -C "$REPO" merge-slot check --json
bd -C "$REPO" merge-slot acquire --holder "$INTEGRATION_OWNER" --json
# Verify holder from the returned/current slot state before any Git merge.

# ...perform only the authorized deterministic integration sequence...

bd -C "$REPO" merge-slot release --holder "$INTEGRATION_OWNER" --json
```

Do not use `--wait` while occupying an agent turn; a held slot blocks only integration. Schedule other safe work and retry later. Release in cleanup even after a failed gate, but retain the failed integration evidence. If release fails, stop all later integration and report the held slot.

## Mission pause/closure

On pause, set `mission.status` to `paused`, validate the contract, update the epic metadata, and perform the resource-closure sweep without closing the epic.

On complete, first verify every child is closed or explicitly user-waived, then:

```bash
bd -C "$REPO" update "$MISSION_ID" \
  --set-metadata final_sha="$FINAL_SHA" \
  --set-metadata acceptance_verdict="$MISSION_VERDICT"
bd -C "$REPO" close "$MISSION_ID" --reason "Mission accepted at $FINAL_SHA."
```

Set `mission.status` to `complete`, validate it with `--require-active`, publish the dashboard transition, and verify no mission-owned process remains. Abort uses status `aborted` plus a preserved-state reason; do not mislabel aborted work complete.
