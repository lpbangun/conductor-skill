#!/usr/bin/env python3
"""Fail closed unless a Beads task has the evidence required before close."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PASS_VERDICTS = {"PASS", "PASS_WITH_NOTES"}


def first_issue(payload: Any) -> dict[str, Any]:
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        return payload[0]
    if isinstance(payload, dict):
        if "id" in payload:
            return payload
        for key in ("issue", "data"):
            if isinstance(payload.get(key), dict):
                return payload[key]
    raise ValueError("unrecognized bd show --json payload")


def metadata_of(issue: dict[str, Any]) -> dict[str, Any]:
    metadata = issue.get("metadata") or {}
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    if not isinstance(metadata, dict):
        raise ValueError("issue metadata is not an object")
    return metadata


def text_value(metadata: dict[str, Any], key: str) -> str:
    value = metadata.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing non-empty evidence metadata: {key}")
    return value.strip()


def require_pass(value: str, key: str) -> None:
    # Accept only an exact first token of PASS or PASS_WITH_NOTES; reject
    # lookalikes (PASSED, PASSABLE, PASSING, PASS-LIKE, ...) that merely begin
    # with the substring "PASS".
    first_token = value.split(None, 1)[0].upper() if value.split(None, 1) else ""
    if first_token not in PASS_VERDICTS:
        raise ValueError(f"{key}: evidence must begin with PASS or PASS_WITH_NOTES")


def require_git_commit(repo: Path, sha: str, key: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-e", f"{sha}^{{commit}}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode:
        raise ValueError(f"{key}: not a commit in the target repository")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--task", required=True)
    parser.add_argument("--require-push-parity", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    try:
        if not args.repo.is_dir():
            raise ValueError("repo must be an existing directory")
        result = subprocess.run(
            ["bd", "-C", str(args.repo), "show", args.task, "--json"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode:
            raise ValueError(f"bd show failed: {result.stderr.strip()}")
        issue = first_issue(json.loads(result.stdout))
        metadata = metadata_of(issue)
        labels = issue.get("labels") or []
        if not isinstance(labels, list):
            raise ValueError("issue labels are not an array")
        risk_labels = {label for label in labels if isinstance(label, str) and label.startswith("risk:")}
        if len(risk_labels) != 1:
            raise ValueError("task must have exactly one risk label")
        risk = next(iter(risk_labels)).split(":", 1)[1]
        if risk not in {"routine", "standard", "critical"}:
            raise ValueError(f"unknown risk label: risk:{risk}")

        required = ["candidate_sha", "tests", "merge_sha", "integration_tests", "push_parity"]
        evidence = {key: text_value(metadata, key) for key in required}
        require_pass(evidence["tests"], "tests")
        require_pass(evidence["integration_tests"], "integration_tests")
        require_git_commit(args.repo, evidence["candidate_sha"], "candidate_sha")
        require_git_commit(args.repo, evidence["merge_sha"], "merge_sha")
        verdict = metadata.get("review_verdict")
        reviewer = metadata.get("reviewer")
        if risk in {"standard", "critical"}:
            if verdict not in PASS_VERDICTS:
                raise ValueError("standard/critical task requires review_verdict PASS or PASS_WITH_NOTES")
            if not isinstance(reviewer, str) or not reviewer.strip():
                raise ValueError("standard/critical task requires reviewer evidence")
        if args.require_push_parity and evidence["push_parity"].lower() in {"not_authorized", "not_required", "n/a"}:
            raise ValueError("authorized push requires verified remote parity")
        if issue.get("status") not in {"in_progress", "blocked", "closed"}:
            raise ValueError(f"unexpected task status before close: {issue.get('status')!r}")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        payload = {"closable": False, "task": args.task, "error": str(exc)}
        print(json.dumps(payload, sort_keys=True) if args.json_output else f"NOT CLOSABLE: {exc}", file=sys.stderr)
        return 1

    payload = {
        "closable": True,
        "task": args.task,
        "risk": risk,
        "candidateSha": evidence["candidate_sha"],
        "mergeSha": evidence["merge_sha"],
        "reviewVerdict": verdict or "not_required_routine",
        "pushParity": evidence["push_parity"],
    }
    print(json.dumps(payload, sort_keys=True) if args.json_output else f"CLOSABLE: {args.task} ({risk})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
