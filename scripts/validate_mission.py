#!/usr/bin/env python3
"""Validate a Conductor mission contract using only the Python standard library."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

STATUSES = {"proposed", "approved", "active", "waiting_user", "paused", "complete", "aborted"}
SUPERVISION = {"interactive", "checkpointed", "delegated"}
PUBLISH_EVENTS = {
    "mission_start", "task_claim", "task_blocked", "test_verdict",
    "review_verdict", "integration", "recovery", "waiting_user",
    "mission_pause", "mission_complete",
}
BUDGET_RANGES = {
    "maxWorkers": (1, 6),
    "maxWeightedSlots": (0.5, 24),
    "minAvailableRamGb": (1, 64),
    "resourceSampleSeconds": (5, 60),
    "maxMemoryPsiFullAvg10": (0.1, 100),
    "maxSwapOutMiBPerSecond": (0.1, 4096),
    "staleAfterMinutes": (5, 240),
    "maxRetriesPerTask": (0, 5),
    "maxCorrectionCycles": (0, 5),
    "maxFullSuites": (0, 5),
}
INTEGER_BUDGETS = {
    "maxWorkers", "resourceSampleSeconds", "staleAfterMinutes",
    "maxRetriesPerTask", "maxCorrectionCycles", "maxFullSuites",
}
REQUIRED_WORKLOAD_CLASSES = ("light", "standard", "heavy")
WORKLOAD_CLASS_FIELDS = {
    "slotCost": (0.1, 6),
    "minAvailableRamGb": (0.5, 64),
}
PLACEHOLDER = re.compile(r"(?i)(^\s*replace\s*:|^\s*(todo|tbd)\s*$|/absolute/path|example command)")


def need(obj: dict[str, Any], key: str, where: str) -> Any:
    if key not in obj:
        raise ValueError(f"{where}.{key}: missing")
    return obj[key]


def nonempty_string(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{where}: must be a non-empty string")
    return value


def string_list(value: Any, where: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        qualifier = "a" if allow_empty else "a non-empty"
        raise ValueError(f"{where}: must be {qualifier} string array")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{where}: every item must be a non-empty string")
    return value


def object_value(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{where}: must be an object")
    return value


def numeric_in_range(value: Any, where: str, low: float, high: float, *, integer: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{where}: must be numeric")
    if integer and not isinstance(value, int):
        raise ValueError(f"{where}: must be an integer")
    if not low <= value <= high:
        raise ValueError(f"{where}: expected {low}..{high}")
    return value


def validate_workload_classes(classes: Any) -> None:
    classes = object_value(classes, "budgets.workloadClasses")
    missing = [name for name in REQUIRED_WORKLOAD_CLASSES if name not in classes]
    if missing:
        raise ValueError(f"budgets.workloadClasses: missing required class(es): {missing}")
    for name, profile in classes.items():
        where = f"budgets.workloadClasses.{name}"
        profile = object_value(profile, where)
        unknown = set(profile) - set(WORKLOAD_CLASS_FIELDS)
        if unknown:
            raise ValueError(f"{where}: unknown field(s): {sorted(unknown)}")
        for field, (low, high) in WORKLOAD_CLASS_FIELDS.items():
            numeric_in_range(need(profile, field, where), f"{where}.{field}", low, high)


def validate(doc: dict[str, Any], *, require_approved: bool, require_active: bool) -> None:
    if require_approved and require_active:
        raise ValueError("choose only one of --require-approved or --require-active")
    if doc.get("schemaVersion") != 1:
        raise ValueError("schemaVersion: expected 1")

    mission = object_value(need(doc, "mission", "root"), "mission")
    for key in ("name", "objective", "integrationBranch", "milestone"):
        nonempty_string(need(mission, key, "mission"), f"mission.{key}")
    repo = nonempty_string(need(mission, "repo", "mission"), "mission.repo")
    if not os.path.isabs(repo):
        raise ValueError("mission.repo: must be an absolute path")
    status = need(mission, "status", "mission")
    if status not in STATUSES:
        raise ValueError(f"mission.status: expected one of {sorted(STATUSES)}")
    supervision = need(mission, "supervisionMode", "mission")
    if supervision not in SUPERVISION:
        raise ValueError(f"mission.supervisionMode: expected one of {sorted(SUPERVISION)}")
    for key in ("inScope", "outOfScope", "acceptance"):
        string_list(need(mission, key, "mission"), f"mission.{key}")

    authority = object_value(need(doc, "authority", "root"), "authority")
    for key in (
        "localIntegrationAuthorized", "pushAuthorized", "destructiveOpsAuthorized",
        "releaseAuthorized", "deployAuthorized", "cleanupAuthorized",
    ):
        if not isinstance(need(authority, key, "authority"), bool):
            raise ValueError(f"authority.{key}: must be boolean")
    nonempty_string(need(authority, "integrationOwner", "authority"), "authority.integrationOwner")
    push_target = need(authority, "authorizedPushTarget", "authority")
    if not isinstance(push_target, str):
        raise ValueError("authority.authorizedPushTarget: must be a string")
    if authority["pushAuthorized"] and not push_target.strip():
        raise ValueError("authority.authorizedPushTarget: required when pushAuthorized is true")
    # Release / deploy / cleanup authority: strict booleans with exact targets when authorized.
    release_target = need(authority, "releaseTarget", "authority")
    if not isinstance(release_target, str):
        raise ValueError("authority.releaseTarget: must be a string")
    if authority["releaseAuthorized"] and not release_target.strip():
        raise ValueError("authority.releaseTarget: required when releaseAuthorized is true")
    deploy_target = need(authority, "deployTarget", "authority")
    if not isinstance(deploy_target, str):
        raise ValueError("authority.deployTarget: must be a string")
    if authority["deployAuthorized"] and not deploy_target.strip():
        raise ValueError("authority.deployTarget: required when deployAuthorized is true")
    cleanup_targets = need(authority, "cleanupTargets", "authority")
    if not isinstance(cleanup_targets, list):
        raise ValueError("authority.cleanupTargets: must be a string array")
    if any(not isinstance(item, str) or not item.strip() for item in cleanup_targets):
        raise ValueError("authority.cleanupTargets: every item must be a non-empty string")
    if authority["cleanupAuthorized"] and not cleanup_targets:
        raise ValueError("authority.cleanupTargets: required when cleanupAuthorized is true")

    budgets = object_value(need(doc, "budgets", "root"), "budgets")
    allowed_budget_keys = set(BUDGET_RANGES) | {"workloadClasses"}
    unknown = set(budgets) - allowed_budget_keys
    if unknown:
        raise ValueError(f"budgets: unknown field(s): {sorted(unknown)}")
    for key, (low, high) in BUDGET_RANGES.items():
        value = need(budgets, key, "budgets")
        numeric_in_range(
            value,
            f"budgets.{key}",
            low,
            high,
            integer=key in INTEGER_BUDGETS,
        )
    validate_workload_classes(need(budgets, "workloadClasses", "budgets"))

    gates = object_value(need(doc, "gates", "root"), "gates")
    string_list(need(gates, "focusedTests", "gates"), "gates.focusedTests")
    string_list(need(gates, "broadTests", "gates"), "gates.broadTests")
    for key in ("build", "lint"):
        string_list(need(gates, key, "gates"), f"gates.{key}", allow_empty=True)

    ledger = object_value(need(doc, "ledger", "root"), "ledger")
    mission_id = need(ledger, "missionId", "ledger")
    if not isinstance(mission_id, str):
        raise ValueError("ledger.missionId: must be a string")
    nonempty_string(need(ledger, "actorPrefix", "ledger"), "ledger.actorPrefix")

    dashboard = object_value(need(doc, "dashboard", "root"), "dashboard")
    if not isinstance(need(dashboard, "enabled", "dashboard"), bool):
        raise ValueError("dashboard.enabled: must be boolean")
    dashboard_path = nonempty_string(need(dashboard, "path", "dashboard"), "dashboard.path")
    if dashboard["enabled"] and not os.path.isabs(dashboard_path):
        raise ValueError("dashboard.path: must be absolute when enabled")
    events = string_list(need(dashboard, "publishOn", "dashboard"), "dashboard.publishOn", allow_empty=True)
    unknown = set(events) - PUBLISH_EVENTS
    if unknown:
        raise ValueError(f"dashboard.publishOn: unknown events {sorted(unknown)}")

    approved_or_later = status in {"approved", "active", "waiting_user", "paused", "complete"}
    active_or_later = status in {"active", "waiting_user", "paused", "complete"}
    if require_approved or require_active or approved_or_later:
        nonempty_string(need(authority, "approvedBy", "authority"), "authority.approvedBy")
        nonempty_string(need(authority, "approvedAt", "authority"), "authority.approvedAt")
    if require_active or active_or_later:
        nonempty_string(mission_id, "ledger.missionId")

    if require_approved or require_active:
        if not Path(repo).is_dir():
            raise ValueError("mission.repo: approved mission requires an existing directory")
        mission_text = [mission[key] for key in ("name", "objective", "milestone")]
        mission_text.extend(mission["inScope"] + mission["outOfScope"] + mission["acceptance"])
        for value in mission_text:
            if PLACEHOLDER.search(value):
                raise ValueError(f"mission: approved contract contains placeholder text: {value!r}")
        for gate_name in ("focusedTests", "broadTests"):
            for command in gates[gate_name]:
                if PLACEHOLDER.search(command):
                    raise ValueError(f"gates.{gate_name}: placeholder command is not executable: {command!r}")
        for auth_key, target_key in (
            ("pushAuthorized", "authorizedPushTarget"),
            ("releaseAuthorized", "releaseTarget"),
            ("deployAuthorized", "deployTarget"),
        ):
            if authority[auth_key] and PLACEHOLDER.search(authority[target_key]):
                raise ValueError(f"authority.{target_key}: authorized target contains placeholder text: {authority[target_key]!r}")
        if authority["cleanupAuthorized"]:
            for target in authority["cleanupTargets"]:
                if PLACEHOLDER.search(target):
                    raise ValueError(f"authority.cleanupTargets: authorized target contains placeholder text: {target!r}")
        if dashboard["enabled"] and not Path(dashboard_path).is_dir():
            raise ValueError("dashboard.path: enabled approved mission requires an existing directory")

    if require_approved and not approved_or_later:
        raise ValueError("mission.status: approval gate requires approved or later non-aborted status")
    if require_active and not active_or_later:
        raise ValueError("mission.status: active gate requires active, waiting_user, paused, or complete")
    if require_active and PLACEHOLDER.search(mission_id):
        raise ValueError("ledger.missionId: active contract contains a placeholder")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--require-approved", action="store_true")
    mode.add_argument("--require-active", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    try:
        doc = json.loads(args.contract.read_text())
        if not isinstance(doc, dict):
            raise ValueError("root: must be an object")
        validate(doc, require_approved=args.require_approved, require_active=args.require_active)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        if args.json_output:
            print(json.dumps({"valid": False, "error": str(exc)}))
        else:
            print(f"INVALID: {exc}", file=sys.stderr)
        return 1

    result = {
        "valid": True,
        "status": doc["mission"]["status"],
        "mission": doc["mission"]["name"],
        "repo": doc["mission"]["repo"],
        "maxWorkers": doc["budgets"]["maxWorkers"],
        "maxWeightedSlots": doc["budgets"]["maxWeightedSlots"],
        "pushAuthorized": doc["authority"]["pushAuthorized"],
    }
    print(json.dumps(result, sort_keys=True) if args.json_output else f"VALID: {result['mission']} ({result['status']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
