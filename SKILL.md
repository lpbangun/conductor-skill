---
name: conductor
description: "Use when the user authorizes a multi-step software mission that should continue autonomously across workers, worktrees, reviews, integration gates, failures, or session restarts. Orchestrates Beads as the durable ledger and Herdr as the execution surface with risk-proportional routing, evidence-backed transitions, resource admission, stale-claim recovery, and explicit human boundaries. Do not use for a single bounded task or strategy discussion without execution approval."
version: 1.4.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  created_by: agent
  hermes:
    tags: [conductor, orchestration, beads, herdr, worktrees, multi-agent, durable-missions]
    related_skills: [agent-loop-engineering, herdr, subagent-roles, requesting-code-review, test-driven-development]
---

# Conductor

## Overview

Conductor is a thin policy layer for durable software missions. It does not code, run a scheduler daemon, own a process registry, or replace Git, Beads, or Herdr.

- **Beads (`bd`)** owns mission/task state, dependencies, atomic claims, metadata, and recovery history.
- **Herdr** owns human-visible workspaces, panes, agent processes, terminal evidence, and worktree placement.
- **Git** owns branches, commits, integration history, and remote parity.
- **Workers** own bounded planning, implementation, tests, and review.
- **Conductor** owns mission approval, risk routing, resource admission, sequencing, evidence reconciliation, stale-claim recovery, integration authorization, dashboard projection, and final acceptance.

The governing loop is:

`reconcile → select ready work → admit resources → dispatch → inspect evidence → review/fix → integrate → advance`

A blocked lane does not stop the mission while other dependency-ready work exists.

## When to Use

Use when the user explicitly authorizes execution of a mission that has one or more of:

- several dependent implementation units;
- parallel workers or worktrees;
- independent review and correction cycles;
- long unattended or checkpointed execution;
- durable recovery after crashes, context compression, or Herdr restart;
- serialized integration, broad test gates, or controlled push;
- a remote read-only status dashboard.

Do not use for:

- strategy discussion, comparison, or planning before the user says to start;
- one bounded edit that one agent can complete and verify directly;
- non-software task queues;
- replacing a project’s existing authoritative orchestrator without an explicit migration decision.

## Non-negotiable invariants

1. **Approval is scoped.** A user-approved mission contract authorizes only its objective, repositories, milestone, autonomy mode, resource limits, and side effects. New product strategy, destructive operations, force pushes, credential changes, releases, or scope expansion require renewed approval.
2. **Conductor does not implement.** Delegate mutating product work to a bounded worker. The conductor may perform deterministic control-plane operations after verified PASS: update Beads, inspect state, create approved worktrees, run predetermined gates, commit already-reviewed changes when explicitly assigned as integration owner, merge without rebase, update the dashboard, and clean up owned resources.
3. **Evidence beats self-report.** A worker’s “done” is a signal to inspect, never proof. Verify the exact worktree, branch, diff, SHA, commands, exit codes, review verdict, and integrated-base result.
4. **One mutating owner per worktree.** Parallel mutation requires separate branches/worktrees. Shared integration files have one named owner.
5. **No hidden runtime.** Do not create a second database, scheduler daemon, merge queue, or process registry. Shell directly to `bd --json` and Herdr’s live CLI. A transparent mission-owned one-shot completion notifier is allowed only as defined in `references/speed-first-liveness.md`; it owns no state and performs no reconciliation.
6. **Risk is not priority.** Beads priority P0–P4 means urgency. Store execution risk independently as `risk:routine`, `risk:standard`, or `risk:critical` labels plus metadata.
7. **Speed-first, work-conserving, and parallelism-targeted.** Useful throughput is the scheduling objective. Resource policy is an admission constraint and circuit breaker, not the optimization target. Use `scripts/scheduler_decision.py` over the complete ready queue and launch the largest admitted set of productive, dependency-ready, non-overlapping lanes. Feasibility includes process headroom under `maxWorkers` and weighted headroom under `maxWeightedSlots`; when two fit, target at least two productive mission-owned workers. Do not fill the second lane with duplicate verification, speculative work, or shared-seam contention. Do not fill additional capacity with those substitutes either; when fewer than two productive lanes run, record the concrete dependency, ownership, capacity, or pressure reason.
8. **Integration is serialized.** Never run concurrent merges, pushes, or duplicate full suites. Reconcile against a stable integration SHA before and after each merge.
9. **Push is denied by default.** Local commit/merge authority does not imply push, release, deployment, primary-branch merge, history rewrite, or worktree deletion authority.
10. **The governing skill is immutable during a mission.** Record lessons, but propose policy changes only after mission closure and user review.

