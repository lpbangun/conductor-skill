# Resource Admission and Operational Validation

Use this reference whenever Conductor defines, changes, reviews, or qualifies worker-admission policy.

## Core distinction

A deterministic policy can be internally consistent and still be operationally wrong. Unit and contract tests that encode a threshold prove **policy-boundary implementation fidelity**, not that the threshold, metric, or capacity model is operationally fit.

Resource admission must establish current capacity for the **next** workload. It must not infer current pressure from a stale cumulative counter, and it must not treat an equal worker count as capacity.

## Signals

Prefer a small set of orthogonal live signals:

- available RAM relative to the absolute emergency floor and the next workload class reserve;
- Linux memory PSI (`full avg10`, and optionally `some`) over the approved sampling window;
- active swap-out rate measured over that window (page delta × page size → MiB/s), not lifetime counters;
- workload resource class / weighted slot cost from the approved mission contract;
- current mission-owned weighted usage and process count;
- global host pressure, including unrelated workloads.

Cumulative swap occupancy is telemetry only. Linux may retain cold pages in swap after pressure ends, so swap-used percentage alone must never be a unilateral dispatch blocker.

Missing, malformed, non-finite, boolean-as-number, stale, or domain-invalid required signals fail admission closed.

## Ownership boundary

Unrelated workloads affect global resource measurements but are not Conductor workers. Never inspect deeply, steer, pause, kill, close, or count them as mission-owned resources. Respond only by admitting fewer or cheaper new mission workers.

## Capacity model

Do not derive a universal worker cap from RAM size alone. Use workload-aware weighted capacity (`budgets.maxWeightedSlots`) with approved classes such as `light`, `standard`, and `heavy`, each carrying `slotCost` and `minAvailableRamGb`. `budgets.maxWorkers` may remain as a separately validated emergency process ceiling; it is a circuit breaker, not a scheduling model and not proof of capacity.

Re-evaluate before every worker-consuming action, including worktree/workspace opening and dispatch. Under pressure, defer new dispatch while allowing evidence reconciliation, cleanup of mission-owned resources, and safe recovery to continue. Never auto-kill existing workers solely because new admission is deferred.

## Mandatory validation matrix

Before calling resource admission qualified, verify all of these:

1. High cumulative swap occupancy with healthy available RAM, zero/low PSI, and no active swap I/O does not block solely because of occupancy.
2. Low available RAM blocks even when swap occupancy is low.
3. Sustained memory PSI blocks according to the approved contract.
4. Active swap thrashing blocks according to the approved contract.
5. Missing, stale, malformed, boolean-as-number, NaN, infinity, and out-of-domain metrics block.
6. Concurrent unrelated workload changes global admission but is never treated as owned or managed.
7. Light and heavy workers consume different weighted capacity and reserves; exhausting weighted slots blocks even when process count is below `maxWorkers`.
8. Existing workers are not killed merely because new dispatch is deferred; cleanup/recovery still proceed.
9. A bounded multi-worker soak exercises real worker processes, dispatch, completion, cleanup, and recovery.
10. Live-host replay includes the current host snapshot and at least one previously observed problematic snapshot.

Record RED evidence for the failed behavior before implementation, GREEN evidence afterward, and full-suite regression results.

## Qualification language

A cleanup-only Herdr canary is not a resource-admission canary. Label each canary by the behavior it actually exercises.

Do not claim “high confidence,” “operationally qualified,” or “overnight ready” from synthetic unit scenarios alone. Qualification requires both:

- internal policy correctness (schema ranges, unknown-field rejection, fail-closed pressure/reserve rules); and
- empirical operational fitness under representative workloads and host states: **live-host replay**, **concurrent unrelated-load coverage**, and a **bounded real-worker soak**.

If either is absent, report the narrower verified claim and keep admission status unqualified.
