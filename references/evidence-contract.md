# Evidence Contract

No task moves from implementation to review, PASS, integration, or closed on narrative self-report alone.

## Task metadata

Use Beads labels and metadata for compact, queryable state:

- labels: `conductor`, `mission:<slug>`, `risk:routine|standard|critical`, `milestone:<slug>`;
- metadata: `risk_rationale`, `escalation_triggers`, `branch`, `worktree`, `worker`, `worker_role`, `herdr_workspace`, `herdr_pane`, `base_sha`, `candidate_sha`, `commit_sha`, `merge_sha`, `claim_lease`, `last_heartbeat`, `retry_count`, `tests`, `review_verdict`, `reviewer`, `integration_tests`, `push_parity`.

Do not place secrets, raw prompts, transcripts, source code, or large logs in metadata. Append concise evidence notes that point to durable local files/commands when detail is needed.

## Evidence by transition

### Claim → working

Required:

- successful atomic Beads claim;
- branch and absolute worktree path;
- exact base SHA and integration branch;
- stable worker identity and role;
- Herdr workspace/pane identity;
- lease and heartbeat timestamps;
- visible expected agent in working state.

### Working → candidate

Required from independent conductor inspection:

- `git status --short` and branch identity;
- `git diff --stat <base>...HEAD` plus changed/untracked file inventory;
- candidate SHA or explicit dirty candidate state;
- focused command(s), exit code(s), and concise result;
- acceptance mapping and known residual risks;
- no unauthorized files/effects.

A dirty candidate may enter review only when the review tool is explicitly reviewing the working tree and the exact diff is captured. Integration still requires a stable commit SHA.

### Candidate → review PASS

Required:

- reviewer identity and harness;
- exact candidate SHA/working-tree fingerprint;
- exact integration base reviewed against;
- verdict: `PASS`, `PASS_WITH_NOTES`, or `FAIL`;
- actionable findings with severity and acceptance impact;
- fresh re-review after material corrections.

`PASS_WITH_NOTES` may proceed only when every note is demonstrably non-actionable under the approved acceptance bar. Record the reason.

### Review PASS → integrated

Required:

- clean integration checkout before merge;
- candidate commit SHA confirmed unchanged;
- merge command/result and merge SHA;
- focused integrated-base checks with exits;
- broad-suite result only when this transition is the named milestone gate and the declared product tree or broad acceptance surface changed, or a concrete unresolved failure requires it; reuse bound broad-suite evidence when the integrated product SHA and declared broad acceptance surface are unchanged;
- remote parity if push was authorized.

### Integrated → closed

Required:

- task present on the integration branch at `merge_sha`;
- required integration evidence passes;
- no unresolved actionable review finding;
- Beads close reason states what shipped and cites the merge SHA;
- dashboard material transition published if enabled.

## Failure and blocker evidence

A blocked task records:

- blocker type: dependency, test, review, resource, strategy, permission, environment, or external;
- observed evidence and last safe SHA;
- what was tried and retry count;
- recovery owner and next allowed action;
- whether unrelated work remains schedulable.

A budget stop records the exact exceeded budget and current safe state. Never label `not converged`, timeout, OOM, or unavailable credential as PASS.

## Mission closure evidence

Capture:

- milestone and acceptance verdict;
- integrated branch and final SHA;
- authorized remote parity;
- focused/broad commands and results;
- closed, waived, blocked, or deferred Beads IDs;
- duration, worker/model calls, correction cycles, full-suite count, unique review findings, duplicated work, resource incidents, and human interventions;
- live process/workspace cleanup result;
- dashboard update result;
- policy lessons proposed for later review, not applied during the mission.

## Evidence quality checks

- Exact SHA, not “latest.”
- Exact worktree, not workspace label alone.
- Actual exit status, not model interpretation.
- Current transcript/process state, not stale watcher notification.
- Integrated-base result, not feature-branch-only green.
- Verified remote SHA, not “push succeeded.”