## `/conductor` command experience

Hermes exposes this enabled skill directly as `/conductor`. Treat text after the command as the user's instruction for this turn, not as implicit authorization to launch.

The direct slash form is for interactive CLI/TUI and gateway chats. Noninteractive `hermes chat -q` does not run the slash dispatcher; preload instead:

```bash
hermes -s conductor chat -q "Implement feature X in ~/projects/myapp. Begin intake only."
```

Do not use `hermes chat -q '/conductor'` as a one-shot invocation; it is plain query text on that surface.

### Bare command: guided intake

For a bare invocation:

```text
/conductor
```

enter **intake mode only**. Do not initialize Beads, write a mission contract, create a worktree, mutate Git, open Herdr execution topology, claim a task, or launch a worker.

1. Perform read-only discovery: inspect the current cwd/repository, project instructions, existing `.hermes/conductor/mission.json`, Beads/Herdr/Git state, likely verification commands, and resource headroom.
2. If an existing mission is found, summarize its authoritative state and offer `resume`, `status`, or a new mission; do not silently replace or resume it.
3. Otherwise present a compact **Conductor mission intake**. Show inferred values and ask only for decisions that cannot be retrieved:
   - measurable outcome and acceptance evidence;
   - in/out-of-scope boundaries or named milestone when ambiguous;
   - supervision mode (`interactive`, `checkpointed`, or `delegated`);
   - local integration authority and exact target;
   - push authority and exact target.
4. Default to `checkpointed`, a workload-aware capacity proposal derived from live host signals and approved `workloadClasses` (template `maxWeightedSlots: 3.0` with `light`/`standard`/`heavy`), emergency `maxWorkers: 3` process ceiling (not proof that capacity is available), no local integration, no push, no release/deploy, and preservation of branches/worktrees. Do not derive a universal worker cap from RAM. Label every default so the user can override it; live resource admission still governs every launch.
5. Ask no more than four concise questions at once. Do not ask for repository facts, test commands, or system state that tools can discover.

End the intake response with: **“Nothing has launched.”**

### Inline command: fast intake

For an invocation with mission text:

```text
/conductor Implement feature X in ~/projects/myapp. Checkpointed; allow local integration into main; do not push. Acceptance: tests A and B pass.
```

use the instruction to prefill the same intake contract. Inspect the named repo and ask only for missing decisions. Even a complete inline instruction is a mission proposal, **not approval**. Never launch on the first turn merely because the instruction says “build,” “implement,” “start,” or “run.”

### Preview and approval barrier

When intake is complete, render `templates/mission-intake.md` as one bounded **Mission Contract Preview** containing:

- repo, integration branch, objective, milestone, in/out scope, and acceptance evidence;
- supervision mode and runtime/persistence disclosure;
- weighted `maxWeightedSlots` capacity, approved `workloadClasses`, emergency `maxWorkers` process ceiling, pressure/reserve thresholds, and retry/correction/broad-suite budgets;
- local integration, push, release, deploy, destructive-operation, and cleanup authority;
- focused/broad gates and dashboard policy;
- inferred values, explicit defaults, and unresolved assumptions.

If no durable controller is active, say explicitly: **“Execution is session-orchestrated; Beads/Herdr preserve recovery state, but after a main-session restart you must run `/conductor resume`.”** Never imply daemonized continuation that does not exist. For delegated mode, automatic worker-to-worker continuation is available only while the Conductor pane exists and every active worker has a verified completion-wake handle; disclose that boundary explicitly.

Then say **“Nothing has launched.”** and ask the user to reply exactly:

```text
Approve mission
```

Only an approval received after the latest preview activates that exact envelope. Earlier strategy approval, an inline imperative, “looks good,” or a bare `/conductor` is insufficient. If any material contract field changes, issue a new preview and require fresh approval.

After `Approve mission`, write and validate the approved contract, bootstrap/reconcile Beads, write the returned mission ID, validate the active-ledger gate, and only then create execution topology or launch workers. If any gate fails, remain inactive and report the exact missing evidence.

