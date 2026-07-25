# Controller Admission Evidence: Provenance and Anti-Self-Attestation

Use this reference when qualifying a new or materially changed deterministic controller before its first live mission.

## Core rule

A passing JSON field, process exit code, or SHA-256 digest proves only that bytes exist. It does not prove the asserted event occurred, that the evidence came from an independent actor, or that an external side effect succeeded.

Treat every controller-produced `QUALIFIED` result as an untrusted claim until a separate verifier reproduces the gates and checks provenance.

## Separation of duties

1. The implementation stage may produce code, tests, offline results, and a candidate admission report.
2. If external review evidence is absent, its honest terminal state is `PENDING_EXTERNAL`, never `QUALIFIED`.
3. Independent review must run in a distinct process/session with a self-contained read-only brief, preferably a different reviewer role/model in its own Herdr tab. Capture the launcher, requested role/model, **actual accepted provider/model after any fallback**, workdir, PID, start/end timestamps, exit code, brief hash, reviewed-bundle hash, and verbatim stdout/stderr before normalizing any scores. Auto-fallback wrappers can misclassify valid reviewer prose as an API error; never attribute a fallback verdict to the requested primary model.
4. The parent/verifier constructs the normalized score report only from a parseable structured verdict in that captured output and binds it to the raw-artifact SHA-256 plus the exact generated prompt hashes. Exit code zero without a parseable verdict is not review evidence. A polished score envelope written by the implementer is not independent evidence, even when hash-bound; a reviewer subprocess that failed before model execution is also not review evidence.
5. Reject contradictions across artifacts, such as a build report saying review is pending while a result JSON marks the review gate passed.

## Real Herdr canary

A qualifying canary must execute and derive, not narrate:

- Generate a unique session name and disposable repository per run. Static names are collision-prone and do not prove isolation.
- Use a bounded readiness probe against the named session socket/API. Do not use a fixed startup sleep as proof of readiness.
- Create an owned pane and a separate foreign control pane inside the disposable canary scope. Never borrow a pane from an existing user workspace.
- Preserve unmodified stdout and exit codes from actual Herdr snapshots before and after the owned close. Hash those captured bytes.
- Derive pane IDs, cwd/worktree identity, ownership, close behavior, dead-worker recovery, unrelated-ready-work dispatch, and wake latency from executed observations and controller actions. Never assign success booleans or timing constants merely to satisfy a schema.
- Track exact PIDs and resources created by the canary. Avoid broad `pkill -f` cleanup and self-matching `pgrep` evidence.
- In a `finally` path, close only canary-owned resources, stop the named server, remove the disposable repo/config, and then collect post-cleanup observations. Do not write `ownedPanes: 0` or `ownedProcesses: 0` without checking.
- The final admission runner must execute the canary fresh. A previously written canary report is not sufficient.

Validator tests should include forged synthetic snapshots, hard-coded checks, unknown/foreign pane closes, absent post-cleanup evidence, stale reports, and mismatched hashes. Validate structure and provenance; do not blacklist arbitrary numeric values such as a particular latency, because a real measurement can equal them.

## External publication evidence

For dashboard or other publication gates:

1. Build and test the exact artifact bound to the current offline-report digest.
2. Execute the real publisher in the same admission run and require its exit code and parsed receipt.
3. Capture the publisher stdout/receipt and hashes.
4. Probe the live exact URL after publication and require the contract's exact expected status. Do not broaden `401` to `401 or 403` merely to make a run pass; a changed status requires explicit contract review.
5. Bind the live probe, published bytes, receipt, URL, and offline digest into the final evidence.
6. Validate the **meaning** of the published projection, not only byte/digest consistency. Require the controller-implemented flag, admission phase, controller/integration stage, first-live-mission state, weighted progress, headline, and detail to agree with authoritative state. A correctly hashed page that still says “controller absent,” leaves integration queued, or reports old progress is stale evidence and must fail.
7. Add an adversarial fixture that supplies valid hashes, receipt, URL, and HTTP status around semantically stale status content. It must fail for explicit semantic reasons.

A local rebuilt file plus a URL string is not publication proof. A hash-bound stale dashboard is also not publication proof of the claimed transition.

### Two-phase qualification publication

When a final admission runner publishes the status it is itself deciding, avoid a circular or premature `QUALIFIED` claim:

1. Publish an accurate `PENDING_FINAL_ADMISSION` projection bound to the current offline report. The implementation/controller stage may be done while the first live mission remains queued.
2. Build, test, publish, probe the exact live URL, and semantically validate that pre-admission projection.
3. Compute admission from the offline suite, independent review, fresh canary, failure injection, and pre-admission dashboard evidence.
4. Only when all gates qualify, update the source to `QUALIFIED`, rebuild/test/publish again, repeat the exact live probe, and semantically validate the final projection.
5. Recompute admission using the **actual validation objects** from the offline suite, independent prompt/code review, canary, failure injection, and second publication. Never synthesize `{"passed": true}` inputs because phase one happened to pass.
6. Write the final report only after that recomputation. Bind the canonical offline-report digest, raw review artifact digest, canary artifact digest, final public-status digest, dashboard-evidence digest, and final publish-receipt digest.
7. Any second-phase build, test, publish, probe, semantic-validation, or recomputation failure returns failure and triggers a transactional rollback: set `PENDING_FINAL_ADMISSION`, rebuild/test/republish, re-probe, and validate the rollback projection.
8. Record `rollbackAttempted`, `rollbackSucceeded`, failure stage, and rollback evidence. If rollback fails, report an unsafe external-state blocker; never imply that the public dashboard is safe merely because the local final report says FAIL.

