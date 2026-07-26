# External Supervision for Conductor Dogfooding

Use this topology when evaluating Conductor itself, refining its policy, or observing whether the skill causes correct autonomous behavior. It is not required for ordinary product missions where no one is evaluating the controller.

## Why separate the roles

A session that both operates a mission and judges the Conductor policy has a blind spot: it observes its own reasoning, not how another agent interprets the installed skill. It may also patch controller policy while relying on that policy, creating moving-target evidence.

Use three layers:

1. **External evaluator:** observes pane transcripts, Beads, Git, resource decisions, watcher receipts, and mission outcomes. It does not claim tasks, dispatch workers, harvest candidates, or update operational state.
2. **Dedicated Conductor:** a persistent interactive Hermes session with Conductor preloaded. It is the sole controller and owns reconciliation, scheduling, dispatch, review/fix routing, integration, and closure.
3. **Workers/reviewers:** bounded panes or subprocesses created by the dedicated Conductor.

This is an ownership boundary, not cosmetic role wording. Exactly one actor may mutate the mission control plane.

## Safe handoff procedure

1. Reach a durable checkpoint. Prefer no active mutation; if a worker remains active, preserve its exact launcher PID/start ticks, pane, claim, lease, result path, watcher, heartbeat, and current Git state.
2. Stop new dispatch from the old controller. Generated-but-unclaimed tokens are inert and must be discarded rather than reused.
3. Freeze the installed Conductor package to reviewed bytes for the evaluation interval. Record its version/source digest or commit. Do not patch it during the run.
4. Start a **persistent interactive** Hermes session in a dedicated Herdr pane with Conductor preloaded. A one-shot `hermes chat -q` exits after one response and cannot remain available for completion-wake events.
5. Give it a self-contained handoff containing:
   - approved contract and authority boundaries;
   - repo/control/integration paths;
   - Beads mission ID and full-suite/correction budgets;
   - active worker lifecycle identities and watcher destinations;
   - open review findings and durable report paths;
   - unused tokens or abandoned launch attempts;
   - explicit declaration that it is now the sole controller.
6. Require the dedicated Conductor to reconcile every fact against Beads, Herdr, Git, `/proc`, artifacts, and live resources before acting. Handoff text is a lead, not authority.
7. Existing completion watchers may target the old controller pane. Rebind safely before artifact creation when possible; otherwise keep an explicit relay path until those attempts finish. All new watchers must target the dedicated Conductor pane.
8. Before relaying an inherited completion event, inspect the receiving pane/transcript and deduplicate on task ID, lifecycle PID/start ticks, completion marker, and receipt path. Do not forward an event already delivered directly.
9. Respect the interactive pane's busy-input semantics. Raw text submitted while Hermes is working may interrupt the current API/tool operation. Use `/queue` for an event that can wait until the current operation completes, or `/steer` only when the new fact must alter the active turn. A message is not delivered merely because `send-text` succeeded: always submit it with `herdr pane send-keys <pane> ENTER`, then re-read the pane and require either the rendered user-message/`Queued:` acknowledgement or `agent_status=working`. Text left at an idle prompt is a failed nudge; correct it in the same observation cycle. Never resend blindly because an acknowledgement is not visible in a short pane tail.
10. The external evaluator is active but not a second controller. It must detect a clearly idle controller with already-authorized ready work and deliver one verified evidence-based nudge; passive status narration is insufficient. It still must not run the scheduler, claim work, harvest candidates, or update Beads itself.

## Recurring observer jobs

For a bounded periodic evaluator:

1. Use an explicitly recurring schedule such as `every 12m`. A duration such as `12m` is a one-shot delay even when a repeat count is supplied.
2. Immediately list the created job and require `enabled: true`, `state: scheduled`, the exact recurring schedule, and a non-null `next_run_at`. After the first tick, verify the repeat counter advanced and another `next_run_at` exists; a completed/disabled job is not recurring observation.
3. Each tick must inspect pane state, recent transcript, foreground process, ready frontier, mission-owned workers/watchers, and material timestamps before deciding whether progress is stalled.
4. A nudge is complete only after `send-text`, `ENTER`, and pane acknowledgement verification. If the observer leaves text at the prompt, it must submit it before returning.
5. Deduplicate completion events by task/lifecycle/marker/receipt, never raw-message a busy pane, and do not mutate mission state.
6. Bound the observer by repeat count or mission completion. Record outputs locally unless the user requests messaging delivery.

## Evaluation signals

Observe behavior induced by the skill, not just final code:

- Does restart reconciliation reject stale metadata and preserve live work?
- Does scheduling inspect the complete ready frontier and maintain useful parallelism without inventing lanes?
- Are lifecycle launchers, fallback children, watchers, and artifacts distinguished correctly?
- Does the controller fail closed on ambiguous timeout, identity, ownership, or authority evidence?
- Are review failures converted into narrow correction briefs rather than accepted because tests are green?
- Are completed panes closed and unrelated panes left untouched?
- Does the controller keep Beads, Herdr, Git, and user-facing status consistent?

Record findings outside the active policy package. Normally patch the skill only after mission closure and user review, then start a fresh controller session for the new version. If the user explicitly requests a library update at a bounded checkpoint, treat the running controller as pinned to its already-loaded snapshot, record the installed/session version divergence, and do not attribute subsequent behavior to the new bytes until a fresh controller session starts.

## Pitfalls

- **Dual controllers:** evaluator and dedicated Conductor both dispatch or harvest. This corrupts ownership and invalidates the evaluation.
- **Self-analysis presented as dogfooding:** the same session runs the policy and declares it effective.
- **One-shot controller:** no persistent pane exists to receive completion events.
- **Mutable evaluation target:** installed skill changes mid-run, making behavioral evidence impossible to bind to one version.
- **Blind handoff:** new controller trusts prose instead of reconciling live state.
- **Orphaned wake target:** inherited watchers still notify a retired pane with no explicit relay.
- **Duplicate event relay:** evaluator forwards an event already delivered to the dedicated pane, causing duplicate reconciliation or interruption.
- **Busy-pane raw input:** evaluator sends ordinary text while Hermes is working; the TUI interrupts an active API/tool call. Queue or steer intentionally instead.