### Operational follow-ups

- `/conductor status [repo]`: read-only reconciliation and concise status; never launches work.
- `/conductor resume [repo]`: reconcile an existing contract, Beads, Herdr, and Git. Resume only the unchanged approved envelope; if paused explicitly by the user, this command is the resume instruction. Re-preview any changed envelope.
- `/conductor pause`: immediately stop scheduling, cancel mission-owned watchers, close completed/paused mission panes, preserve Git state, and mark the mission paused.
- `/conductor abort`: stop scheduling and preserve evidence/state; mark aborted with a reason. Do not delete branches, worktrees, or ledger history without separate destructive authorization.

**Completion criterion:** before activation, the user has seen the full current preview, the response states “Nothing has launched,” and a later explicit `Approve mission` matches that unchanged preview.

## Invocation contract

A mission cannot become `active` until `.hermes/conductor/mission.json` passes both the approved-envelope and active-ledger gates in `references/mission-contract.md`. If required facts are retrievable, inspect them; ask the user only for decisions that cannot be inferred.

Recommend one supervision mode:

| Mode | Use when | Human gates |
|---|---|---|
| `interactive` | Strategy is fluid or effects are consequential | Approve each strategy/integration boundary |
| `checkpointed` | Plan is stable but milestone judgment remains human-owned | Pause at named milestone(s) |
| `delegated` | User approves autonomous execution inside a narrow decision envelope | Pause only on envelope exit, safety ambiguity, or mission circuit breaker |

The contract must name:

- absolute repository path and integration branch;
- objective, milestone target, acceptance evidence, in-scope and out-of-scope work;
- supervision mode and explicit push authorization;
- weighted capacity, workload resource classes, reserve/pressure signals, emergency process ceiling, retry, correction-cycle, stale-claim, and broad-suite budgets;
- focused and broad verification commands;
- dashboard policy if enabled.

**Completion criterion:** the contract validates, the user has approved its decision envelope, and live Git/Herdr/Beads state has been reconciled with it.

## Mission lifecycle

### 1. Reconcile before every scheduling cycle

Inspect authoritative sources, not remembered state:

- repository instructions and approved mission contract;
- `git status`, branch, worktrees, integration tip, and remote parity;
- Beads mission epic, children, dependencies, claims, and metadata;
- Herdr workspaces/panes/agent status and available machine resources;
- dashboard status only as a projection, never as authority.

After a restart or context compression, perform this reconciliation before steering, reclaiming, merging, or launching anything.

**Completion criterion:** every in-progress Bead maps to a live worker/worktree or is explicitly classified as a recovery candidate; every live mission-owned worker maps back to one Bead.

### 2. Bootstrap the durable ledger

If the repository has no Beads database and the approved contract allows setup:

```bash
# First-time initialization must run from the repository cwd. Some Beads versions
# try to discover an existing project before honoring `-C`, so `bd -C "$REPO" init`
# fails precisely when `.beads` does not exist yet.
(
  cd "$REPO"
  bd init --skip-agents --skip-hooks --setup-exclude --init-if-missing --non-interactive
)

# After initialization, use `-C` normally.
bd -C "$REPO" metrics off
```

Create one mission epic, the Beads merge slot, and child tasks. Keep the mission’s stable ID in `mission.json`. Use native parent-child relationships for grouping and blocking dependencies for execution order. See `references/beads-herdr-recipes.md` for exact commands.

Preserve plan-declared parallel lanes as separate Beads with disjoint owner/file boundaries. Add a blocking edge only when downstream acceptance actually requires a predecessor artifact or integrated SHA; a preferred order, broad risk label, or easier bookkeeping is a convenience dependency and must not serialize otherwise independent work. Do not collapse a phase containing independent producer, consumer, surface, fixture, or review lanes into one giant task. Before activation and after each material transition, inspect graph width: if fewer than two units can become ready under a mission that permits two workers, re-check the plan and remove false dependencies or split oversized units without changing product scope or acceptance.

Do not initialize Beads during strategy discussion, overwrite an existing database, or enable an external Dolt server for this mission-owned worker design.

**Completion criterion:** `bd show "$MISSION_ID" --json` returns the epic; all approved units are children; `bd dep cycles --json` reports no cycle; `bd ready --parent "$MISSION_ID" --json` agrees with the plan.

