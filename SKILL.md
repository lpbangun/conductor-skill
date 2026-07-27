---
name: conductor
description: "Use when the user authorizes a multi-step software mission that should continue autonomously across workers, worktrees, reviews, integration gates, failures, or session restarts. Orchestrates Beads as the durable ledger and Herdr as the execution surface with risk-proportional routing, evidence-backed transitions, resource admission, stale-claim recovery, and explicit human boundaries. Do not use for a single bounded task or strategy discussion without execution approval."
version: 1.7.6
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  created_by: agent
  hermes:
    tags: [conductor, orchestration, beads, herdr, worktrees, multi-agent, durable-missions]
    related_skills: [agent-loop-engineering, herdr, subagent-roles, requesting-code-review, test-driven-development, kanban-orchestrator, external-agent-review-loops]
---

# Conductor

## Overview

Conductor is a thin policy layer for durable software missions. It does not code, own a scheduler daemon or process registry, or replace Git, Beads, or Herdr. For delegated missions it bundles a transparent timer-based idle wake guard; that guard has no scheduling or ledger authority.

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
2. **Conductor does not implement, commit, or merge.** Delegate mutating product work to a bounded worker. The conductor may perform deterministic control-plane operations after verified PASS: update Beads, inspect state, create approved worktrees, run predetermined gates, update the dashboard, and clean up owned resources. Commits and merges belong to the serialized integration lane and are executed only by Droid (invariant 8). This invariant restricts the conductor process, not the mission's authorized lanes: Droid commit and merge under an approved contract require no additional human approval, and demanding it is an invented gate, not caution.
3. **Evidence beats self-report.** A worker’s “done” is a signal to inspect, never proof. Verify the exact worktree, branch, diff, SHA, commands, exit codes, review verdict, and integrated-base result.
4. **One mutating owner per worktree.** Parallel mutation requires separate branches/worktrees. Shared integration files have one named owner.
5. **No hidden authority.** Do not create a second database, scheduler, merge queue, or process registry. Shell directly to `bd --json` and Herdr’s live CLI. Delegated missions use two transparent mission-owned liveness processes defined in `references/speed-first-liveness.md`: one completion watcher per worker and one controller idle watchdog per dedicated pane. They may observe state and wake the sole controller, but they must not claim tasks, mutate Beads/Git, choose work, run tests, or run `scheduler_decision.py`.
6. **Risk is not priority.** Beads priority P0–P4 means urgency. Store execution risk independently as `risk:routine`, `risk:standard`, or `risk:critical` labels plus metadata.
7. **Speed-first, work-conserving, and parallelism-targeted.** Useful throughput is the scheduling objective. Resource policy is an admission constraint and circuit breaker, not the optimization target. Use `scripts/scheduler_decision.py` over the complete ready queue and launch the largest admitted set of productive, dependency-ready, non-overlapping lanes. Feasibility includes process headroom under `maxWorkers` and weighted headroom under `maxWeightedSlots`; when two fit, target at least two productive mission-owned workers. Do not fill the second lane with duplicate verification, speculative work, or shared-seam contention. Do not fill additional capacity with those substitutes either; when fewer than two productive lanes run, record the concrete dependency, ownership, capacity, or pressure reason.
8. **Integration is serialized and Droid-owned.** Never run concurrent merges, pushes, or duplicate full suites. Reconcile against a stable integration SHA before and after each merge. Merges into the integration branch are performed by Droid (Factory Droid, GLM-5.2 High — never default Opus) and Droid alone, after its review findings are fixed. The conductor authorizes and sequences the lane; it never commits or merges itself.
9. **Push is denied by default.** Local integration authority does not imply push, release, deployment, primary-branch merge, history rewrite, or worktree deletion authority.
10. **The governing skill is immutable during a mission.** Record lessons, but propose policy changes only after mission closure and user review.
11. **Dispatch is visible.** Every OMP, Droid, or CLI-harness dispatch runs in a human-visible Herdr pane inside a dedicated worktree, and the dispatch record carries `pane_id`, workspace, worktree, branch, brief path, and the conductor's lane judgment. Headless dispatch (`delegate_task` sub-agent, `hermes chat -q`, plain scripts) is allowed only for routine work. If a visible pane cannot be opened for a standard or critical lane, that lane does not dispatch; record the blocker instead.

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
   - per-unit routing: the work units with inferred risk lane and harness chain (shown in the preview for approval, not asked as questions when discovery can infer them);
   - local integration authority and exact target;
   - push authority and exact target.
