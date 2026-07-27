# Controller release and delegated handoff

Use this release checklist for continuation-runtime changes.

1. Work in an isolated source worktree; keep installed bytes frozen.
2. Add fail-closed and nearby-valid tests for each behavior.
3. Run package gates, compile, and diff checks from source.
4. Commit the exact candidate.
5. Run a disposable live-Herdr canary that binds repo, pane, and non-null session.
6. Obtain an independent review on that exact commit; unresolved High findings block install.
7. Install an explicit package manifest, delete stale package-local state, run installed gates, and require byte-identical surfaces.
8. Only then start a fresh controller and one pane/session-bound watchdog.

The canary must show `wakeDelivered: true`, a controller working transition, durable throttle/ack state, and no Beads mutation by the watchdog. Close the disposable workspace and remove its repository afterward.

## Operator pause and repair isolation

If the user says stop, cancel, or pause while a mission is active, that instruction overrides the roadmap immediately. Before changing this skill or its runtime package: stop mission-owned controller/worker/watchdog processes, release active Beads claims, persist the pause reason, close only owned paused/completed panes, and preserve Git/Beads evidence. Do not run a new controller, review, gate, or canary against the live mission. Perform package repair in an isolated source worktree and test with disposable fixtures; resume only after the user explicitly directs it.

For a controller replacement: retire the prior pane/guard, create the new controller at the mission repo, deliver a file-backed handoff, bind the returned session, start one tracked watchdog, prove its singleton lock, and only then resume any observer.

Do not install on test-only evidence, bind a null session, or treat process existence as qualification.