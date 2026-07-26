# Verification Scope and Budget Discipline

## Principle

Verify the artifact that changed. A control-plane-only change (for example, mission budget, authority amendment, or orchestration metadata) must use the contract validator and its focused policy tests. It does not justify a product-wide suite.

## Broad-suite reservation

Treat a finite broad-suite budget as a reservation ledger, not merely a counter:

1. During intake, count every mandatory broad command/gate in acceptance and reserve enough authorized slots before preview. A generated default must not contradict mandatory acceptance by leaving no capacity for the final integrated gate.
2. Before starting a broad suite, identify the frozen-plan gate and target SHA it satisfies. Reserve the final available slot for the named final integrated gate; do not spend it on control-plane verification or worker convenience.
3. Never run a broad suite concurrently with an implementation lane unless the frozen plan explicitly calls for it and resource admission covers both.
4. A worker brief saying “do not run the broad suite” is not enforcement evidence. Inspect live worker commands when practical; if a forbidden broad run appears, terminate it safely, record the policy incident and observed partial state, and tighten the next brief/route.
5. Keep two truthful concepts in metadata: **actual broad runs** (including worker violations) and **authorized gate slots used**. An interrupted run without complete PASS evidence is an actual partial incident, not gate evidence and not completed authorized-slot consumption.
6. A completed forbidden broad run is still an incident and actual resource use. It does not satisfy or consume a reserved mandatory gate unless it ran at the exact required integrated SHA and acceptance surface. Do not let an accidental worker run silently revoke an already-approved mandatory final gate. If the preview explicitly defined `maxFullSuites` as a hard monetary/runtime ceiling rather than an operational gate budget, then crossing it remains a human boundary; make that consequence explicit during intake.
7. Reuse a completed broad PASS only when exact product SHA and declared broad acceptance surface are unchanged. Otherwise preserve the evidence as historical and run the required serialized gate within its reservation.

## Independent review gate

A closed or PASS-labeled lane is not automatically integrable. Before serialized composition, reconcile exact candidate SHA, artifact and watcher receipt, focused rerun, fixture hash, ownership diff, and a fresh exact-SHA independent review. Reopen the lane for bounded correction when review finds actionable defects, even if prior metadata said closed.

## Dependency graph hygiene

Do not let Beads closure dependencies deadlock serial composition. A feature-lane task may close only when its own acceptance evidence is complete; the separate composition task owns cross-lane integration evidence. If the graph requires a lane to be closed before the task that would provide its integration evidence can begin, reconcile the graph deliberately and record why rather than falsely marking integration complete.

## User authority amendments

When a user explicitly raises a mission-wide correction limit and directs autonomous continuation, amend the contract and durable ledger with timestamp, scope, and rationale; validate the active contract; then resume within the new cap. Continue to escalate failures through model/reviewer/decomposition strategy. Do not request repeated authorization below that amended cap unless scope, external authority, destructive operation, release/deploy, or another real contract boundary changes.
