#!/usr/bin/env python3
"""Deterministic speed-first dispatch planning for Conductor scheduling cycles.

The helper does not claim or launch work. It chooses the largest safe set of
productive, dependency-ready, ownership-disjoint lanes from a reconciled JSON
snapshot. Resource signals are fail-closed admission constraints, not the
optimization objective.
"""
from __future__ import annotations

import argparse
from collections import Counter
from itertools import combinations, combinations_with_replacement, product
import json
import math
from pathlib import Path
import sys
from typing import Any


_REQUIRED_RESOURCES = (
    "availableRamGb",
    "memoryPsiFullAvg10",
    "swapOutMiBPerSecond",
    "sampleAgeSeconds",
)
_REQUIRED_BUDGETS = (
    "maxWorkers",
    "maxWeightedSlots",
    "minAvailableRamGb",
    "maxMemoryPsiFullAvg10",
    "maxSwapOutMiBPerSecond",
    "resourceSampleSeconds",
)


def _real_number(value: Any, *, minimum: float = 0.0) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and float(value) >= minimum
    )


def _valid_resources(resources: dict[str, Any], budgets: dict[str, Any]) -> bool:
    if not all(key in resources for key in _REQUIRED_RESOURCES):
        return False
    if not all(key in budgets for key in _REQUIRED_BUDGETS):
        return False
    if not all(_real_number(resources[key]) for key in _REQUIRED_RESOURCES):
        return False
    if not all(_real_number(budgets[key]) for key in _REQUIRED_BUDGETS):
        return False
    max_workers = budgets["maxWorkers"]
    return isinstance(max_workers, int) and not isinstance(max_workers, bool) and 1 <= max_workers <= 6


def _pressure_safe(resources: dict[str, Any], budgets: dict[str, Any]) -> bool:
    return (
        resources["availableRamGb"] > budgets["minAvailableRamGb"]
        and resources["memoryPsiFullAvg10"] < budgets["maxMemoryPsiFullAvg10"]
        and resources["swapOutMiBPerSecond"] < budgets["maxSwapOutMiBPerSecond"]
        and resources["sampleAgeSeconds"] <= budgets["resourceSampleSeconds"]
    )


def _task_valid(task: dict[str, Any]) -> bool:
    conflicts = task.get("conflictsWith", [])
    return (
        isinstance(task.get("id"), str)
        and bool(task["id"].strip())
        and isinstance(task.get("priority"), int)
        and not isinstance(task.get("priority"), bool)
        and 0 <= task["priority"] <= 4
        and isinstance(task.get("productive"), bool)
        and _real_number(task.get("slotCost"), minimum=0.000001)
        and _real_number(task.get("ramReserveGb"))
        and isinstance(task.get("ownershipKeys"), list)
        and bool(task["ownershipKeys"])
        and all(isinstance(item, str) and item for item in task["ownershipKeys"])
        and isinstance(conflicts, list)
        and all(isinstance(item, str) and item for item in conflicts)
    )


