#!/usr/bin/env python3
"""Disposable Beads smoke test for the Conductor skill; mutates only a temp repo."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def run(*args: str, cwd: Path, capture: bool = True) -> str:
    result = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(args)}\n"
            f"stdout: {result.stdout or ''}\nstderr: {result.stderr or ''}"
        )
    return (result.stdout or "").strip()


def expect_failure(*args: str, cwd: Path) -> None:
    result = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode == 0:
        raise AssertionError(f"command unexpectedly passed: {' '.join(args)}\n{result.stdout}")


def ids(payload: Any) -> set[str]:
    if isinstance(payload, list):
        return {str(item["id"]) for item in payload if isinstance(item, dict) and "id" in item}
    if isinstance(payload, dict):
        for key in ("issues", "items", "data"):
            if isinstance(payload.get(key), list):
                return ids(payload[key])
        if "id" in payload:
            return {str(payload["id"])}
    return set()


def first_issue(payload: Any) -> dict[str, Any]:
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        return payload[0]
    if isinstance(payload, dict):
        if "id" in payload:
            return payload
        for key in ("issue", "data"):
            if isinstance(payload.get(key), dict):
                return payload[key]
    raise AssertionError(f"unrecognized issue payload: {payload!r}")


def main() -> int:
    if not shutil.which("bd"):
        raise SystemExit("SKIP: bd is not installed")

    with tempfile.TemporaryDirectory(prefix="conductor-skill-smoke-") as tmp:
        repo = Path(tmp)
        run("git", "init", "-q", cwd=repo)
        run("git", "config", "user.email", "conductor-smoke@example.invalid", cwd=repo)
        run("git", "config", "user.name", "Conductor Smoke", cwd=repo)
        (repo / "README.md").write_text("# disposable conductor smoke test\n")
        run("git", "add", "README.md", cwd=repo)
        run("git", "commit", "-qm", "initial", cwd=repo)
        candidate_sha = run("git", "rev-parse", "HEAD", cwd=repo)

        run("bd", "init", "--skip-agents", "--init-if-missing", "--non-interactive", cwd=repo)
        run("bd", "metrics", "off", cwd=repo)
        run("bd", "merge-slot", "create", cwd=repo)

        mission = run(
            "bd", "create", "Smoke mission", "--type", "epic", "--priority", "P1",
            "--labels", "conductor,mission,mission:smoke", "--acceptance", "Both child tasks close",
            "--silent", cwd=repo,
        )
        first = run(
            "bd", "create", "First unit", "--type", "task", "--priority", "P2",
            "--parent", mission, "--labels", "conductor,mission:smoke,risk:standard",
            "--acceptance", "Focused smoke evidence recorded", "--silent", cwd=repo,
        )
        second = run(
            "bd", "create", "Second unit", "--type", "task", "--priority", "P2",
            "--parent", mission, "--labels", "conductor,mission:smoke,risk:routine",
            "--acceptance", "Becomes ready after first closes", "--silent", cwd=repo,
        )

        run(
            "bd", "update", first,
            "--set-metadata", "risk_rationale=localized behavior",
            "--set-metadata", "escalation_triggers=shared contract discovered",
            cwd=repo,
        )
        run("bd", "dep", "add", second, first, cwd=repo)
        run("bd", "dep", "cycles", "--json", cwd=repo)

        ready_before = json.loads(run("bd", "ready", "--parent", mission, "--json", cwd=repo))
        assert first in ids(ready_before), ready_before
        assert second not in ids(ready_before), ready_before

        run(
            "bd", "--actor", "conductor/smoke-worker", "update", first, "--claim",
            "--set-metadata", "worker=conductor/smoke-worker",
            "--set-metadata", "worker_role=task",
            "--set-metadata", "base_sha=smoke-base",
            "--set-metadata", "claim_lease=2099-01-01T00:00:00Z",
            "--set-metadata", "last_heartbeat=2098-12-31T23:59:00Z",
            cwd=repo,
        )
        run(
            "bd", "update", first,
            "--set-metadata", f"candidate_sha={candidate_sha}",
            "--set-metadata", "tests=FAIL focused-smoke",
            "--set-metadata", "review_verdict=PASS",
            "--set-metadata", "reviewer=smoke-reviewer",
            "--set-metadata", f"merge_sha={candidate_sha}",
            "--set-metadata", "integration_tests=FAIL integrated-smoke",
            "--set-metadata", "push_parity=not_authorized",
            cwd=repo,
        )
        run("bd", "merge-slot", "acquire", "--holder", "conductor", "--json", cwd=repo)
        expect_failure(
            "python3", str(Path(__file__).with_name("check_close_evidence.py")),
            "--repo", str(repo), "--task", first, "--json", cwd=repo,
        )
        run(
            "bd", "update", first,
            "--set-metadata", "tests=PASS focused-smoke",
            "--set-metadata", "integration_tests=PASS integrated-smoke",
            cwd=repo,
        )
        run(
            "python3", str(Path(__file__).with_name("check_close_evidence.py")),
            "--repo", str(repo), "--task", first, "--json", cwd=repo,
        )
        run("bd", "close", first, "--reason", f"Integrated at {candidate_sha}; acceptance verified.", cwd=repo)
        run("bd", "merge-slot", "release", "--holder", "conductor", "--json", cwd=repo)

        ready_after = json.loads(run("bd", "ready", "--parent", mission, "--json", cwd=repo))
        assert second in ids(ready_after), ready_after

        issue = first_issue(json.loads(run("bd", "show", first, "--json", cwd=repo)))
        assert issue["status"] == "closed", issue
        metadata = issue.get("metadata") or {}
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        for key in ("worker", "candidate_sha", "review_verdict", "merge_sha", "integration_tests"):
            assert key in metadata, (key, metadata)

        print(json.dumps({
            "result": "PASS",
            "mission": mission,
            "first": first,
            "second": second,
            "readyPropagation": True,
            "metadataEvidence": True,
            "tempRepoRemovedOnExit": True,
        }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
