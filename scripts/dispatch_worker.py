#!/usr/bin/env python3
"""Fail-closed, file-backed Conductor worker dispatcher.

This utility launches one explicit worker route, attaches the packaged completion
watcher, and prints a JSON dispatch record. It never mutates Beads, Git, or mission
state; the controller persists the record only after it verifies the claimed lane and
ownership boundaries.

Harnesses:
  hermes  headless `hermes chat` waiter (PID-grade completion: the launcher exits).
  omp     visible OMP TUI in a worker pane (pane-aware completion: the watcher is
  droid   bound with --worker-pane because persistent TUIs never exit at task end;
          the worker-created result artifact or an idle-without-artifact wake is the
          completion signal).

For TUI harnesses the dispatch is verified before qualification: the brief is injected
into the pane and the agent must prove live within the verification window (Herdr
agent_status working, or the harness process proven in the proc root). A pane creation
alone is never a dispatch.
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
TUI_HARNESSES = ("omp", "droid")
HARNESS_DEFAULT_BINS = {
    "omp": str(Path.home() / ".bun" / "bin" / "omp"),
    "droid": str(Path.home() / ".local" / "bin" / "droid"),
}
TUI_WORKING_STATES = {"working", "busy", "running", "processing"}
HERDR_TIMEOUT_SECONDS = 15


def die(message: str) -> None:
    raise ValueError(message)


def absolute_file(value: str, *, must_exist: bool = False) -> Path:
    path = Path(value)
    if not path.is_absolute():
        die(f"path must be absolute: {value}")
    if must_exist and not path.is_file():
        die(f"required file does not exist: {value}")
    return path.resolve()


def start_ticks(pid: int, proc_root: Path = Path("/proc")) -> int | None:
    try:
        text = (proc_root / str(pid) / "stat").read_text()
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


def run_herdr(herdr_bin: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [herdr_bin, *args], text=True, capture_output=True, timeout=HERDR_TIMEOUT_SECONDS, check=False
    )


def pane_snapshot(herdr_bin: str, pane: str) -> dict[str, Any]:
    cp = run_herdr(herdr_bin, ["pane", "get", pane])
    if cp.returncode != 0:
        die(f"worker pane unavailable: {cp.stderr.strip() or cp.stdout.strip()}")
    try:
        data = json.loads(cp.stdout)
    except json.JSONDecodeError as exc:
        die(f"herdr pane get returned invalid JSON: {exc}")
    pane_data = data.get("result", {}).get("pane", {}) if isinstance(data, dict) else {}
    return pane_data if isinstance(pane_data, dict) else {}


def scan_worker_pid_once(
    proc_root: Path, worktree: Path, harness_bin: str
) -> tuple[int, int] | None:
    """Find exactly one harness process whose cwd is the worktree.

    Returns None when none exists yet; fails closed when the identity is
    ambiguous. Only an argv token exactly equal to the harness binary
    path counts, so preserved helper children of the same harness do not
    create false matches.
    """
    matches: list[int] = []
    try:
        entries = list(proc_root.iterdir())
    except OSError as exc:
        die(f"cannot inspect proc root: {exc}")
    for entry in entries:
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        try:
            cwd = os.readlink(entry / "cwd")
            raw = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        if Path(cwd) != worktree:
            continue
        parts = [part.decode(errors="replace") for part in raw.split(b"\0") if part]
        if harness_bin in parts:
            matches.append(pid)
    if not matches:
        return None
    if len(matches) > 1:
        die(f"ambiguous TUI worker processes in {worktree}: {sorted(matches)}")
    ticks = start_ticks(matches[0], proc_root)
    if ticks is None:
        return None
    return matches[0], ticks


def verify_tui_launch(
    args: argparse.Namespace, worktree: Path, harness_bin: str
) -> tuple[int, int]:
    """After brief injection, prove the TUI agent is live.

    Either Herdr reports a working agent_status or the exact harness
    process is proven in the proc root (the skill's verified-launch
    rule). Fails closed when neither appears inside the window.
    """
    deadline = time.monotonic() + args.launch_verify_seconds
    while time.monotonic() < deadline:
        snapshot = pane_snapshot(args.herdr_bin, args.worker_pane)
        status = snapshot.get("agent_status")
        if isinstance(status, str) and status.lower() in TUI_WORKING_STATES:
            found = scan_worker_pid_once(Path(args.proc_root), worktree, harness_bin)
            if found is not None:
                return found
            # Working status but PID not yet observable: keep sampling.
        else:
            found = scan_worker_pid_once(Path(args.proc_root), worktree, harness_bin)
            if found is not None:
                return found
        time.sleep(0.5)
    die(
        "TUI launch not verified within "
        f"{args.launch_verify_seconds:g}s: no working agent_status and no harness "
        f"process in {worktree} — inspect the pane; the dispatch FAILED"
    )
    raise AssertionError("unreachable")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", required=True)
    p.add_argument("--worktree", required=True)
    p.add_argument("--task-id", required=True)
    p.add_argument("--role", required=True)
    p.add_argument("--provider", default="")
    p.add_argument("--model", default="")
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
    p.add_argument("--harness", choices=("hermes", *TUI_HARNESSES), default="hermes")
    p.add_argument(
        "--worker-pane",
        default="",
        help="Required for omp/droid: the visible pane the TUI runs in.",
    )
    p.add_argument("--harness-bin", default="", help="Override the TUI binary path.")
    p.add_argument("--launch-verify-seconds", type=float, default=30.0)
    p.add_argument(
        "--idle-after-seconds",
        type=float,
        default=600.0,
        help="TUI only: watcher idle-without-artifact threshold.",
    )
    p.add_argument("--proc-root", default="/proc", help=argparse.SUPPRESS)
    return p.parse_args()


def validate(args: argparse.Namespace) -> tuple[Path, Path, Path, Path, Path, Path, Path]:
    if not TASK_RE.fullmatch(args.task_id): die("invalid task ID")
    if not args.role.strip(): die("role is required")
    if not PANE_RE.fullmatch(args.conductor_pane): die("invalid conductor pane")
    if not SESSION_RE.fullmatch(args.conductor_session): die("invalid conductor session")
    if not args.base_sha or any(char.isspace() for char in args.base_sha): die("invalid base SHA")
    if args.timeout_seconds <= 0: die("timeout must be positive")
    if args.launch_verify_seconds <= 0: die("launch verify window must be positive")
    if args.harness == "hermes":
        if not args.provider.strip() or not args.model.strip():
            die("provider and model are required for the hermes harness")
        if args.worker_pane:
            die("the hermes harness is headless and takes no worker pane")
    else:
        if not args.worker_pane or not PANE_RE.fullmatch(args.worker_pane):
            die("a valid --worker-pane is required for TUI harnesses")
        if not args.harness_bin:
            args.harness_bin = HARNESS_DEFAULT_BINS[args.harness]
        if not Path(args.harness_bin).is_absolute():
            die("harness binary path must be absolute")
    repo = absolute_file(args.repo) if Path(args.repo).is_file() else Path(args.repo).resolve()
    worktree = Path(args.worktree).resolve()
    if not repo.is_dir() or not worktree.is_dir(): die("repo and worktree must be existing directories")
    brief = absolute_file(args.brief_file, must_exist=True)
    result = absolute_file(args.result_json)
    receipt = absolute_file(args.receipt)
    dispatch_dir = absolute_file(args.dispatch_dir)
    watcher = absolute_file(args.watcher_script, must_exist=True)
    if os.path.lexists(result) or os.path.lexists(receipt): die("result or receipt path already exists")
    if not Path(args.proc_root).is_dir(): die("proc root must be an existing directory")
    return repo, worktree, brief, result, receipt, dispatch_dir, watcher


def launcher_source(query_path: Path, log_path: Path, command: list[str]) -> str:
    return """import subprocess, sys\nfrom pathlib import Path\ncmd = %r\nlog_path = Path(%r)\nlog_path.parent.mkdir(parents=True, exist_ok=True)\nwith log_path.open('w', buffering=1) as log:\n    child = subprocess.Popen(cmd, cwd=%r, stdout=log, stderr=subprocess.STDOUT, text=True, start_new_session=True)\n    sys.exit(child.wait())\n""" % (command, str(log_path), str(query_path.parent))


def build_record(
    args: argparse.Namespace,
    repo: Path,
    worktree: Path,
    token: str,
    result: Path,
    receipt: Path,
    worker_pid: int,
    worker_ticks: int,
    watcher_pid: int,
    watcher_ticks: int,
    provider: str,
    model: str,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schemaVersion": 1,
        "taskId": args.task_id,
        "role": args.role,
        "harness": args.harness,
        "requestedProvider": provider,
        "requestedModel": model,
        "worktree": str(worktree),
        "repo": str(repo),
        "baseSha": args.base_sha,
        "completionToken": token,
        "resultJson": str(result),
        "receipt": str(receipt),
        "launcherPid": worker_pid,
        "launcherStartTicks": worker_ticks,
        "watcherPid": watcher_pid,
        "watcherStartTicks": watcher_ticks,
        "conductorPane": args.conductor_pane,
        "conductorSession": args.conductor_session,
        "beadsMetadata": {
            "process_pid": worker_pid,
            "process_start_ticks": worker_ticks,
            "watcher_pid": watcher_pid,
            "watcher_start_ticks": watcher_ticks,
            "completion_token": token,
            "result_json": str(result),
            "watcher_receipt": str(receipt),
            "conductor_pane": args.conductor_pane,
            "conductor_session": args.conductor_session,
            "requested_provider": provider,
            "requested_model": model,
            "harness": args.harness,
        },
    }
    if args.worker_pane:
        record["workerPane"] = args.worker_pane
        record["beadsMetadata"]["worker_pane"] = args.worker_pane
    return record


def dispatch_tui(
    args: argparse.Namespace,
    repo: Path,
    worktree: Path,
    brief: Path,
    result: Path,
    receipt: Path,
    dispatch_dir: Path,
    watcher: Path,
) -> int:
    harness_bin = args.harness_bin
    snapshot = pane_snapshot(args.herdr_bin, args.worker_pane)
    status = snapshot.get("agent_status")
    if isinstance(status, str) and status.lower() in TUI_WORKING_STATES:
        die(f"worker pane {args.worker_pane} is already busy (agent_status={status})")
    dispatch_dir.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(16)
    attempt = f"{args.task_id}-{token}"
    query_path = dispatch_dir / f"{attempt}.query.txt"
    query = brief.read_text().replace("{{COMPLETION_TOKEN}}", token).replace("{{RESULT_JSON}}", str(result))
    if "{{COMPLETION_TOKEN}}" in query or "{{RESULT_JSON}}" in query:
        die("brief placeholder replacement failed")
    atomic_write(query_path, query)

    launched = run_herdr(args.herdr_bin, ["pane", "run", args.worker_pane, harness_bin])
    if launched.returncode != 0:
        die(f"pane run failed: {launched.stderr.strip() or launched.stdout.strip()}")
    sent = run_herdr(args.herdr_bin, ["pane", "send-text", args.worker_pane, query])
    if sent.returncode != 0:
        die(f"brief injection failed: {sent.stderr.strip() or sent.stdout.strip()}")
    entered = run_herdr(args.herdr_bin, ["pane", "send-keys", args.worker_pane, "ENTER"])
    if entered.returncode != 0:
        die(f"brief submission failed: {entered.stderr.strip() or entered.stdout.strip()}")

    worker_pid, worker_ticks = verify_tui_launch(args, worktree, harness_bin)

    watcher_cmd = [
        sys.executable, str(watcher),
        "--worker-pid", str(worker_pid),
        "--worker-start-ticks", str(worker_ticks),
        "--task-id", args.task_id,
        "--result-json", str(result),
        "--marker-key", "completionMarker",
        "--marker-value", token,
        "--conductor-pane", args.conductor_pane,
        "--conductor-session", args.conductor_session,
        "--receipt", str(receipt),
        "--herdr-bin", args.herdr_bin,
        "--timeout-seconds", str(args.timeout_seconds),
        "--worker-pane", args.worker_pane,
        "--idle-after-seconds", str(args.idle_after_seconds),
    ]
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
    record = build_record(
        args, repo, worktree, token, result, receipt,
        worker_pid, worker_ticks, watcher_proc.pid, watcher_ticks,
        args.provider.strip() or args.harness,
        args.model.strip() or "tui-default",
    )
    print(json.dumps(record, sort_keys=True))
    return 0


def dispatch_hermes(
    args: argparse.Namespace,
    repo: Path,
    worktree: Path,
    brief: Path,
    result: Path,
    receipt: Path,
    dispatch_dir: Path,
    watcher: Path,
) -> int:
    dispatch_dir.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(16)
    attempt = f"{args.task_id}-{token}"
    query_path = dispatch_dir / f"{attempt}.query.txt"
    launcher_path = dispatch_dir / f"{attempt}.launcher.py"
    log_path = dispatch_dir / f"{attempt}.worker.log"
    query = brief.read_text().replace("{{COMPLETION_TOKEN}}", token).replace("{{RESULT_JSON}}", str(result))
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
    # Fail closed on instant launcher death. A healthy launcher lives for the
    # whole worker run, so a short grace window cannot mask a real failure.
    grace_deadline = time.monotonic() + 0.5
    while launcher.poll() is None and time.monotonic() < grace_deadline:
        time.sleep(0.05)
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
    record = build_record(
        args, repo, worktree, token, result, receipt,
        launcher.pid, ticks, watcher_proc.pid, watcher_ticks,
        args.provider, args.model,
    )
    print(json.dumps(record, sort_keys=True))
    return 0


def main() -> int:
    try:
        args = parse_args()
        repo, worktree, brief, result, receipt, dispatch_dir, watcher = validate(args)
        if args.harness in TUI_HARNESSES:
            return dispatch_tui(args, repo, worktree, brief, result, receipt, dispatch_dir, watcher)
        return dispatch_hermes(args, repo, worktree, brief, result, receipt, dispatch_dir, watcher)
    except (OSError, RuntimeError, ValueError) as exc:
        print(json.dumps({"error": str(exc), "schemaVersion": 1}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