4. Default to `checkpointed`, a workload-aware capacity proposal derived from live host signals and approved `workloadClasses` (template `maxWeightedSlots: 4.0` with `light`/`standard`/`heavy` — four concurrent standard workers; memory reserves are the real gate), emergency `maxWorkers: 5` process ceiling (not proof that capacity is available), `maxCorrectionCycles: 5` for delegated long missions, no local integration, no push, no release/deploy, and preservation of branches/worktrees. After two materially similar correction failures, escalate execution strategy automatically rather than asking the user while below the approved total cap. Do not derive a universal worker cap from RAM. Label every default so the user can override it; live resource admission still governs every launch.
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
- a per-unit **routing & execution plan**: every work unit with its risk lane, harness chain, review requirement (with explicit skip reasons), worktree + visible pane, merge path, the concurrency budget, and the anti-stall contract (verified launch, watcher per claim, watchdog bound to the live session) — nothing may dispatch differently from what the user approved here;
- weighted `maxWeightedSlots` capacity, approved `workloadClasses`, emergency `maxWorkers` process ceiling, pressure/reserve thresholds, and retry/correction/broad-suite budgets;
- local integration, push, release, deploy, destructive-operation, and cleanup authority;
- focused/broad gates and dashboard policy;
- inferred values, explicit defaults, and unresolved assumptions.

If no durable controller is active, say explicitly: **“Execution is session-orchestrated; Beads/Herdr preserve recovery state, but after a main-session restart you must run `/conductor resume`.”** For delegated mode, automatic continuation is available only while the dedicated Conductor pane and its verified idle watchdog remain live and every active worker has a verified completion-wake handle bound to the current pane and canonical result path; disclose that boundary explicitly.

Then say **“Nothing has launched.”** and ask the user to reply exactly:

```text
Approve mission
```

Only an approval received after the latest preview activates that exact envelope. Earlier strategy approval, an inline imperative, “looks good,” or a bare `/conductor` is insufficient. If any material contract field changes, issue a new preview and require fresh approval. The routing plan is part of the approved envelope: changing a unit's risk lane or review policy is a material change requiring a new preview and fresh approval; a harness override **within** an approved lane is conductor judgment, recorded as `routingJudgment` in the dispatch record, and does not require re-approval.

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

Flag every claim whose recorded pane is absent, exited, or not working as a recovery candidate in the same tick — a claim with no live pane is never silently left in-progress. Likewise, dependency-ready work auto-advances: recompute the ready frontier after each transition and dispatch/refill up to the admitted `maxWeightedSlots`/`maxWorkers` envelope without waiting for a human nudge.

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

Record both **risk** and **resource class** before claim. Execution risk does not determine resource class. Risk controls review/acceptance; resource class controls admission.

The mission's routing plan — the table the user approved in the preview — is persisted as `routingPlan` in the mission-epic Beads metadata at bootstrap. Every dispatch must match it: same lane, same review policy. A change to a unit's risk lane or review policy is a material contract change (new preview + fresh approval); a harness override within an approved lane is recorded as `routingJudgment` in the dispatch record.

