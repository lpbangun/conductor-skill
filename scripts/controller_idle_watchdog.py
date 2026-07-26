#!/usr/bin/env python3
"""Deterministic idle-controller wake guard for delegated Conductor missions.

This process never mutates Beads, Git, worktrees, or mission state. It only wakes an
idle dedicated controller when durable state has actionable work without a qualified
live completion watcher. The controller remains the sole control-plane authority.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any

PANE_RE = re.compile(r"^[A-Za-z0-9_-]+:p[A-Za-z0-9_-]+$")
LEDGER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
TOKEN_RE = re.compile(r"^[0-9a-fA-F]{32,}$")
IDLE_CONTROLLER_STATES = {"idle", "done"}
WORKING_CONTROLLER_STATES = {"working", "busy", "running", "processing"}
COMMAND_TIMEOUT_SECONDS = 15
WATCHDOG_VERSION = "1.5.0"
MAX_INTERVAL_SECONDS = 86400.0
MAX_MIN_REPEAT_SECONDS = 86400.0
EXPECTED_WATCHER_SCRIPT = str(Path(__file__).resolve().parent / "watch_worker_completion.py")


def run_json(argv: list[str], *, cwd: Path | None = None) -> Any:
    cp = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=COMMAND_TIMEOUT_SECONDS)
    if cp.returncode != 0:
        raise RuntimeError(f"command failed ({cp.returncode}): {argv!r}: {cp.stderr.strip() or cp.stdout.strip()}")
    try:
        return json.loads(cp.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"command returned invalid JSON: {argv!r}") from exc


def run_command(argv: list[str], *, cwd: Path | None = None) -> None:
    cp = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=COMMAND_TIMEOUT_SECONDS)
    if cp.returncode != 0:
        raise RuntimeError(f"command failed ({cp.returncode}): {argv!r}: {cp.stderr.strip() or cp.stdout.strip()}")


def pane_status(herdr: str, pane: str, repo: Path, session_id: str) -> str:
    data = run_json([herdr, "pane", "get", pane])
    pane_data = data.get("result", {}).get("pane", {}) if isinstance(data, dict) else {}
    if pane_data.get("pane_id") != pane or pane_data.get("agent") != "hermes":
        raise RuntimeError("controller pane identity is not the expected Hermes pane")
    session = pane_data.get("agent_session")
    observed_session = session.get("value") if isinstance(session, dict) else None
    if observed_session != session_id:
        raise RuntimeError("controller pane session does not match the bound session")
    observed_cwd = pane_data.get("foreground_cwd") or pane_data.get("cwd")
    if not isinstance(observed_cwd, str) or Path(observed_cwd).resolve() != repo:
        raise RuntimeError("controller pane cwd does not match the mission repository")
    status = pane_data.get("agent_status") or pane_data.get("status")
    if not isinstance(status, str) or not status:
        raise RuntimeError("herdr pane get did not report agent status")
    return status.lower()


def wait_for_working_status(
    herdr: str, pane: str, repo: Path, session_id: str, timeout_seconds: float = 3.0
) -> str:
    deadline = time.monotonic() + timeout_seconds
    status = pane_status(herdr, pane, repo, session_id)
    while status not in WORKING_CONTROLLER_STATES and time.monotonic() < deadline:
        time.sleep(0.1)
        status = pane_status(herdr, pane, repo, session_id)
    return status


def mission_is_active(repo: Path, mission_id: str) -> bool:
    path = repo / ".hermes" / "conductor" / "mission.json"
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read active mission contract: {path}") from exc
    mission = data.get("mission") if isinstance(data, dict) else None
    status = mission.get("status") if isinstance(mission, dict) else None
    if not (isinstance(status, str) and status.lower() == "active"):
        return False
    ledger = data.get("ledger") if isinstance(data, dict) else None
    contract_mission_id = ledger.get("missionId") if isinstance(ledger, dict) else None
    if contract_mission_id != mission_id:
        raise RuntimeError("watchdog mission ID does not match the active contract ledger")
    return True


def task_id(task: Any) -> str:
    if not isinstance(task, dict) or "id" not in task:
        raise RuntimeError("Beads returned a malformed task entry")
    value = task["id"]
    if not isinstance(value, str) or not LEDGER_ID_RE.fullmatch(value):
        raise RuntimeError("Beads returned an invalid task ID")
    return value


def metadata(task: Any) -> dict[str, Any]:
    if not isinstance(task, dict):
        raise RuntimeError("Beads returned a malformed task entry")
    value = task.get("metadata", {})
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    raise RuntimeError("Beads returned malformed task metadata")


def read_start_ticks(proc_root: Path, pid: int) -> int | None:
    try:
        text = (proc_root / str(pid) / "stat").read_text()
        close = text.rfind(")")
        if close < 0:
            return None
        fields = text[close + 2 :].split()
        return int(fields[19])  # /proc/<pid>/stat field 22; fields begin at field 3.
    except (OSError, ValueError, IndexError):
        return None


def flag(argv: list[str], name: str) -> str | None:
    try:
        index = argv.index(name)
    except ValueError:
        return None
    return argv[index + 1] if index + 1 < len(argv) else None


def valid_completion_token(value: Any) -> bool:
    return isinstance(value, str) and TOKEN_RE.fullmatch(value) is not None


def exact_absolute_path(value: Any) -> str | None:
    """Require an exact absolute lexical path. Relative paths and control chars fail closed."""
    if not isinstance(value, str) or not value:
        return None
    if any(ord(char) < 32 for char in value):
        return None
    if not value.startswith("/"):
        return None
    try:
        path = Path(value)
    except (TypeError, ValueError):
        return None
    if not path.is_absolute():
        return None
    # Preserve absolute form without symlink resolution; reject empties after normpath edge cases.
    normalized = os.path.normpath(value)
    if not normalized.startswith("/"):
        return None
    return normalized


def is_expected_watcher_argv(argv: list[str], expected_script: str) -> bool:
    return bool(argv) and (
        argv[0] == expected_script or (len(argv) > 1 and argv[1] == expected_script)
    )


def scan_watchers(
    proc_root: Path, *, expected_script: str = EXPECTED_WATCHER_SCRIPT
) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    try:
        entries = list(proc_root.iterdir())
    except OSError as exc:
        raise RuntimeError(f"cannot inspect process root: {exc}") from exc
    for entry in entries:
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        # Bracket cmdline with start-tick reads so the inspected argv belongs to this identity.
        ticks_before = read_start_ticks(proc_root, pid)
        if ticks_before is None:
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        ticks_after = read_start_ticks(proc_root, pid)
        if ticks_after is None:
            continue
        if ticks_after != ticks_before:
            raise RuntimeError("completion watcher process identity changed during inspection")
        argv = [part.decode(errors="replace") for part in raw.split(b"\0") if part]
        if not is_expected_watcher_argv(argv, expected_script):
            continue
        worker_pid_text = flag(argv, "--worker-pid")
        worker_ticks_text = flag(argv, "--worker-start-ticks")
        try:
            worker_pid = int(worker_pid_text) if worker_pid_text else None
            worker_ticks = int(worker_ticks_text) if worker_ticks_text else None
        except ValueError as exc:
            raise RuntimeError("completion watcher has malformed lifecycle identity") from exc
        required = {
            "taskId": flag(argv, "--task-id"),
            "pane": flag(argv, "--conductor-pane"),
            "sessionId": flag(argv, "--conductor-session"),
            "resultJson": flag(argv, "--result-json"),
            "markerValue": flag(argv, "--marker-value"),
            "receipt": flag(argv, "--receipt"),
        }
        if worker_pid is None or worker_ticks is None or any(value is None for value in required.values()):
            raise RuntimeError("completion watcher is missing required identity arguments")
        found.append(
            {
                "pid": pid,
                "startTicks": ticks_after,
                "script": expected_script,
                **required,
                "workerPid": worker_pid,
                "workerStartTicks": worker_ticks,
                "workerLive": bool(
                    worker_pid
                    and worker_ticks is not None
                    and read_start_ticks(proc_root, worker_pid) == worker_ticks
                ),
            }
        )
    return found


def qualified_watcher_tasks(
    pane: str,
    session_id: str,
    tasks: list[Any],
    watchers: list[dict[str, Any]],
) -> set[str]:
    expected: dict[str, dict[str, Any]] = {}
    for task in tasks:
        tid = task_id(task)
        if not tid:
            continue
        md = metadata(task)
        session = md.get("conductor_session", md.get("controller_session"))
        expected[tid] = {
            "resultJson": exact_absolute_path(md.get("result_json")),
            "watcherPid": md.get("watcher_pid"),
            "watcherStartTicks": md.get("watcher_start_ticks"),
            "workerPid": md.get("process_pid", md.get("worker_pid")),
            "workerStartTicks": md.get("process_start_ticks", md.get("worker_start_ticks")),
            "markerValue": md.get("completion_token"),
            "receipt": exact_absolute_path(md.get("watcher_receipt")),
            "pane": md.get("conductor_pane"),
            "sessionId": session if isinstance(session, str) else None,
        }
    qualified: set[str] = set()
    for watcher in watchers:
        tid = watcher.get("taskId")
        watched_path = exact_absolute_path(watcher.get("resultJson"))
        watched_receipt = exact_absolute_path(watcher.get("receipt"))
        want = expected.get(tid) if isinstance(tid, str) else None
        token = want.get("markerValue") if isinstance(want, dict) else None
        if (
            isinstance(tid, str)
            and isinstance(want, dict)
            and watcher.get("pane") == pane
            and want.get("pane") == pane
            and watcher.get("sessionId") == session_id
            and want.get("sessionId") == session_id
            and watcher.get("workerLive") is True
            and watcher.get("pid") == want.get("watcherPid")
            and watcher.get("startTicks") == want.get("watcherStartTicks")
            and watcher.get("workerPid") == want.get("workerPid")
            and watcher.get("workerStartTicks") == want.get("workerStartTicks")
            and valid_completion_token(token)
            and watcher.get("markerValue") == token
            and watched_receipt is not None
            and want.get("receipt") is not None
            and watched_receipt == want.get("receipt")
            and watched_path is not None
            and want.get("resultJson") is not None
            and watched_path == want.get("resultJson")
        ):
            qualified.add(tid)
    return qualified


def load_state(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, sort_keys=True) + "\n")
    os.replace(tmp, path)


def acquire_instance_lock(repo: Path, mission_id: str) -> int:
    lock_path = repo.resolve() / ".hermes" / "conductor" / f"controller-watchdog.{mission_id}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(lock_path, flags, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.ftruncate(fd, 0)
        os.write(fd, f"{os.getpid()}\n".encode())
        return fd
    except (BlockingIOError, OSError) as exc:
        os.close(fd)
        raise RuntimeError(f"another watchdog owns {lock_path}") from exc


def fingerprint(reason: str, ready: list[str], in_progress: list[str], qualified: set[str]) -> str:
    payload = json.dumps(
        {"reason": reason, "ready": sorted(ready), "inProgress": sorted(in_progress), "qualified": sorted(qualified)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def validate_timing_args(interval_seconds: float, min_repeat_seconds: float) -> str | None:
    if not isinstance(interval_seconds, (int, float)) or isinstance(interval_seconds, bool):
        return "interval must be a finite positive number"
    if not isinstance(min_repeat_seconds, (int, float)) or isinstance(min_repeat_seconds, bool):
        return "minimum repeat must be a finite non-negative number"
    if not math.isfinite(interval_seconds) or interval_seconds <= 0 or interval_seconds > MAX_INTERVAL_SECONDS:
        return "interval must be a finite positive number within 86400 seconds"
    if (
        not math.isfinite(min_repeat_seconds)
        or min_repeat_seconds < 0
        or min_repeat_seconds > MAX_MIN_REPEAT_SECONDS
    ):
        return "minimum repeat must be a finite non-negative number within 86400 seconds"
    return None


def evaluate_once(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    repo = Path(args.repo).resolve()
    if not mission_is_active(repo, args.mission_id):
        return 0, {"wakeDelivered": False, "reason": "mission_not_active"}

    status = pane_status(args.herdr_bin, args.pane, repo, args.session_id)
    if status in WORKING_CONTROLLER_STATES:
        return 0, {"wakeDelivered": False, "reason": "controller_working", "controllerStatus": status}
    if status not in IDLE_CONTROLLER_STATES:
        return 0, {"wakeDelivered": False, "reason": "controller_not_idle", "controllerStatus": status}

    ready_raw = run_json(
        [args.bd_bin, "ready", "--parent", args.mission_id, "--limit", "0", "--json"], cwd=repo
    )
    tasks_raw = run_json(
        [args.bd_bin, "list", "--parent", args.mission_id, "--limit", "0", "--json"], cwd=repo
    )
    if not isinstance(ready_raw, list) or not isinstance(tasks_raw, list):
        raise RuntimeError("Beads ready/list JSON must each be an array")
    ready_tasks = ready_raw
    tasks = tasks_raw
    ready = sorted(tid for task in ready_tasks if (tid := task_id(task)))
    in_progress = sorted(
        tid for task in tasks
        if isinstance(task, dict) and task.get("status") == "in_progress" and (tid := task_id(task))
    )
    expected_script = getattr(args, "expected_watcher_script", EXPECTED_WATCHER_SCRIPT)
    watchers = scan_watchers(Path(args.proc_root), expected_script=expected_script)
    qualified = qualified_watcher_tasks(args.pane, args.session_id, tasks, watchers)

    if ready:
        reason = "ready_without_live_watcher"
    elif in_progress and set(in_progress).issubset(qualified):
        return 0, {
            "wakeDelivered": False,
            "reason": "productive_worker_has_live_wake",
            "inProgress": in_progress,
            "qualifiedWatchers": sorted(qualified),
        }
    elif in_progress:
        reason = "in_progress_without_qualified_watcher"
    else:
        unfinished = sorted(
            tid for task in tasks
            if isinstance(task, dict)
            and task.get("status") not in {"closed", "complete", "completed", "cancelled", "canceled"}
            and (tid := task_id(task))
        )
        if not unfinished:
            return 0, {"wakeDelivered": False, "reason": "no_unfinished_work"}
        reason = "active_mission_without_productive_work"

    fp = fingerprint(reason, ready, in_progress, qualified)
    now = time.time()
    state = load_state(Path(args.state))
    state_bound = (
        state.get("version") == WATCHDOG_VERSION
        and state.get("missionId") == args.mission_id
        and state.get("pane") == args.pane
        and state.get("sessionId") == args.session_id
    )
    try:
        last_wake_at = float(state.get("lastWakeAt", 0))
    except (TypeError, ValueError, OverflowError):
        last_wake_at = 0.0
    if not math.isfinite(last_wake_at) or last_wake_at < 0 or last_wake_at > now + 60:
        last_wake_at = 0.0
    if state_bound and state.get("fingerprint") == fp and now - last_wake_at < args.min_repeat_seconds:
        return 0, {
            "wakeDelivered": False,
            "reason": "wake_rate_limited",
            "frontierReason": reason,
            "ready": ready,
            "inProgress": in_progress,
        }

    message = (
        f"Wake guard ({reason}): reconcile mission {args.mission_id} from durable Beads/Git/process/artifact evidence now. "
        f"Ready={','.join(ready) or 'none'}; in_progress={','.join(in_progress) or 'none'}. "
        "If an authorized dependency-ready/resource-safe lane exists, sample resources, run scheduler_decision.py, and dispatch/refill immediately. "
        "Do not merely summarize the next action and return idle. If a real human boundary blocks progress, record the exact boundary durably."
    )
    pre_submit_status = pane_status(args.herdr_bin, args.pane, repo, args.session_id)
    if pre_submit_status not in IDLE_CONTROLLER_STATES:
        return 0, {
            "wakeDelivered": False,
            "reason": "controller_changed_before_wake",
            "controllerStatus": pre_submit_status,
        }

    # Persist throttle before the external side effect so a later state-write
    # failure cannot re-enable an unlimited wake storm for this frontier.
    submitted_at = time.time()
    state_payload = {
        "version": WATCHDOG_VERSION,
        "missionId": args.mission_id,
        "pane": args.pane,
        "sessionId": args.session_id,
        "fingerprint": fp,
        "lastWakeAt": submitted_at,
        "reason": reason,
        "acknowledged": False,
        "submitPhase": "pending",
    }
    try:
        save_state(Path(args.state), state_payload)
    except OSError as exc:
        return 1, {
            "wakeDelivered": False,
            "reason": "wake_state_persist_failed",
            "error": str(exc),
        }

    try:
        run_command([args.herdr_bin, "pane", "run", args.pane, message])
    except RuntimeError as exc:
        return 1, {"wakeDelivered": False, "reason": "wake_submission_failed", "error": str(exc)}

    state_payload["submitPhase"] = "submitted"
    try:
        save_state(Path(args.state), state_payload)
    except OSError as exc:
        # Throttling already durable from the pending write; surface the failure.
        return 1, {
            "wakeDelivered": False,
            "reason": "wake_state_persist_failed_after_submit",
            "error": str(exc),
            "throttleEstablished": True,
        }

    try:
        accepted_status = wait_for_working_status(
            args.herdr_bin, args.pane, repo, args.session_id
        )
    except RuntimeError as exc:
        return 1, {"wakeDelivered": False, "reason": "wake_ack_observation_failed", "error": str(exc)}
    if accepted_status not in WORKING_CONTROLLER_STATES:
        return 1, {
            "wakeDelivered": False,
            "reason": "wake_not_acknowledged",
            "controllerStatus": accepted_status,
        }
    state_payload["acknowledged"] = True
    try:
        save_state(Path(args.state), state_payload)
    except OSError as exc:
        return 1, {
            "wakeDelivered": False,
            "reason": "wake_ack_state_persist_failed",
            "error": str(exc),
            "controllerStatus": accepted_status,
            "throttleEstablished": True,
        }
    return 0, {
        "wakeDelivered": True,
        "reason": reason,
        "controllerStatus": accepted_status,
        "ready": ready,
        "inProgress": in_progress,
        "qualifiedWatchers": sorted(qualified),
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", required=True)
    p.add_argument(
        "--mission-id",
        required=True,
        type=lambda value: value if LEDGER_ID_RE.fullmatch(value) else p.error("invalid mission ID"),
    )
    p.add_argument("--pane", required=True, type=lambda value: value if PANE_RE.fullmatch(value) else p.error("invalid pane ID"))
    p.add_argument(
        "--session-id",
        required=True,
        type=lambda value: value if LEDGER_ID_RE.fullmatch(value) else p.error("invalid session ID"),
    )
    p.add_argument("--state", required=True)
    p.add_argument("--interval-seconds", type=float, default=30.0)
    p.add_argument("--min-repeat-seconds", type=float, default=90.0)
    p.add_argument("--proc-root", default="/proc")
    p.add_argument("--herdr-bin", default="herdr")
    p.add_argument("--bd-bin", default="bd")
    p.add_argument(
        "--expected-watcher-script",
        default=EXPECTED_WATCHER_SCRIPT,
        help=argparse.SUPPRESS,
    )
    p.add_argument("--once", action="store_true")
    return p


def run_loop(
    args: argparse.Namespace,
    *,
    evaluate: Any = evaluate_once,
    sleeper: Any = time.sleep,
    max_iterations: int | None = None,
) -> int:
    iterations = 0
    while True:
        try:
            code, result = evaluate(args)
        except Exception as exc:
            code, result = 1, {"wakeDelivered": False, "reason": "watchdog_error", "error": str(exc)}
        print(json.dumps(result, sort_keys=True), flush=True)
        iterations += 1
        if args.once:
            return code
        if result.get("reason") == "mission_not_active":
            return 0
        if max_iterations is not None and iterations >= max_iterations:
            return code
        sleeper(args.interval_seconds)


def main() -> int:
    args = parser().parse_args()
    timing_error = validate_timing_args(args.interval_seconds, args.min_repeat_seconds)
    if timing_error:
        parser().error(timing_error)
    args.expected_watcher_script = str(Path(args.expected_watcher_script))
    try:
        lock_fd = acquire_instance_lock(Path(args.repo), args.mission_id)
    except RuntimeError as exc:
        print(json.dumps({"wakeDelivered": False, "reason": "duplicate_watchdog", "error": str(exc)}), flush=True)
        return 1
    try:
        return run_loop(args)
    finally:
        os.close(lock_fd)


if __name__ == "__main__":
    sys.exit(main())
