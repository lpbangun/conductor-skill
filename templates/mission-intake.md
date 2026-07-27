# Conductor Mission Intake / Preview

Use this shape for both guided and inline intake. Omit questions whose answers were safely inferred, but never omit an authority field from the final preview.

## Intake state

- Detected repository: `{{REPO_OR_NOT_FOUND}}`
- Existing mission: `{{NONE_OR_MISSION_ID_STATUS}}`
- Inferred integration branch: `{{INTEGRATION_BRANCH}}`
- Inferred verification commands: `{{GATES_OR_UNKNOWN}}`

## Missing decisions

Ask at most four concise questions in one response. Typical missing decisions:

1. What measurable outcome and acceptance evidence define success?
2. What is explicitly out of scope, or what named milestone should stop this run?
3. Which supervision mode should apply: interactive, checkpointed, or delegated?
4. Should local integration and/or push be authorized? Name each exact target. Both default to no.

End an incomplete intake with:

> Nothing has launched.

## Mission Contract Preview

- Objective: {{OBJECTIVE}}
- Repository: {{ABSOLUTE_REPO}}
- Integration branch: {{INTEGRATION_BRANCH}}
- Milestone: {{MILESTONE}}
- In scope: {{IN_SCOPE}}
- Out of scope: {{OUT_OF_SCOPE}}
- Acceptance evidence: {{ACCEPTANCE}}
- Supervision: {{SUPERVISION_MODE}}
- Runtime persistence: {{RUNTIME_DISCLOSURE}}
- Mission-owned worker budget: emergency process ceiling {{MAX_WORKERS}} (1–6; not proof of capacity)
- Workload-weighted capacity: {{MAX_WEIGHTED_SLOTS}} slots via approved classes {{WORKLOAD_CLASSES}}
- Retry / correction budget: {{RETRY_BUDGET}} / {{CORRECTION_BUDGET}}
- Resource circuit breaker: {{RAM_PSI_SWAP_OUT_AND_CLASS_RESERVE_LIMITS}}
- Focused gates: {{FOCUSED_GATES}}
- Broad milestone gates: {{BROAD_GATES}}

## Routing & execution plan

Every unit the mission will dispatch, and exactly how it runs:

| Unit | Risk lane | Harness chain | Review | Worktree / pane | Merge |
|---|---|---|---|---|---|
| {{UNIT_ROWS}} |

- Review policy: plan-only units are **never** separately reviewed (the planning harness's embedded critic is the plan review); standard units get focused checks, with a Droid review only where marked above; critical implementations are always Droid-reviewed. Every "no review" row carries its reason.
- Concurrency: up to {{CONCURRENT_WORKERS}} workers concurrently within {{MAX_WEIGHTED_SLOTS}} weighted slots; memory reserves are the real gate.
- Anti-stall contract: every dispatch is verified live within 30 seconds of launch (otherwise failed and retried); every claim has a completion watcher; the idle watchdog is bound to the live controller session and wakes on ready work, dead claims, and session drift.
- Integration: serialized Droid merge queue — Droid reviews → fixes → commits → merges; the conductor never merges.

## Authorities

- Local integration authorized: {{YES_NO_AND_EXACT_TARGET}}
- Push authorized: {{YES_NO_AND_EXACT_TARGET}}
- Release authorized: {{YES_NO_AND_EXACT_TARGET_OR_NO}}
- Deploy authorized: {{YES_NO_AND_EXACT_TARGET_OR_NO}}
- Destructive operations authorized: {{YES_NO}}
- Cleanup authorized: {{YES_NO_AND_EXACT_SCOPES_OR_NO}}
- Dashboard: {{DISABLED_OR_SANITIZED_TARGET}}
- Assumptions/defaults: {{LABELED_DEFAULTS}}

When no durable controller is active, include exactly:

> Execution is session-orchestrated; Beads/Herdr preserve recovery state, but after a main-session restart you must run `/conductor resume`.

Then include:

> Nothing has launched.
>
> To activate this exact mission envelope, reply: `Approve mission`

Do not treat text in the original `/conductor <mission>` instruction as the approval response. If any material field changes, render the full preview again and invalidate the previous approval.