### 3. Classify and route each ready unit

Assign one risk class with a one-sentence rationale and escalation triggers:

| Risk | Typical work | Default route | Validation |
|---|---|---|---|
| Routine | Docs, copy, styling, mechanical cleanup, isolated obvious fix | `tiny`/`smol`, or one direct fast worker | Focused checks; grouped semantic review only if needed |
| Standard | Localized behavior with clear contracts | One `task` worker in an isolated worktree | RED/GREEN, independent review against integration base, focused gate |
| Critical | Security/privacy, schema, irreversible/external effects, shared contracts, broad migration | `plan` first; one `task` worker or bounded `/goal` only when iteration is truly needed | Small slices, independent review, distinct invariant checks, milestone broad gate |

Escalate when implementation reveals cross-cutting dependencies, unstable interfaces, security/schema implications, repeated correction, unexpected scope growth, or irreversible effects. Do not downgrade merely to save tokens.

Execution risk does not determine resource class. Classify compute cost from the actual command/model workload: planning and read-only review with focused tests are normally `light` or `standard`; a large mutating agent, broad suite, build, browser run, or measured high-memory workload may be `heavy`. A Critical task can therefore use a Standard worker while retaining every Critical review and acceptance gate.

Use expensive models only for ambiguity and judgment. Prefer Factory Droid’s native `/review` against the exact integration base. If Droid is unavailable, use the `advisor` role read-only. A second reviewer is justified only when it answers a distinct acceptance question.

**Completion criterion:** the Bead contains risk label, rationale, escalation triggers, acceptance criteria, owner/worktree boundaries, and named verification route before claim.

### 4. Admit work against dependencies and resources

Before dispatch:

1. Query `bd ready --parent "$MISSION_ID" --json` (or query all mission children and filter dependency readiness when the installed Beads version lacks `--parent`).
2. Build a reconciled snapshot containing the complete ready queue, active mission-owned workers, ownership keys, workload costs, budgets, and fresh pressure signals. Run `python3 scripts/scheduler_decision.py snapshot.json`. Treat its `maximize_useful_throughput` selection as the scheduling default; inspect every excluded lane and never stop after selecting the first `bd ready` result.
3. Reconcile completed workers before admitting replacements. If fewer than two productive workers would be active, require the planner's concrete `underfillReason`; otherwise dispatch every selected lane up to the admitted maximum.
4. Re-sample global resource pressure before every worker-consuming action, including worktree/workspace opening and overnight dispatch. Read available RAM, `/proc/pressure/memory` `full avg10`, and the `pswpout` delta across `budgets.resourceSampleSeconds`; convert pages with the live system page size to MiB/s.
5. Require every metric and sampling datum to be present, finite, real (not boolean), and in its valid domain. Missing, malformed, or stale evidence fails closed.
6. Classify the next workload by an approved `budgets.workloadClasses` profile (`light` / `standard` / `heavy` or another validated class). Do not assume every worker has equal cost. Do not derive a universal worker cap from RAM.
7. Count only mission-owned active workers and weighted usage. Unrelated workloads affect global pressure and available headroom but must never be counted as owned, inspected deeply, steered, paused, managed, or closed.
8. Enforce the approved `budgets.maxWeightedSlots` capacity and the emergency `budgets.maxWorkers` process ceiling (1–6). `maxWorkers` is a circuit breaker only—not proof that capacity is available.
9. Defer worktree/workspace opening and dispatch when any of the following holds: available RAM is at or below `budgets.minAvailableRamGb` or below the next class reserve; memory PSI `full avg10` is at or above `budgets.maxMemoryPsiFullAvg10`; active swap-out rate is at or above `budgets.maxSwapOutMiBPerSecond`; current weighted usage plus next `slotCost` would exceed `maxWeightedSlots`; or the emergency process ceiling would be exceeded. Cumulative swap occupancy is telemetry only and never blocks by itself.
10. Pressure stops new worker-consuming actions only; never kill existing workers automatically. Cleanup, dead-worker recovery, and unrelated non-launch reconciliation continue.
11. Serialize broad suites and integration operations, not all tests. Focused tests do not consume the broad-suite budget or global broad-suite lane and may overlap independent work when their measured resource class fits. Two focused suites that contend for the same database, ports, browser profile, generated artifacts, or files are not independent.

