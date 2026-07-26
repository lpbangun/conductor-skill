# Correction Convergence and Escalation

Use this policy for implementer→reviewer loops in Standard and Critical mission work. The goal is autonomous convergence without accepting weak semantics or turning every difficult third fix into a user interruption.

## Distinguish three events

1. **Correction cycle:** implementation candidate receives actionable independent FAIL and returns to bounded correction.
2. **Strategy escalation:** Conductor changes how the next bounded attempt is executed while remaining inside approved scope and authority.
3. **Human escalation:** Conductor requests a decision because continuing would cross an approved circuit breaker or decision envelope.

A strategy escalation is not a human boundary.

## Default convergence policy

- Cycle 1: send exact findings to the same bounded branch; require RED/GREEN and fresh review.
- Cycle 2, or the second materially similar finding: perform root-cause classification before dispatch. Change at least one relevant dimension—model/provider route, implementer, reviewer, task decomposition, focused reproduction, invariant test, or ownership slice. Do not merely resend a longer version of the same prompt.
- Later cycles below `maxCorrectionCycles`: continue only when the candidate made measurable progress or a new strategy addresses the remaining finding. Record `correction_count`, finding fingerprints, strategy generation, changed dimension, and progress evidence.
- At `maxCorrectionCycles`: stop additional correction dispatch and request a budget decision unless another already-approved lane can proceed. This is the finite human circuit breaker.

For delegated long missions, propose a default `maxCorrectionCycles` of 5 in the mission preview. Lower values are appropriate only when cost, risk, or checkpoint intent justifies them and the preview makes the early-stop consequence explicit.

## No-progress detection

Treat two consecutive cycles as no-progress when they preserve the same actionable finding family without narrowing the failing behavior, strengthening a regression test, or changing the candidate semantics. Green tests alone are not progress when review identifies that tests assert labels, metadata, or permissive fallbacks instead of behavior.

On no-progress:

1. preserve the branch and exact review evidence;
2. derive the smallest semantic reproduction;
3. classify whether the defect is implementation, acceptance interpretation, test weakness, or ownership decomposition;
4. change execution strategy;
5. issue a fresh token/claim and exact-SHA brief;
6. require a fresh independent reviewer.

Do not weaken acceptance, strip failing rules before validation, or count warnings as enforcement merely to converge.

## Human boundaries

Ask the user before:

- exceeding the approved `maxCorrectionCycles`;
- changing product scope, architecture, acceptance, external side effects, or destructive authority;
- exceeding an explicit cost/time/token/full-suite limit;
- continuing after repeated no-progress when no materially different in-envelope strategy remains.

Do not ask merely because:

- a third correction is needed while the approved cap is higher;
- a different model/reviewer/decomposition is warranted;
- the branch remains within approved ownership and resource admission;
- a review correctly rejects a green-but-semantically-weak candidate.

## Evidence and closure

A correction lane becomes PASS only when focused evidence is bound to the exact SHA and a fresh independent review reports no actionable finding. Mark a reviewed PASS implementation task complete/closed according to the plan's integration semantics; do not label it `blocked` merely because a serial composition task is not ready yet. The dependency graph, not a false blocked state, should represent pending composition.
