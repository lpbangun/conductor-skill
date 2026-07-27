#!/usr/bin/env python3
"""Fail-closed, file-backed Conductor worker dispatcher.

This utility launches one explicit Hermes provider/model route, attaches the packaged
completion watcher to a stable Python waiter, and prints a JSON dispatch record. It
never mutates Beads, Git, or mission state; the controller persists the record only
after it verifies the claimed lane and ownership boundaries.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import time
from typing import Any

HERE = Path(__file__).resolve().parent
WATCHER = HERE / "watch_worker_completion.py"
TASK_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
PANE_RE = re.compile(r"^w[A-Za-z0-9]+:p[A-Za-z0-9]+$")
SESSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")


def die(message: str) -> None:
    raise ValueError(message)


def absolute_file(value: str, *, must_exist: bool = False) -> Path:
    path = Path(value)
    if not path.is_absolute():
        die(f"path must be absolute: {value}")
    if must_exist and not path.is_file():
        die(f"required file does not exist: {path}")
    return path.resolve()


def start_ticks(pid: int) -> int | None:
    try:
        text = Path(f"/proc/{pid}/stat").read_text()
        close = text.rfind(")")
        return int(text[close + 1:].split()[19]) if close >= 0 else None
    except (OSError, ValueError, IndexError):
        return None


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(content)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", required=True)
    p.add_argument("--worktree", required=True)
    p.add_argument("--task-id", required=True)
    p.add_argument("--role", required=True)
    p.add_argument("--provider", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--brief-file", required=True)
    p.add_argument("--base-sha", required=True)
    p.add_argument("--conductor-pane", required=True)
    p.add_argument("--conductor-session", required=True)
    p.add_argument("--result-json", required=True)
    p.add_argument("--receipt", required=True)
    p.add_argument("--dispatch-dir", required=True)
    p.add_argument("--hermes-bin", default="hermes")
    p.add_argument("--herdr-bin", default="herdr")
    p.add_argument("--watcher-script", default=str(WATCHER))
    p.add_argument("--timeout-seconds", type=float, default=7200.0)
    p.add_argument("--toolsets", default="terminal,file")
    return p.parse_args()


def validate(args: argparse.Namespace) -> tuple[Path, Path, Path, Path, Path, Path, Path]:
    if not TASK_RE.fullmatch(args.task_id): die("invalid task ID")
    if not args.role.strip() or not args.provider.strip() or not args.model.strip(): die("role/provider/model are required")
    if not PANE_RE.fullmatch(args.conductor_pane): die("invalid conductor pane")
    if not SESSION_RE.fullmatch(args.conductor_session): die("invalid conductor session")
    if not args.base_sha or any(char.isspace() for char in args.base_sha): die("invalid base SHA")
    if args.timeout_seconds <= 0: die("timeout must be positive")
    repo = absolute_file(args.repo) if Path(args.repo).is_file() else Path(args.repo).resolve()
    worktree = Path(args.worktree).resolve()
    if not repo.is_dir() or not worktree.is_dir(): die("repo and worktree must be existing directories")
    brief = absolute_file(args.brief_file, must_exist=True)
    result = absolute_file(args.result_json)
    receipt = absolute_file(args.receipt)
    dispatch_dir = absolute_file(args.dispatch_dir)
    watcher = absolute_file(args.watcher_script, must_exist=True)
    if os.path.lexists(result) or os.path.lexists(receipt): die("result or receipt path already exists")
    return repo, worktree, brief, result, receipt, dispatch_dir, watcher


def launcher_source(query_path: Path, log_path: Path, command: list[str]) -> str:
    return """import subprocess, sys\nfrom pathlib import Path\ncmd = %r\nlog_path = Path(%r)\nlog_path.parent.mkdir(parents=True, exist_ok=True)\nwith log_path.open('w', buffering=1) as log:\n    child = subprocess.Popen(cmd, cwd=%r, stdout=log, stderr=subprocess.STDOUT, text=True, start_new_session=True)\n    sys.exit(child.wait())\n""" % (command, str(log_path), str(query_path.parent))


def main() -> int:
    try:
        args = parse_args()
        repo, worktree, brief, result, receipt, dispatch_dir, watcher = validate(args)
        dispatch_dir.mkdir(parents=True, exist_ok=True)
        token = secrets.token_hex(16)
        attempt = f"{args.task_id}-{token}"
        query_path = dispatch_dir / f"{attempt}.query.txt"
        launcher_path = dispatch_dir / f"{attempt}.launcher.py"
        log_path = dispatch_dir / f"{attempt}.worker.log"
        raw_brief = brief.read_text()
        query = raw_brief.replace("{{COMPLETION_TOKEN}}", token).replace("{{RESULT_JSON}}", str(result))
        if "{{COMPLETION_TOKEN}}" in query or "{{RESULT_JSON}}" in query:
            die("brief placeholder replacement failed")
        atomic_write(query_path, query)
        command = [args.hermes_bin, "chat", "-q", query, "-Q", "-m", args.model, "--provider", args.provider, "-t", args.toolsets, "--yolo"]
        atomic_write(launcher_path, launcher_source(worktree / ".", log_path, command).replace(repr(str(query_path.parent)), repr(str(worktree))))
        launcher = subprocess.Popen(
            [sys.executable, str(launcher_path)],
            cwd=worktree,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.08)
        ticks = start_ticks(launcher.pid)
        if launcher.poll() is not None or ticks is None:
            raise RuntimeError("launcher failed before watcher attachment")
        watcher_cmd = [sys.executable, str(watcher), "--worker-pid", str(launcher.pid), "--worker-start-ticks", str(ticks), "--task-id", args.task_id, "--result-json", str(result), "--marker-key", "completionMarker", "--marker-value", token, "--conductor-pane", args.conductor_pane, "--conductor-session", args.conductor_session, "--receipt", str(receipt), "--herdr-bin", args.herdr_bin, "--timeout-seconds", str(args.timeout_seconds)]
        watcher_proc = subprocess.Popen(
            watcher_cmd,
            cwd=worktree,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.08)
        watcher_ticks = start_ticks(watcher_proc.pid)
        if watcher_proc.poll() is not None or watcher_ticks is None:
            raise RuntimeError("watcher failed before qualification")
        record: dict[str, Any] = {"schemaVersion": 1, "taskId": args.task_id, "role": args.role, "requestedProvider": args.provider, "requestedModel": args.model, "worktree": str(worktree), "repo": str(repo), "baseSha": args.base_sha, "completionToken": token, "resultJson": str(result), "receipt": str(receipt), "launcherPid": launcher.pid, "launcherStartTicks": ticks, "watcherPid": watcher_proc.pid, "watcherStartTicks": watcher_ticks, "conductorPane": args.conductor_pane, "conductorSession": args.conductor_session, "beadsMetadata": {"process_pid": launcher.pid, "process_start_ticks": ticks, "watcher_pid": watcher_proc.pid, "watcher_start_ticks": watcher_ticks, "completion_token": token, "result_json": str(result), "watcher_receipt": str(receipt), "conductor_pane": args.conductor_pane, "conductor_session": args.conductor_session, "requested_provider": args.provider, "requested_model": args.model}}
        print(json.dumps(record, sort_keys=True))
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(json.dumps({"error": str(exc), "schemaVersion": 1}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