**Completion criterion:** the selected task is dependency-ready; current pressure, next-class reserve/cost, and weighted capacity are explicitly safe; execution is isolated; and no higher-priority ready unit is skipped without a recorded reason.

### 5. Claim, dispatch, and establish evidence identity

Atomically claim through Beads before starting a worker. Record:

- stable worker/role identity;
- branch and absolute worktree path;
- Herdr workspace/tab/pane or terminal ID;
- claim lease expiration and last heartbeat;
- base SHA and integration branch;
- retry count and milestone.
- approved `resource_class`, `weighted_slots`, and `ram_reserve_gb` copied from the mission contract profile.

Create/open Herdr topology only after the claim succeeds. Keep the primary workspace as the project home and pass an explicit `--path` for feature worktrees; the default worktree path is `~/projects/<name>-worktrees/<branch-slug>/` unless the operator overrides it. Never accept Herdr's default path silently. Use a self-contained brief based on `templates/worker-brief.md`. Require the worker to read project instructions and report artifacts, commands, outputs, risks, and next action.

For delegated supervision, launch `scripts/watch_worker_completion.py` as a separate mission-owned process after verifying the worker PID/start identity and expected result marker. Record the watcher PID and receipt path, then verify it is live. A generic background wait that exits silently is not sufficient. Never return idle while an active worker is unwatched. On a validated wake, reconcile the worker evidence and Bead immediately, then resample and refill through `scripts/scheduler_decision.py`. Follow `references/speed-first-liveness.md`.

**Completion criterion:** Beads claim, Herdr process/tracked subprocess handle, exact cwd, worktree, branch, base SHA, and—when delegated—the verified completion-wake handle all cross-reference one another, and the expected agent and watcher are independently confirmed live.

### 6. Supervise without stealing implementation

At material transitions, inspect live evidence. For a lane that stalls:

`inspect → steer once → retry/split/fallback within budget → mark blocked/escalate`

Do not repeatedly resend prompts, infer failure from one watcher timeout, or reclaim from lease expiry alone. Keep scheduling unrelated ready work.

A heartbeat is a compact metadata update, not prose chatter. Refresh it after observable progress, a test/review transition, or bounded supervision interval. Do not use heartbeats to conceal a worker that is idle at a prompt.

**Completion criterion:** each active task has fresh, truthful state; blocked tasks name the blocker and recovery owner; unrelated ready work continues when safe.

### 7. Verify, review, and correct

Before review, independently inspect:

- worktree and branch identity;
- changed/staged/untracked files;
- diff against the recorded base;
- focused tests and exact exit status;
- acceptance criteria mapping;
- prohibited scope changes.

Verification must be change-proportional: metadata-only changes, ignored local mission artifacts, or an unchanged product SHA must not trigger a broad suite. Validate the changed metadata/schema directly and reuse still-bound exact-SHA product evidence. Run a broad suite only when its declared product tree or broad acceptance surface changed, or when a concrete unresolved failure requires it.

Standard/Critical work receives an independent review against the named integration branch. The implementer fixes actionable findings; material fixes require fresh independent re-review. A reviewer that edits a finding cannot certify its own correction.

Store concise evidence in Beads metadata and append detailed command/output references in notes. Follow `references/evidence-contract.md`.

**Completion criterion:** focused gates pass on the exact candidate SHA, review verdict is PASS with no unresolved actionable finding, and the evidence record identifies who verified what.

### 8. Integrate deterministically

Only the contract's named integration owner may enter this serialized lane. Refuse to merge unless `authority.localIntegrationAuthorized` is true and the current owner matches `authority.integrationOwner`.

1. Atomically acquire the native Beads merge slot as the named integration owner; failure means wait, not merge.
2. Verify candidate SHA and clean integration checkout.
3. Refresh normally without rebasing or rewriting active worker history.
4. Merge deliberately with a normal/no-fast-forward merge when project policy allows.
5. Run predetermined focused integration checks.
6. At a named mission/milestone gate, run the broad suite only when the declared product tree or broad acceptance surface changed, or a concrete unresolved failure requires it, and the budget admits it. Reuse bound broad-suite evidence when the integrated product SHA and declared broad acceptance surface are unchanged.
7. Record merge SHA, integrated-base test evidence, and branch parity.
8. Push only if `pushAuthorized` is true for this exact target.
9. Close the Bead only after integrated evidence exists.
10. Release the merge slot in a `finally`-style cleanup after recording the outcome; if release fails, stop further integration and report the held slot.