| Risk | Lane | Harness chain | Required evidence |
|---|---|---|---|
| Routine | fast, headless | Hermes sub-agent via `delegate_task` (a separate instance, never the conductor's own session) or a plain script; trivial automation needs no agent at all | focused checks |
| Standard | visible implementation | OMP in a visible Herdr pane + dedicated worktree, implements with `/goal` (never `/go`) → Droid reviews only if the conductor's judgment requires it → Droid fixes → Droid commits + merges | focused checks; independent review only when conductor judgment requires (recorded) |
| Critical | visible plan handoff | OMP plans in a visible pane (tab 1, plan-only) → frozen plan handed to a second OMP instance (tab 2, same worktree) that implements with `/goal` → Droid reviews → Droid fixes → Droid commits + merges | invariant checks + fresh review + declared milestone gate |

The conductor decides the lane. That judgment — routine/standard/critical plus its rationale — is itself a dispatch field recorded in the dispatch record and Beads metadata (`routingJudgment`). `scripts/conductor_controller.py route_task()` emits a harness default per risk (`routine→hermes-subagent`, `standard→omp`, `critical→omp` plan+implement, review/merge always `droid`); the conductor may override the default but must record the override rationale. A provider/model is a dispatch field, never an inference from a fallback list. Record requested and accepted route in Beads. If the selected route is unavailable, stop that lane and record the fallback decision; do not silently substitute a harness. Droid is the review/fix/commit/merge lane only — it never implements. Independent review is read-only: Factory Droid read-only review against the exact candidate/base SHA. Review is proportional: it applies to implementation work, never to a plan-only lane (the planning harness's embedded critic is the plan review, and the frozen plan goes straight to implementation); for Standard work it is conductor-judged, not automatic. Headless dispatch is routine-only (invariant 11). Escalate risk for cross-cutting interfaces, security/schema/external effects, repeated correction, or irreversible actions. A Critical lane may still be `light` or `standard` resource class.

The full harness flow — OMP plan-only pane → `/goal` implementation pane → Droid review/fix/commit/merge — is codified in `~/.hermes/orchestration/PLAYBOOK.md`. Read it before dispatching any standard or critical lane; this skill and that playbook must not disagree, and where they do, the stricter authority boundary wins.

**Completion criterion:** risk, resource class, route, rationale, acceptance, ownership, and verification are durable before claim.

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

Claim through Beads before opening a dedicated Herdr workspace. Record `worktree`, `branch`, `base_sha`, `role`, `route`, `resource_class`, and `ownership`. Then use `scripts/dispatch_worker.py` with a file-backed brief and current controller pane/session (contract in `references/worker-launch.md`). It launches `watch_worker_completion.py`; every active worker has a verified completion-wake handle. For visible interactive Droid review in a detached worktree, materialize the exact brief in that worktree before launch and use the canonical PID/start-ticks/token/worker-created-result-artifact watcher flow; a plain `herdr wait agent-status ... done` is telemetry, not a qualified watcher. See `references/visible-droid-review-handoff.md`. Persist its `beadsMetadata` only after the returned launcher and watcher identities are live and exact. Never return idle while an active worker is unwatched. `delegate_task` is the routine lane only: a separate headless Hermes sub-agent is acceptable for routine work, but never for standard/critical mission worker or reviewer roles, and never a substitute for the conductor's own session. Never use `spawn_agent --background`; standard and critical lanes dispatch through visible Herdr panes (invariant 11), and a routine lane that needs a watcher uses `dispatch_worker.py`.

Relaunch is resume: a relaunched worker is never started from empty context. Re-inject its bead (ID, metadata, lease state), the original file-backed brief, the current SHA/diff of its worktree, and the prior dispatch record, so the fresh process resumes the same bounded task instead of rediscovering it.

A dispatch is live only once verified: within 30 seconds of pane launch, Herdr must show a live agent in the pane (agent-status working, or a launcher PID proven in `/proc`). Otherwise the dispatch is **failed** — record the failure in Beads metadata and retry; never report "dispatched" on pane creation alone, and never leave the bead claimed against a pane with no agent.

TUI workers (OMP, Droid) never exit at task end, so "watched" is not "working" by itself: every TUI brief must require the same completion artifact as hermes lanes — a result JSON at the named path containing `completionMarker` with the injected token — and the watcher must be launched with `--worker-pane <lane pane>` so a worker idle at its prompt without an artifact triggers a manual-reconcile wake after ten minutes instead of riding out the timeout. If that wake fires, the worker writes its own artifact (never the conductor) or the lane is recovered from inspected evidence.

**Prompt and watcher discipline:** `herdr pane run` can leave a prompt staged but unsubmitted. Inspect the pane after injection; if text remains in the composer, focus it, send one `ENTER`, and verify `agent_status: working` within 30 seconds before claiming the lane. Never reuse a completed OMP/Droid session for another lane: create a fresh pane/session and file-backed brief, because stale context can redirect work. A plain `herdr wait`, heartbeat, or explanatory Beads field is not a qualified completion watcher. Every Standard/Critical claim must be launched through `dispatch_worker.py` or the role-specific canonical watcher flow, with exact launcher/watcher PID+start ticks, token-bound result path, receipt, pane, and current controller session persisted before it is treated as in-progress. If that topology cannot be established, fail the dispatch closed, clear the claim, preserve the worktree, and relaunch canonically—never repeatedly acknowledge wake-guard warnings.

If the controller pane's live session drifts from the idle watchdog's binding (for example after `hermes --resume`), the watchdog still wakes with a `controller_session_drift` warning carrying a rebinding instruction — retire the old watchdog and start a fresh one bound to the observed session. A stale binding must never become a silent permanent non-wake.

Delegated supervision has one verified live pane/session-bound `scripts/controller_idle_watchdog.py`. It is wake-only: it cannot claim, schedule, test, mutate Git/Beads/worktrees, or select routes; it must not run `scheduler_decision.py`. A controller replacement retires old watchers and creates a fresh pane/session binding; a session mismatch is a durable recovery state, not an implicit retarget.

**Completion criterion:** claimed Bead, worktree, route, launcher, watcher, result path, receipt, pane, and session agree in the dispatch record and Beads metadata.

### 6. Supervise without stealing implementation

At material transitions, inspect live evidence. For a lane that stalls:

`inspect → steer once → retry/split/fallback within budget → mark blocked/escalate`

A correction failure triggers diagnosis, not automatic human interruption. After a second materially similar review FAIL, automatically change an in-envelope strategy dimension—model/provider route, implementer, reviewer, decomposition, focused reproduction, invariant test, or ownership slice—before another attempt. Continue strategy-escalated corrections while below the approved `maxCorrectionCycles` and while progress/resource evidence remains sound. Only exhaustion of the approved total cap, absence of any materially different in-envelope strategy, or another explicit authority/cost/safety boundary requires the user.

Do not repeatedly resend prompts, infer failure from one watcher timeout, or reclaim from lease expiry alone. Keep scheduling unrelated ready work. Follow `references/correction-convergence.md` for finding fingerprints, no-progress detection, evidence, and human-boundary rules.

**Blocked is an evidence state, not a mood.** A bead may be marked blocked only with an exact boundary durably recorded in its metadata — a named dependency, ownership conflict, resource ceiling, or a human authority decision with where and when it was asked. Invented gates are forbidden: if the approved contract already authorizes an action (Droid-owned commit/merge under `localIntegrationAuthorized` is the canonical case), requiring further human approval is an error. Reconcile treats every blocked bead lacking a durable boundary as a recovery candidate: verify, unblock, and redispatch. The idle watchdog audits blocked beads and wakes for this check.

A heartbeat is a compact metadata update, not prose chatter. Refresh it after observable progress, a test/review transition, or bounded supervision interval. Do not use heartbeats to conceal a worker that is idle at a prompt. If a visible worker is stopped at its own scoped approval UI for an already-authorized, reversible command, the controller must actively submit the approval and verify `agent_status: working` (or record the failed launch); leaving text or a pending approval at the prompt is not productive work and is not a human boundary.

**Completion criterion:** each active lane is progressing, safely waiting on an explicit gate, or has one recorded recovery action; unrelated ready work continues.

### 6a. Pre-final continuation guard

Before emitting any final response during an active delegated mission, reconcile the current pane, mission status, Beads ready frontier, active workers, qualified completion watchers, and idle-watchdog process. A checkpoint-only final is forbidden when authorized work can continue.

The controller may return idle only when at least one condition is proven:

- the mission or approved milestone is complete;
- an explicit human authority/safety/cost boundary requires a decision, no unrelated safe work remains, the exact boundary is durable, and `mission.status` has transitioned away from `active`;
- every unfinished lane is dependency/ownership/resource blocked and the exact blocker is durable;
- productive workers are live and every one has a qualified watcher bound to the current pane and actual result path.

If the ready frontier is non-empty and no qualified productive worker already covers it, continue in the same turn: sample resources, run `scripts/scheduler_decision.py`, claim atomically, and dispatch/refill. Never end with only “task X is ready next.” A final response that names a next action without executing it — while no durable human boundary blocks — is a checkpoint-only final and is forbidden; execute the action in the same turn. The idle watchdog is recovery for model-turn failure, not permission to stop at routine checkpoints.

**Completion criterion:** every active-mission final response names the proven idle condition; otherwise the controller remains working and advances the loop.

### 7. Verify, review, and correct

Before review, independently inspect:

- worktree and branch identity;
- changed/staged/untracked files;
- diff against the recorded base;
- focused tests and exact exit status;
- acceptance criteria mapping;
- prohibited scope changes.

Verification must be change-proportional: metadata-only changes, ignored local mission artifacts, or an unchanged product SHA must not trigger a broad suite. Validate the changed metadata/schema directly and reuse still-bound exact-SHA product evidence. Run a broad suite only when its declared product tree or broad acceptance surface changed, or when a concrete unresolved failure requires it. Treat broad-suite capacity as reserved gate authority, not one undifferentiated counter: track accidental/forbidden worker runs separately from authorized gate slots and never let a worker violation silently consume the required final integrated gate. Follow `references/verification-scope-and-budget-discipline.md`.

Critical work always receives an independent review against the named integration branch. Standard work receives focused checks; an independent review is required only when the conductor's judgment demands it — shared seams, external effects, security-adjacent surfaces, or repeated correction — and the choice is recorded in the dispatch record. A plan-only lane is never independently reviewed: the planning harness's embedded critic is the plan review, and the frozen plan goes straight to implementation. The implementer fixes actionable findings; material fixes require fresh independent re-review. A reviewer that edits a finding cannot certify its own correction. Track correction count separately from dispatch/recovery retries. A reviewed PASS implementation lane is complete according to its plan state; do not mark it blocked merely because a downstream serial composition or integration dependency is not ready—the dependency graph must represent that wait.

Store concise evidence in Beads metadata and append detailed command/output references in notes. Follow `references/evidence-contract.md` and `references/correction-convergence.md`.

**Completion criterion:** focused gates pass on the exact candidate SHA, review verdict is PASS with no unresolved actionable finding, and the evidence record identifies who verified what.

### 8. Integrate deterministically

Only Droid enters this serialized lane, and only after its review fix pass is complete — Droid reviews, Droid fixes its findings, then Droid commits and merges (see `~/.hermes/orchestration/PLAYBOOK.md`, steps 5–7). The contract must name `droid` as `authority.integrationOwner`; any other owner value fails closed. Refuse to merge unless `authority.localIntegrationAuthorized` is true and the current owner is Droid. The conductor authorizes the lane, hands Droid the exact candidate/base, and inspects the integrated evidence — it never commits or merges itself.

Reviewed-PASS candidates form a serialized Droid merge queue: one merge at a time, and after each merge plus its post-merge check completes, the next candidate auto-advances to Droid without a human nudge, inside the approved envelope.

1. Atomically acquire the native Beads merge slot for the Droid integration lane; failure means wait, not merge.
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

## Checkups

Three tiers. Every tier is read-only inspection of Beads↔Git↔Herdr consistency; a checkup never merges, pushes, or rewrites state — findings become new beads.

| Tier | When | What | Owner skill |
|---|---|---|---|
| 1 · transition sweep | after every material transition (claim, verdict, merge, recovery, restart) | fast consistency sweep: every in-progress bead maps to a live pane + worktree, every live worker maps back to one bead, dispatch records complete, no claim without a live pane | `kanban-orchestrator` |
| 2 · integrated-base health | every 2–3 merges | deeper sweep of the integrated branch: focused suite on the integrated base, orphan branch/worktree scan, watcher-destination audit, dashboard reconciliation | `external-agent-review-loops` (integrated-base review cadence) |
| 3 · post-big-merge | after a merge integrating 3+ beads, or a large cross-lane composition | full health: broad suite on the post-merge SHA, remote parity (only if `pushAuthorized`), dependency-graph width check, stale-claim sweep, metrics checkpoint | this skill (policy below) |

Tier-3 policy: trigger when one merge integrates 3+ beads or touches a shared contract. Run the broad suite once on the post-merge SHA, verify remote parity only under explicit push authority, sweep for claims with no live pane, and publish exactly one dashboard transition. A tier-3 checkup gates the next dispatch wave, not a human; actionable findings become beads and ambiguous ones escalate to the user.

The conductor's judgment decides which tier a transition earns; record the tier in the dashboard transition.

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

The password-protected dashboard is read-only and sanitized. Update it only after material transitions: mission start/pause/complete, task claim, blocker, test/review verdict, integration, strategy gate, recovery, **and every routing/dispatch event** (lane, harness, pane_id, checkup tier). Dispatch events belong on the dashboard, not only in pane scrollback — they are how a human watches which agent is doing what. Do not publish every heartbeat.

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
- exceeding any approved weighted-capacity, workload-reserve, pressure, emergency worker-ceiling, total retry, total correction, test, time, or token circuit breaker; an in-envelope strategy change below those total caps does not require approval;
- reclaiming an ambiguous worker that may still be active.

Do not ask for routine TDD fixes, predetermined reviews, normal task claims, evidence updates, authorized local integration, dashboard refreshes, or safe scheduling inside a delegated decision envelope. In particular, when the approved envelope grants `localIntegrationAuthorized: true` and `integrationOwner: droid`, a reviewed-PASS candidate’s normal Droid commit/merge is authorized integration work—not a separate human commit-authority gate. The conductor does not commit; it dispatches the Droid integration lane.

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
16. **Premature human escalation.** Treating a second review FAIL as a new authority decision defeats delegated missions. Change strategy automatically below the approved total correction cap; ask only at the cap or a real envelope boundary.
17. **False blocked PASS lane.** A reviewed PASS candidate waiting on downstream composition is not itself blocked. Close/complete it according to the plan and let dependencies hold the composition lane.
18. **Passive or unsubmitted observer nudge.** External evaluation is not status narration. When the sole controller is clearly idle with admitted ready work, send one evidence-based nudge, press Enter, and verify the pane accepted it; text left at the prompt is no action.
19. **One-shot observer mistaken for recurring.** Duration syntax such as `12m` schedules one delayed run. Use `every 12m`, list the job immediately, and verify enabled/scheduled state plus a future next run after the first tick.
20. **Violation consumes mandatory gate.** Record forbidden worker broad suites as actual incidents, but do not silently spend reserved final-gate authority or accept them at the wrong SHA. Keep actual-run accounting separate from authorized gate-slot use.
21. **Broad-test violation containment.** A worker brief prohibition is not enforcement. At every completion artifact and material worker inspection, inspect the process tree for `npm test`, `npm run test`, smoke, and equivalent broad commands. If a forbidden broad command is live, terminate only its process group—not the launcher or worker—then preserve and reconcile the artifact. Count it only if completion evidence proves it finished; an interrupted run is partial/unverified and uncounted. If the artifact later proves an already-completed broad suite, correct the ledger to count it before dispatching another gate.
22. **Stale watcher destination.** A watcher with an old controller pane is invalid even if its PID is live. Kill it, keep the stable launcher/artifact intact, and recreate one watcher bound to the current controller pane before relying on completion delivery.
23. **Checkpoint-only final.** Reporting the next ready task and returning idle is a liveness failure. Apply the pre-final continuation guard and dispatch/refill in the same turn.
24. **Watchdog as scheduler.** The timer guard only wakes an idle controller. Giving it claims, scheduling, reconciliation, Git, test, or Beads mutation authority creates a second controller and is forbidden.

## Context-preserving long stages

When the user asks to preserve the parent conversation context, or when implementation/review/evaluation will produce substantial output, run that stage in a dedicated unfocused Herdr tab with a self-contained brief and a completion-bound watcher. Keep iterative logs in the tab; return only launch identity, material blockers, and the verified completion summary to the parent chat.

A created tab or pane is not proof of startup, and a process exit is not proof of success. Verify the actual agent process, require durable result artifacts, independently rerun the relevant gates in the parent session, and close the completed mission-owned tab promptly after verification. Never reuse or close unrelated panes.

Follow `references/detached-herdr-stage.md` for the reusable launch, watcher, artifact, verification, and cleanup pattern.

## External supervision when dogfooding Conductor

When the mission is also evaluating Conductor itself, do not let one session both operate the mission and judge whether the skill caused correct behavior. Use a dedicated persistent interactive Conductor pane as the **sole** control-plane mutator, keep workers beneath it, and make the parent/meta session a read-only evaluator. Freeze the controller session to the skill snapshot it loaded for the evaluation interval; collect findings separately and normally patch only after mission closure and user review. If the user explicitly orders a library update at a bounded checkpoint, record that the active controller remains bound to its prior loaded snapshot and require a fresh controller session before attributing behavior to the new version. A one-shot controller is insufficient because it cannot remain available for completion-wake events.

Handoff must bind approved authority, Beads/Git/Herdr paths, active launcher PID/start identity, leases, watchers and their destination panes, artifacts, review findings, budgets, and unused launch tokens. The receiving Conductor must independently reconcile every claim before acting. Explicitly retire the old controller, discard unclaimed tokens, and ensure inherited watchers either target the new pane or have a temporary relay; dual controllers invalidate mission ownership and evaluation evidence. Follow `references/controller-release-and-handoff.md` for operator pause/repair isolation and controller release.

Follow `references/external-supervision.md` for the reusable topology, safe handoff sequence, evaluation signals, and pitfalls.

For deterministic controller/watchdog changes, use `references/read-only-continuation-runtime-review.md` as the independent negative-path review checklist.

## Controller admission evaluation

Before the first live mission under a new or materially changed deterministic controller, require a fixed pre-controller evaluation contract. Evaluator self-tests, implementer-authored `QUALIFIED` JSON, process exit codes, and hash-bound self-attestation are never proof of passing.

The admission suite must measure at least: exact Routine/Standard/Critical routing (conflicting signals, escalation, 100% Critical recall, zero unsafe under-routing); generated worker-prompt completeness, zero-context executability, exact authority boundaries, and independent hash-bound semantic review; event-driven reconciliation and wake behavior with no blind `wait`/`sleep` plus stale-process failure injection; Herdr ownership, cross-system identity, explicit worktree paths, and zero close/reuse of foreign panes; learning-record destination and quality; deterministic fail-closed integration ordering where every safety-bearing input requires an exact boolean (`is True`/`is False`), never generic truthiness; and resource admission at approved workload/reserve/pressure boundaries, including malformed/missing metrics, workload-class differences, weighted-slot exhaustion below the emergency process ceiling, and proof that cumulative swap occupancy alone must not block.

Use two distinct layers: an offline deterministic suite (missing adapter/controller returns a distinct `NOT_READY` failure, never skip or pass) and external admission evidence (hash-bound prompt review, an isolated named-session Herdr canary on a disposable repository, and dashboard publication bound to the current artifact that semantically projects actual controller state). Qualification publication is a two-phase transaction (`PENDING_FINAL_ADMIPTION` → `QUALIFIED`) with attempted rollback on any post-qualification failure; final admission is the last operation allowed to mutate report, canary, or publication evidence; and material change to the admission path requires fresh independent hash-bound review. Only an explicit final `QUALIFIED` permits the first bounded live mission; `NOT_READY`, offline `FAIL`, or `PENDING_EXTERNAL` prohibits launch.

Load `references/controller-admission-evidence.md` for the full provenance, real-canary, adversarial-validator, exact-publication, parent-reproduction, and rollback requirements.

**Completion criterion:** the real controller adapter passes the offline suite, independent prompt review, isolated Herdr canary, failure-injection gates, and bound dashboard evidence; the final artifact says `QUALIFIED` and can be reproduced without touching a real project.

## Policy-change verification

After changing the mission contract, lifecycle rules, authority model, evidence gate, or helper scripts, load `references/fail-closed-policy-validation.md` and run the contract tests, disposable Beads smoke test, and Python compilation commands it defines. Require negative-path coverage for every fail-closed rule and a nearby-valid case for every placeholder detector. For consequential changes, obtain a fresh read-only independent re-review before treating the policy as ready.

**Policy-surface alignment:** when a new invariant changes a contract field or budget, update the validator, regression tests, `templates/mission.json`, governing reference, and package version as one reviewed change. Before resuming a paused mission, validate its already-approved historical envelope with the installed package; never silently lower a valid approved budget to satisfy a stale validator. Commit the reviewed source package before syncing it to the active profile, rerun the package gates from the installed directory, and require byte-identical source/install contents before activation.

When synchronizing a public/source package with the installed skill, load `references/skill-package-sync.md`. Compare before copying, reconcile rather than downgrade, include every file consumed by packaged tests, rerun tests from the installed path, and require byte-identical source/install package files before declaring reload readiness.

## Verification checklist

- [ ] Approved, validated mission contract exists.
- [ ] Repo instructions, Git/worktrees, Beads, Herdr, and resources reconciled.
- [ ] Mission epic and dependency graph are durable and cycle-free.
- [ ] Every task separates urgency from risk and defines acceptance/evidence.
- [ ] Every active claim maps to one worker, pane, branch, worktree, and base SHA.
- [ ] Delegated mode has exactly one verified-live idle watchdog for the current controller pane and one qualified completion watcher per active worker.
- [ ] Weighted capacity, workload class reserves, available-RAM floor, PSI/swap-I/O pressure gates, emergency process ceiling, retry budget, and single full-suite/integration lanes are enforced; cumulative swap occupancy is not a unilateral blocker.
- [ ] Every blocked bead carries a durable exact boundary; no invented authority gate was applied to a contract-authorized action.
- [ ] Every dispatched unit matches the approved routing plan (lane, review policy); deviations are re-approved or recorded as in-lane judgment.
- [ ] Critical work (and Standard work where review was required) has independent review evidence at the exact candidate SHA; plan-only lanes carry no separate plan review.
- [ ] Integrated-base checks and merge SHA are recorded before task closure.
- [ ] Push/release/deploy occurred only under explicit authority.
- [ ] Dashboard contains only sanitized projection data.
- [ ] Pause/closure sweep leaves no mission-owned processes forgotten.
- [ ] Final verdict names incomplete/waived work and real evidence; no fabricated success.
