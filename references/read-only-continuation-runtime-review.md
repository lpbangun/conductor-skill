# Read-only Continuation Runtime Review

Use this checklist for independent review of dirty controller, watchdog, completion-notifier, scheduler, or terminal-wake changes. It complements admission tests; it does not authorize edits.

## Establish the exact review surface

- Record `HEAD`, the requested base SHA, `git status --short`, and tracked plus untracked paths.
- `git diff <base>` omits untracked files. Read every relevant untracked file directly.
- If repeated reads, mtimes, sizes, or test results disagree, assume concurrent worktree mutation. Re-read affected files, rerun focused checks, and bind the verdict to the final observed snapshot.
- In a no-edit review, do not stash, reset, add, format, auto-fix, or otherwise mutate source state.

## Authority and pane-input checks

1. Mission eligibility must be a positive allowlist (normally exact `active`), not “anything not terminal.” Test proposed, approved, waiting-user, paused, complete, aborted, and unknown states.
2. Bind runtime arguments such as mission ID and pane ID to the approved contract and recorded controller identity.
3. Verify destination agent/session ownership and expected repo/cwd, not merely pane existence and an `idle` status.
4. Treat `check idle → query Beads/processes → submit input` as TOCTOU. Revalidate immediately before input and prefer atomic queue-or-reject-if-busy semantics.
5. “Exactly one watchdog” requires runtime singleton enforcement or an exact lock/lease/PID-start identity. Prose alone does not prevent duplicate wake races.
6. Keep every external command bounded by timeout and define transient-error retry/backoff. One hung CLI must not hang continuation forever.

## PID and watcher qualification

- Parse `/proc/<pid>/stat` after the final `)`; field 22 is index 19 once the remainder begins at field 3.
- A matching script basename anywhere in argv is not watcher identity. Bind exact watcher PID/start ticks, executable/script identity, task, lifecycle PID/start ticks, destination pane/session, result path, marker/token, and receipt to durable metadata.
- Recheck watcher identity after reading cmdline to reduce exit/reuse races.
- Exact artifact paths are stronger than symlink-resolved equivalence; examine parent-symlink and artifact-creation TOCTOU.

## Complete-frontier and storm checks

- Explicitly disable CLI default limits or paginate to exhaustion for both ready and in-progress work.
- Unexpected JSON shapes must fail closed; never coerce malformed responses to an empty queue.
- Validate ready work while another worker has a good watcher, blocked-only missions, worker-exit/watcher-validation races, malformed throttle state, duplicate guards, and transient CLI failures.
- Rate-limit state must be finite, in-domain, and bound to mission/pane/version. NaN, infinity, corruption, or stale handoff state must not suppress wakes or disable throttling.

## Test adequacy

Fakes must reproduce unsafe transitions, not only happy protocol:

- idle→working between observation and submission;
- pane reuse by another agent/session;
- wrong mission ID versus contract ledger ID;
- spoofed watcher argv and stale watcher identity;
- task counts beyond CLI defaults and malformed JSON;
- hung/transient Beads or Herdr commands;
- two watchdogs racing on one state file;
- a disposable live-Herdr canary when documentation claims transport qualification.

Report PASS/FAIL with Critical/High/Medium/Low findings and exact paths/lines. Passing unit tests do not erase missing negative-path coverage.