# Visible Droid review handoff and qualified completion watching

## Before launching a Droid review in a detached worktree

1. Materialize the review brief **inside the exact review worktree** before starting Droid. Mission-state `.hermes/conductor/briefs/` files are usually uncommitted/ignored and do not automatically appear in a detached worktree.
2. Verify the exact brief path from that worktree (`test -r ...`) before submitting the prompt. A missing brief makes the review non-certifying; do not infer a verdict from another prompt.
3. Record the candidate SHA, review-worktree path, visible Herdr pane ID, model/routing, and read-only boundaries in Beads before dispatch.

## Qualified watcher for a visible interactive reviewer

A `herdr wait agent-status ... done` notification is useful telemetry but is **not** a Conductor-qualified completion watcher. A qualified watcher requires all of:

- the live reviewer process PID and `/proc/<pid>/stat` start ticks captured before attachment;
- a non-existent-at-attachment result JSON path;
- a unique completion token;
- a worker-created result JSON containing that token;
- `watch_worker_completion.py` launched with the controller pane and current controller session;
- its receipt path recorded in Beads.

For an interactive Droid review, instruct Droid before completion to create the result JSON with at least `completionToken`, `verdict`, `candidateSha`, and concise findings. Do not manufacture that artifact from the controller: it must represent the reviewer’s result. Attach the canonical watcher before the reviewer exits. On retry, use a fresh token, result path, receipt path, worker PID/start ticks, and watcher handle.

## Recovery

If the reviewer completes without a qualified watcher or cannot read its brief, mark the attempt non-certifying in Beads, retain the pane transcript as evidence, repair the handoff, and re-run the read-only review. Do not start implementation based on that attempt.