Conflicts, base drift, unexpected dirty state, or changed acceptance boundaries exit the deterministic lane and become a correction/review task. Never improvise conflict resolution inside Git ceremony.

**Completion criterion:** the task is present on the integration branch at a recorded SHA, required integrated checks pass, Beads is closed with evidence, and any authorized remote parity is verified.

### 9. Advance, pause, or close the mission

After each material transition, recompute ready/blocked work and update the sanitized dashboard. Mission completion requires:

- every in-scope Bead closed or explicitly waived by the user;
- no mission-owned worker, watcher, test, or merge process still active;
- integration and authorized remote parity verified;
- broad acceptance evidence inspected, not merely green;
- branches/worktrees preserved or cleaned according to explicit policy;
- dashboard and handoff updated;
- metrics captured: duration, worker/model calls, broad suites, correction cycles, unique findings, duplicated work, resource incidents, and human interventions.

For completion, close the mission epic with final SHA/acceptance evidence and set `mission.status` to `complete`; for pause, keep the epic open and set status `paused`. Validate the resulting contract and reconcile it back to Beads before publishing the final transition.

A user pause/stop overrides the roadmap immediately. Cancel owned watchers, close completed/paused mission panes to reclaim RAM, preserve Git state, and do not run “one last” review or gate.

**Completion criterion:** authoritative state, live processes, Git, dashboard, and user-facing verdict agree.

## Stale-claim recovery

Beads has no native lease enforcement. Treat an expired `claim_lease` only as a recovery candidate.

Before reclaiming, require at least two independent signals:

- lease/heartbeat exceeds `staleAfterMinutes`;
- Herdr pane/process is absent, exited, or non-working after inspection;
- no recent Git/file progress in the assigned worktree;
- worker transcript shows terminal completion/failure rather than active work.

Then:

1. Preserve and inspect the worktree/branch; never reset or delete it.
2. Record recovery evidence and increment `retry_count`.
3. If usable work exists, create a narrow continuation brief from the current SHA/diff.
4. Clear/reassign the claim only within retry budget.
5. Escalate repeated stale claims or ambiguous shared state to the user.

## Dashboard projection

The password-protected dashboard is read-only and sanitized. Update it only after material transitions: mission start/pause/complete, task claim, blocker, test/review verdict, integration, strategy gate, or recovery. Do not publish every heartbeat.

When the contract enables a dashboard, read its path from `mission.json`, update its sanitized source, and run from that exact path:

```bash
cd "$DASHBOARD_PATH"
python3 build_status.py
python3 test_dashboard.py
python3 publish.py
```

Never publish repository paths, branch secrets, credentials, raw prompts/transcripts, source code, pane IDs, private issue text, or write controls. The dashboard is not a control plane and cannot authorize transitions.

## Human boundaries

Always ask before:

- activating a mission whose decision envelope is not already approved;
- changing product direction, milestone, architecture contract, or acceptance bar;
- destructive Git/filesystem/database operations;
- force push, release, deployment, external communication, credential/config changes;
- merging/pushing to a target not explicitly authorized;
- exceeding any approved weighted-capacity, workload-reserve, pressure, emergency worker-ceiling, retry, correction, test, time, or token circuit breaker;
- reclaiming an ambiguous worker that may still be active.

Do not ask for routine TDD fixes, predetermined reviews, normal task claims, evidence updates, authorized local integration, dashboard refreshes, or safe scheduling inside a delegated decision envelope.

## Common pitfalls

