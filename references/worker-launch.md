# Worker launch (stable lifecycle + completion artifact)

Use `scripts/dispatch_worker.py` for every active Conductor implementation or independent-review lane. It is the canonical launcher and produces the machine-readable dispatch record required for Beads metadata and watcher qualification.

## Contract

`dispatch_worker.py` accepts an absolute repository/worktree, task ID, role, explicit provider/model, brief file, conductor pane/session, base SHA, result path, and receipt path. It rejects malformed or unsafe input before launch. It then:

1. generates a fresh ≥32-hex completion token;
2. launches a stable, file-backed `hermes chat` waiter without shell interpolation;
3. proves the launcher PID and start ticks from `/proc`;
4. attaches the exact packaged completion watcher to that lifecycle identity;
5. proves the watcher’s argv, PID, and start ticks; and
6. emits one JSON dispatch record or a non-zero failure with no qualifying partial state.

The worker brief must require the returned `completionToken` and `resultJson` path in its artifact. Store every JSON field named `beadsMetadata` in the claimed task before treating the worker as live.

## Role and route choice

- A durable plan freeze that writes/commits a plan is a write-capable `task` lane, scoped to the plan/docs path.
- An independent review is read-only. Critical review uses visible Factory Droid against the exact candidate/base; if unavailable, use an explicit read-only fallback and record the fallback route.
- A mutating lane records the selected provider/model before launch. Do not infer OMP/Droid routing from a Hermes fallback configuration.

## Handoff and kill hygiene

On a controller handoff, retire watchers bound to the prior pane/session before dispatching. Kill only exact launcher, child, or watcher PIDs recorded in the dispatch record—never broad `pkill` patterns.

## Verification

A lane is dispatch-qualified only if its dispatch record, Beads metadata, `/proc` identities, watcher argv, result path, receipt path, and current controller pane/session agree. A launcher failure is a non-zero dispatch failure, never a successful PID.