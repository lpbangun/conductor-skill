# Fail-Closed Policy Validation

Use this when changing the Conductor contract, lifecycle rules, evidence gate, or integration authority. The goal is to prevent a validator from producing a reassuring `VALID`/`CLOSABLE` result for a contract that cannot safely execute.

## Three distinct validation gates

Do not collapse these into one boolean:

1. **Structural draft:** schema, types, enums, ranges, absolute-path shape. Draft placeholders and missing approval/ledger IDs are allowed.
2. **Approved envelope:** real repository and enabled-dashboard directories exist; approval identity/time are present; mission text and test commands contain no explicit placeholders; push authority names one exact target.
3. **Active ledger:** approved-envelope checks plus an active-capable status and a non-placeholder Beads mission ID. Then reconcile the ID with live `bd show`; local validation cannot prove ledger existence by itself.

Approval precedes Beads bootstrap, so the approved gate must not require a mission ID. Activation follows bootstrap, so the active gate must require one.

## Slash-command launch barrier

Treat `/conductor` and `/conductor <mission>` as intake turns, not activation:

- bare invocation performs read-only discovery and guided intake;
- inline mission text prefills intake but cannot approve itself;
- the latest complete preview must state “Nothing has launched”;
- only a later explicit `Approve mission` activates that unchanged preview;
- material edits invalidate the prior approval and require a new preview;
- status is read-only, while resume is limited to an unchanged approved envelope;
- disclose when no durable controller exists and manual `/conductor resume` is required after restart.

Regression checks should fail if the skill loses the direct command examples, no-mutation bare path, inline-is-not-approval rule, exact approval phrase, re-preview rule, or runtime persistence disclosure.

## Precise placeholder detection

Reject explicit tokens such as:

- `REPLACE: ...`
- standalone `TODO` or `TBD`
- `/absolute/path/...`
- known example-command markers

Do not reject ordinary prose merely because it contains words such as “replace,” “todo,” or “tbd” in a larger legitimate sentence. Every placeholder rule needs both a rejection test and a nearby-valid acceptance test.

## Semantic evidence, not presence checks

Before close, require more than non-empty metadata:

- focused and integrated test summaries begin with an unambiguous PASS token;
- Standard/Critical review verdict is `PASS` or justified `PASS_WITH_NOTES`;
- reviewer identity is present where review is mandatory;
- candidate and merge SHAs resolve to commit objects in the target repository;
- push parity cannot be `not_authorized`/`not_required` when the contract requires push.

A value like `tests=FAIL` is populated data but failing evidence. Treat it as not closable.

## Authority before serialization

A lock prevents concurrency; it does not grant permission. Check, in order:

1. `localIntegrationAuthorized` is true;
2. current identity matches `integrationOwner`;
3. the native Beads merge slot is acquired atomically;
4. candidate/base/evidence remain stable;
5. integrate;
6. release the slot even after a failed gate.

## Cross-system identity

A label is not identity. Before work begins, cross-check:

- Beads claim actor and task ID;
- Herdr returned workspace/pane or tracked subprocess handle;
- actual cwd equals the absolute worktree path recorded in Beads;
- branch and base SHA match the brief and Git;
- explicit Herdr `--path` matches the user's worktree convention.

## Regression discipline

After any policy or validator change, run:

```bash
ROOT="${HERMES_HOME:-$HOME/.hermes}/skills/autonomous-ai-agents/conductor"
python3 "$ROOT/scripts/test_contract.py" -v
python3 "$ROOT/scripts/test_invocation_contract.py" -v
python3 "$ROOT/scripts/smoke_test.py"
python3 -m py_compile "$ROOT/scripts/"*.py
```

The regression matrix should contain both happy and fail-closed paths:

- approved without ledger ID passes;
- active without a real/non-placeholder ID fails;
- explicit placeholders fail while legitimate neighboring prose passes;
- fractional count budgets fail;
- every unknown budget field fails, including legacy `maxSwapUsedPercent` and alternate occupancy-limit names;
- missing/invalid `maxWeightedSlots` or `workloadClasses` (including missing `light`/`standard`/`heavy` and unknown class fields) fails;
- sticky high cumulative swap occupancy with safe RAM, safe PSI, and no active swap-out admits when weighted capacity and the mission-owned emergency process ceiling permit;
- missing/malformed PSI or `pswpout` sampling evidence fails closed for both workspace opening and dispatch;
- light vs heavy class cost/reserve differences and weighted-slot exhaustion below `maxWorkers` are covered by policy docs/tests;
- enabled missing dashboard path fails;
- push without exact target fails;
- failing tests and non-commit SHAs fail pre-close;
- dependency readiness, atomic claim, merge-slot acquire/release, and close propagation pass in a disposable repo.

For consequential policy edits, obtain a fresh read-only independent review. If it finds a false positive, add the legitimate case before narrowing the detector; if it finds a fail-open case, add the negative case before accepting the fix.