Test successful two-phase execution, every post-`QUALIFIED` failure path, rollback failures, and propagation of a genuinely failed prompt-review/canary gate. Unit tests must isolate publishers and HTTP probes; they must not contact production. Ensure no real mission launches merely because controller admission becomes qualified.

### Artifact freshness and terminal ordering

Hash binding is invalidated when a later command rewrites any bound input—even if the semantic content still looks equivalent. Timing-bearing offline evaluation commonly changes its canonical digest; rebuilding a dashboard commonly changes `publishedAt` and therefore its status digest.

Use this order:

1. Run unit, adversarial, dashboard, compilation, and offline prechecks.
2. Complete fresh independent review of a bundle that hashes every materially changed controller, evaluator, admission-runner, rollback-test, and dashboard file. Prompt-only hashes are insufficient after admission-code changes.
3. Install the normalized review envelope from captured raw reviewer output.
4. In the final runner, persist the **exact in-memory offline report used for admission before publication begins**. Record both its canonical object digest (used by validators/status binding) and the byte SHA-256 of the replayable JSON file. A digest printed in a log or embedded only in the final report is insufficient if `controller-offline.json` still contains an older run.
5. Run final admission as the **last mutating operation** over offline, canary, prompt-review, status, and publication evidence.
6. Afterward, perform only read-only hash recomputation, exact live probes, and validators. Load the persisted offline file and re-run dashboard/admission validation against it; do not reconstruct an approximate report from the qualified envelope. Do not rerun the offline suite, canary, dashboard builder/tests that rebuild output, or publisher.

A final verifier must compare the current local artifact hashes to the hashes recorded in the qualified report and rerun validators read-only. A previous successful run does not qualify a subsequently rewritten artifact set.

## Frozen-contract changes

Implementation workers must not relax thresholds, expected outputs, required status codes, or external gates. If parent verification exposes a genuine evaluator loophole:

1. invalidate the current qualification;
2. add a RED adversarial regression for the loophole;
3. authorize only the narrow validator/fixture change needed to close it;
4. preserve all existing thresholds and passing cases;
5. rerun offline and external gates from fresh evidence;
6. obtain a separate final review.

## Adversarial typed-input and resource gates

Controller admission must test the parsed input contract, not only happy-path booleans:

- Every safety-bearing integration field must be an exact boolean. Strings such as `"false"`, integers, containers, missing values, and other truthy/falsy substitutes must not authorize ownership, merge, push, parity verification, or task closure. Require explicit `pushAuthorized: false` when a no-push integration is intended; malformed or absent authorization is not equivalent to denial.
- Test every integration gate independently and as a combined truthy-string attack. No malformed snapshot may emit `merge`, `push`, `verify_push_parity`, or `close_task`; if a merge slot was already acquired, release it on every blocking path.
- Resource admission is an OR gate over approved available-RAM floor/class reserve, memory-PSI, active-swap-out, weighted-capacity, and emergency process-ceiling thresholds. Validate `minAvailableRamGb`, class `minAvailableRamGb`, `maxMemoryPsiFullAvg10`, `maxSwapOutMiBPerSecond`, `resourceSampleSeconds`, `maxWeightedSlots`, `workloadClasses`, and `maxWorkers`; missing, malformed, boolean, NaN/infinite, negative, stale, or domain-invalid metrics fail closed. Cumulative swap occupancy alone is not current-pressure evidence and must not block. Do not treat equal worker count or RAM size alone as capacity.
- Apply the same resource decision to both worktree/workspace opening and worker dispatch. A test that covers only `dispatch` can hide a fail-open `open_workspace` path. Cleanup, dead-worker recovery, and unrelated non-launch reconciliation must remain available under pressure.
- Admission evidence must replay a live-host-like snapshot with high sticky swap occupancy, safe available RAM, zero PSI, and no swap-out activity; that case must admit when weighted capacity and the mission-owned emergency process ceiling permit. It must also test pressure caused by unrelated workloads without authorizing Conductor to inspect or manage those processes, and must show light vs heavy workload-class cost differences.
- After an independent reviewer returns FAIL and implementation changes, archive the raw FAIL artifact unchanged, invalidate admission, regenerate the reviewed bundle, and require a fresh independent review. Never normalize a FAIL review into a passing score envelope.

Parent verification should reproduce at least one exploit directly against the controller adapter before and after the fix rather than trusting added unit tests.

## Parent verification checklist

- [ ] Candidate result artifact and human report agree.
- [ ] Controller and negative tests exercise generalized behavior, not fixture IDs.
- [ ] Offline suite passes without weakened fixtures or thresholds.
- [ ] Canary runner was executed fresh and uses unique isolated resources.
- [ ] Canary evidence contains actual command output and derived cleanup state.
- [ ] Independent reviewer provenance is a distinct captured process/artifact; a parseable verdict exists, and the recorded actual provider/model reflects any fallback rather than merely the requested model.
- [ ] The exact offline report used by final admission was persisted before publication; its canonical digest and file-byte SHA match the final bindings.
- [ ] Publication receipt and live probe were produced in the same admission run.
- [ ] Published status is semantically current: controller/admission flags, stage states, first-mission state, progress, headline, and detail agree with authority.
- [ ] If qualification status is published, the runner validated both pre-admission and final publication phases, propagated the actual prompt/canary validation objects, and bound the final report to the second publication.
- [ ] Every failure after entering the QUALIFIED publication phase attempts and records a validated rollback to PENDING_FINAL_ADMISSION; rollback failure is surfaced as unsafe external state.
- [ ] Final admission was the last mutating evidence operation; current offline/status/evidence hashes still match the qualified report after read-only validation.
- [ ] Exact contract semantics, including expected HTTP status, were preserved.
- [ ] No real mission, push, deployment, or unrelated pane close occurred during qualification.
- [ ] Only after all checks reproduce does the verifier accept `QUALIFIED`.