1. **Strategy chat becomes execution.** Drafting a plan is not permission to initialize Beads, create worktrees, or launch agents.
2. **Priority/risk collapse.** P0 urgency does not mean Critical execution risk; retain both dimensions.
3. **Ledger theater.** Updating Beads without reconciling Herdr/Git creates false state. Cross-check all three.
4. **Self-report acceptance.** “Tests pass” without exact SHA and command output is not evidence.
5. **Lease-only reclaim.** Expiry alone cannot prove death; inspect process and worktree.
6. **Conductor coding.** If product code needs judgment or mutation, dispatch a worker.
7. **Review multiplication.** More reviewers are not automatically safer; each must answer a distinct question.
8. **Free-slot compulsion.** Parallelism that destabilizes shared seams increases cycle time.
9. **False serialization.** Collapsing plan-declared disjoint lanes into one Bead, labeling every Critical worker Heavy, or treating focused tests as broad work defeats approved concurrency.
10. **Full-suite duplication.** One broad-suite owner at one stable SHA; unchanged product evidence is reusable.
11. **Authority creep.** Merge permission does not imply push/release/cleanup permission.
12. **Premature close.** Worker PASS is not integrated PASS; close only after integration evidence.
13. **Metric-validity blindness.** Tests that prove a hardcoded threshold is enforced do not prove the metric predicts real pressure. Replay live host states and representative workloads; never use sticky cumulative swap occupancy as a unilateral blocker. Follow `references/resource-admission-validation.md`.
14. **Free equal-worker assumption.** Do not treat `maxWorkers` or RAM size alone as capacity; use weighted classes and reserves.
15. **Silent stop override.** A user pause is immediate, not “after the current step.”

## Context-preserving long stages

When the user asks to preserve the parent conversation context, or when implementation/review/evaluation will produce substantial output, run that stage in a dedicated unfocused Herdr tab with a self-contained brief and a completion-bound watcher. Keep iterative logs in the tab; return only launch identity, material blockers, and the verified completion summary to the parent chat.

A created tab or pane is not proof of startup, and a process exit is not proof of success. Verify the actual agent process, require durable result artifacts, independently rerun the relevant gates in the parent session, and close the completed mission-owned tab promptly after verification. Never reuse or close unrelated panes.

Follow `references/detached-herdr-stage.md` for the reusable launch, watcher, artifact, verification, and cleanup pattern.

## Controller admission evaluation

Before the first live mission under a new or materially changed deterministic controller, require a fixed pre-controller evaluation contract. Never treat evaluator self-tests, an implementer-authored `QUALIFIED` JSON, a process exit code, or a hash-bound self-attestation as proof that the controller passes. Load `references/controller-admission-evidence.md` for provenance, real-canary, independent-review, exact-publication, adversarial-validator, and parent-reproduction requirements.

The admission suite must measure at least:

- exact Routine/Standard/Critical routing, including conflicting signals, escalation, 100% Critical recall, and zero unsafe under-routing;
- generated worker-prompt completeness, conciseness, zero-context executability, exact authority boundaries, and independent hash-bound semantic review;
- event-driven reconciliation and wake behavior with no blind `wait`/`sleep`, explicit tick evidence, stale-process failure injection, and unrelated-lane progress;
- Herdr ownership, cross-system identity, explicit worktree paths, prompt pane/workspace opening, prompt cleanup of mission-owned terminal states, and zero close/reuse of unknown or foreign panes;
- learning-record destination and quality: evidence, recurrence, confidence, deduplication, secret/transcript exclusion, ephemeral-data discard, and no active-mission policy rewrite;
- deterministic integration ordering and fail-closed authority, owner, merge-slot, drift, dirty-state, conflict, test, push-target, parity, and slot-release paths; every safety-bearing input must require an exact boolean (`is True`/`is False`), never generic truthiness, and malformed/missing authorization must block before merge or closure;
- resource admission at approved workload/reserve/pressure boundaries, including high sticky swap with healthy PSI, low-RAM-only, sustained-PSI-only, active-swap-I/O-only, concurrent unrelated load, missing/malformed/NaN/infinite/out-of-range metrics, workload-class capacity differences (`light` vs `heavy`), weighted-slot exhaustion below the emergency process ceiling, and proof that unsafe resources block both workspace opening and dispatch while cleanup/recovery continues; cumulative swap occupancy alone must not block;

Use two distinct layers:

1. **Offline deterministic suite:** failure-injection fixtures and scorers run against the real controller adapter. Missing adapter/controller must return a distinct `NOT_READY` failure, never skip or pass.
2. **External admission evidence:** independent review must bind to hashes of generated prompts; an isolated named-session Herdr canary must use a disposable repository and command-output evidence; dashboard publication must bind to the current offline report artifact **and semantically project the actual controller/admission state**. A matching digest beside stale copy such as “controller absent,” an unfinished controller stage, or the wrong weighted progress is a failed dashboard gate.