def _conflicts(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_id = left.get("id")
    right_id = right.get("id")
    if left_id == right_id:
        return True
    if right_id in left.get("conflictsWith", []) or left_id in right.get("conflictsWith", []):
        return True
    return bool(set(left.get("ownershipKeys", [])) & set(right.get("ownershipKeys", [])))


def _set_is_disjoint(tasks: tuple[dict[str, Any], ...], active: list[dict[str, Any]]) -> bool:
    for task in tasks:
        if any(_conflicts(task, running) for running in active):
            return False
    return all(not _conflicts(a, b) for a, b in combinations(tasks, 2))


def _priority(task: dict[str, Any]) -> int:
    value = task.get("priority", 2)
    return value if isinstance(value, int) and not isinstance(value, bool) else 2


def _underfill_reason(
    productive_ready: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    active: list[dict[str, Any]],
    productive_active: list[dict[str, Any]],
    resources: dict[str, Any],
    budgets: dict[str, Any],
) -> str:
    productive_after = len(productive_active) + len(selected)
    if productive_after >= min(2, budgets["maxWorkers"]):
        return ""
    if len(productive_ready) + len(productive_active) < 2:
        return "no_second_productive_dependency_ready_lane"
    if budgets["maxWorkers"] - len(active) < max(1, 2 - len(productive_active)):
        return "process_ceiling_blocks_second_lane"
    candidates = productive_active + productive_ready
    if any(_conflicts(a, b) for a, b in combinations(candidates, 2)):
        nonconflicting_pair_exists = any(
            not _conflicts(a, b) for a, b in combinations(candidates, 2)
        )
        if not nonconflicting_pair_exists:
            return "ownership_conflict_blocks_second_lane"
    needed_productive = max(0, 2 - len(productive_active))
    smallest_reserves = sorted(float(item["ramReserveGb"]) for item in productive_ready)
    if len(smallest_reserves) >= needed_productive:
        needed_reserve = sum(smallest_reserves[:needed_productive])
        if needed_reserve + float(budgets["minAvailableRamGb"]) >= resources["availableRamGb"]:
            return "ram_reserve_blocks_second_lane"
    active_slots = sum(float(item["slotCost"]) for item in active)
    smallest_ready = sorted(float(item["slotCost"]) for item in productive_ready)
    if len(smallest_ready) >= needed_productive:
        needed = sum(smallest_ready[:needed_productive])
        if active_slots + needed > budgets["maxWeightedSlots"]:
            return "weighted_capacity_blocks_second_lane"
    return "no_feasible_second_lane"


def plan_dispatch(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return a deterministic dispatch plan from a fully reconciled snapshot."""
    ready = snapshot.get("ready", [])
    active_raw = snapshot.get("active", [])
    resources = snapshot.get("resources", {})
    budget = snapshot.get("budgets", {})
    control_actions = list(snapshot.get("pendingControlActions", []))

    result: dict[str, Any] = {
        "schemaVersion": 1,
        "objective": "maximize_useful_throughput",
        "selectedTaskIds": [],
        "productiveWorkersAfter": 0,
        "underfilled": True,
        "underfillReason": "",
        "dispatchBlockedReason": "",
        "controlActions": control_actions,
    }

    if not isinstance(ready, list) or not isinstance(active_raw, list):
        result["dispatchBlockedReason"] = "invalid_scheduler_snapshot"
        return result
    if not isinstance(resources, dict) or not isinstance(budget, dict) or not _valid_resources(resources, budget):
        result["dispatchBlockedReason"] = "invalid_or_stale_resource_evidence"
        return result

    if any(
        not isinstance(item, dict)
        or not _task_valid(item)
        or not isinstance(item.get("live"), bool)
        for item in active_raw
    ):
        result["dispatchBlockedReason"] = "invalid_active_worker_evidence"
        return result
    active = [item for item in active_raw if item["live"] is True]
    productive_active = [item for item in active if item["productive"] is True]
    result["productiveWorkersAfter"] = len(productive_active)

    if not _pressure_safe(resources, budget):
        result["dispatchBlockedReason"] = "resource_pressure"
        result["underfillReason"] = "resource_pressure_blocks_new_lane"
        return result

    invalid_ready = [item.get("id") for item in ready if not isinstance(item, dict) or not _task_valid(item)]
    if invalid_ready:
        result["dispatchBlockedReason"] = "invalid_ready_task_evidence"
        result["invalidTaskIds"] = invalid_ready
        return result

    ready_ids = [item["id"] for item in ready]
    active_ids = [item["id"] for item in active]
    if len(set(ready_ids)) != len(ready_ids) or len(set(active_ids)) != len(active_ids) or set(ready_ids) & set(active_ids):
        result["dispatchBlockedReason"] = "duplicate_task_identity"
        return result

    productive_ready = [item for item in ready if item.get("productive") is True]
    process_headroom = max(0, budget["maxWorkers"] - len(active))
    active_slots = sum(float(item["slotCost"]) for item in active)
    slot_headroom = float(budget["maxWeightedSlots"]) - active_slots
    ordered = sorted(productive_ready, key=lambda item: (_priority(item), item["id"]))

    selected: list[dict[str, Any]] = []
    max_count = min(process_headroom, len(ordered))
    if ordered and slot_headroom >= 0:
        min_slot_cost = min(float(item["slotCost"]) for item in ordered)
        max_count = min(max_count, int(slot_headroom // min_slot_cost))

    by_priority = {
        priority: [item for item in ordered if _priority(item) == priority]
        for priority in range(5)
    }
    # Search cardinality first. Within a cardinality, enumerate the complete
    # nondecreasing priority vector lexicographically (P0 before P1, etc.),
    # then ID combinations lexicographically. This preserves every earlier
    # urgency position: P0+P0 beats P0+P1, while P0+P4 beats P1+P1.
    for count in range(max_count, 0, -1):
        for priority_vector in combinations_with_replacement(range(5), count):
            required = Counter(priority_vector)
            if any(required[p] > len(by_priority[p]) for p in required):
                continue
            per_priority_choices = [
                combinations(by_priority[p], required[p])
                for p in sorted(required)
            ]
            for grouped_choices in product(*per_priority_choices):
                group = tuple(item for choices in grouped_choices for item in choices)
                if sum(float(item["slotCost"]) for item in group) > slot_headroom:
                    continue
                new_reserve = sum(float(item["ramReserveGb"]) for item in group)
                if new_reserve + float(budget["minAvailableRamGb"]) >= resources["availableRamGb"]:
                    continue
                if not _set_is_disjoint(group, active):
                    continue
                selected = list(group)
                break
            if selected:
                break
        if selected:
            break

    result["selectedTaskIds"] = [item["id"] for item in selected]
    result["productiveWorkersAfter"] = len(productive_active) + len(selected)
    target = min(2, budget["maxWorkers"])
    result["underfilled"] = result["productiveWorkersAfter"] < target
    if result["underfilled"]:
        result["underfillReason"] = _underfill_reason(
            productive_ready,
            selected,
            active,
            productive_active,
            resources,
            budget,
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", nargs="?", help="JSON file; omit to read stdin")
    args = parser.parse_args()
    try:
        text = Path(args.snapshot).read_text() if args.snapshot else sys.stdin.read()
        snapshot = json.loads(text)
        if not isinstance(snapshot, dict):
            raise ValueError("snapshot must be a JSON object")
        plan = plan_dispatch(snapshot)
        print(json.dumps(plan, sort_keys=True))
        return 3 if plan["dispatchBlockedReason"] else 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc), "schemaVersion": 1}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