For admission runners that publish qualification status, use a two-phase transition: publish and validate an accurate `PENDING_FINAL_ADMISSION` projection, compute all gates, then—only if they qualify—publish `QUALIFIED`, probe the exact live URL again, validate the final semantic projection, and recompute/write the final admission artifact from that second publication. Pass the actual prompt-review, canary, offline, and dashboard validation objects into the recomputation; never replace them with hard-coded `{"passed": true}` stand-ins merely because an earlier phase passed.

Treat the second publication as a transaction. Every failure after setting or publishing `QUALIFIED`—build, test, publish, live probe, semantic validation, or recomputation—must attempt to restore `PENDING_FINAL_ADMISSION`, rebuild/test/republish it, require the exact live probe, and validate rollback evidence. The failure artifact must record whether rollback was attempted and succeeded; rollback failure is an explicit unsafe external-state blocker, not a normal FAIL with implied cleanup.

Run all unit, failure-injection, compilation, offline, and independent-review work before final admission. Final admission is the last operation allowed to mutate the offline report, dashboard source/public artifact, canary report, prompt-review envelope, or publication evidence. The runner must persist the exact in-memory offline report used for that run before publication, then bind both its canonical object digest and replayable file-byte SHA. After it succeeds, use only read-only digest and validator checks against that persisted file; rerunning a timing-bearing offline suite or dashboard builder can invalidate otherwise-correct bindings. Bind the final report to the canonical offline digest, offline artifact byte digest, raw independent-review artifact, fresh canary artifact, final dashboard status, dashboard-evidence object, and publish receipt.

A material change to the evaluator, semantic validator, canary, publication runner, rollback path, or admission wiring requires a fresh independent hash-bound review of those exact code and test files—not merely reuse of unchanged prompt scores. Archive prior raw PASS/FAIL reviews unchanged and regenerate the reviewed bundle.

The runner must derive every declared pre-mission gate and fail closed on unknown required gates. Only an explicit final `QUALIFIED` result may permit the first bounded live mission. `NOT_READY`, offline `FAIL`, or `PENDING_EXTERNAL` prohibits launch. Preserve the evaluation fixtures as a fixed acceptance contract during controller implementation; changes to thresholds or expected outputs require separate review rather than controller-driven relaxation.

**Completion criterion:** the real controller adapter passes the offline suite, independent prompt review, isolated Herdr canary, failure-injection gates, and bound dashboard evidence; the final artifact says `QUALIFIED` and can be reproduced without touching a real project.

## Policy-change verification

After changing the mission contract, lifecycle rules, authority model, evidence gate, or helper scripts, load `references/fail-closed-policy-validation.md` and run the contract tests, disposable Beads smoke test, and Python compilation commands it defines. Require negative-path coverage for every fail-closed rule and a nearby-valid case for every placeholder detector. For consequential changes, obtain a fresh read-only independent re-review before treating the policy as ready.

When synchronizing a public/source package with the installed skill, load `references/skill-package-sync.md`. Compare before copying, reconcile rather than downgrade, include every file consumed by packaged tests, rerun tests from the installed path, and require byte-identical source/install package files before declaring reload readiness.

## Verification checklist

- [ ] Approved, validated mission contract exists.
- [ ] Repo instructions, Git/worktrees, Beads, Herdr, and resources reconciled.
- [ ] Mission epic and dependency graph are durable and cycle-free.
- [ ] Every task separates urgency from risk and defines acceptance/evidence.
- [ ] Every active claim maps to one worker, pane, branch, worktree, and base SHA.
- [ ] Weighted capacity, workload class reserves, available-RAM floor, PSI/swap-I/O pressure gates, emergency process ceiling, retry budget, and single full-suite/integration lanes are enforced; cumulative swap occupancy is not a unilateral blocker.
- [ ] Standard/Critical work has independent review evidence at the exact candidate SHA.
- [ ] Integrated-base checks and merge SHA are recorded before task closure.
- [ ] Push/release/deploy occurred only under explicit authority.
- [ ] Dashboard contains only sanitized projection data.
- [ ] Pause/closure sweep leaves no mission-owned processes forgotten.
- [ ] Final verdict names incomplete/waived work and real evidence; no fabricated success.
