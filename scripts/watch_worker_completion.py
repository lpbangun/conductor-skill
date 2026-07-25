#!/usr/bin/env python3
"""Wait for a real worker completion artifact and wake a Conductor Herdr pane.

This is a transparent one-shot mission-owned notifier, not a scheduler or state
store. It never writes worker result evidence or mutates Beads.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import select
import subprocess
import sys
import time
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def valid_completion_token(value: str) -> bool:
    return len(value) >= 32 and all(char in "0123456789abcdefABCDEF" for char in value)


def valid_task_id(value: str) -> bool:
    return re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value) is not None


def valid_pane_id(value: str) -> bool:
    return re.fullmatch(r"w[A-Za-z0-9]+:p[A-Za-z0-9]+", value) is not None


def atomic_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    os.replace(temp, path)


def process_start_ticks(pid: int) -> int | None:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
        close_paren = stat.rfind(")")
        if close_paren < 0:
            return None
        # The remainder starts at field 3 (state); starttime is field 22.
        remainder = stat[close_paren + 1 :].split()
        return int(remainder[19])
    except (OSError, ValueError, IndexError):
        return None


def wait_for_exit(
    pid: int,
    expected_start_ticks: int,
    deadline: float,
    attached_pidfd: int | None = None,
) -> bool:
    """Block on a verified pidfd when available; use bounded identity polling otherwise."""
    if attached_pidfd is not None:
        poller = select.poll()
        poller.register(attached_pidfd, select.POLLIN)
        remaining_ms = max(0, int((deadline - time.monotonic()) * 1000))
        return bool(poller.poll(remaining_ms))

    current = process_start_ticks(pid)
    if current is None:
        return True
    if current != expected_start_ticks:
        return True

    delay = 0.05
    while time.monotonic() < deadline:
        current = process_start_ticks(pid)
        if current is None or current != expected_start_ticks:
            return True
        time.sleep(min(delay, max(0.0, deadline - time.monotonic())))
        delay = min(delay * 1.7, 1.0)
    return False


def wait_for_valid_artifact(
    path: Path,
    marker_key: str,
    marker_value: str,
    deadline: float,
) -> tuple[bool, str]:
    delay = 0.05
    last_error = "completion artifact missing"
    while time.monotonic() < deadline:
        try:
            data = json.loads(path.read_text())
            if not isinstance(data, dict):
                last_error = "completion artifact is not a JSON object"
            elif data.get(marker_key) != marker_value:
                return False, f"completion marker mismatch: expected {marker_value!r}"
            else:
                return True, ""
        except FileNotFoundError:
            last_error = "completion artifact missing"
        except (OSError, json.JSONDecodeError) as exc:
            last_error = f"completion artifact unreadable: {exc}"
        time.sleep(min(delay, max(0.0, deadline - time.monotonic())))
        delay = min(delay * 1.7, 1.0)
    return False, last_error


def run_herdr(binary: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [binary, *args],
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker-pid", type=int, required=True)
    parser.add_argument("--worker-start-ticks", type=int, required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--result-json", type=Path, required=True)
    parser.add_argument("--marker-key", required=True)
    parser.add_argument("--marker-value", required=True)
    parser.add_argument("--conductor-pane", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--herdr-bin", default="herdr")
    parser.add_argument("--timeout-seconds", type=float, default=7200.0)
    args = parser.parse_args()

    started_monotonic = time.monotonic()
    receipt: dict[str, Any] = {
        "schemaVersion": 1,
        "taskId": args.task_id,
        "workerPid": args.worker_pid,
        "startedAt": utc_now(),
        "workerExitObserved": False,
        "completionArtifactValidated": False,
        "conductorWakeDelivered": False,
        "manualReconcile": False,
        "wakeMessage": "",
        "error": "",
    }

    if (
        args.worker_pid <= 1
        or args.timeout_seconds <= 0
        or not args.marker_key
        or not valid_completion_token(args.marker_value)
        or not valid_task_id(args.task_id)
        or not valid_pane_id(args.conductor_pane)
    ):
        receipt["error"] = "invalid worker PID, timeout, marker key/token, task ID, or pane ID"
        receipt["manualReconcile"] = True
        atomic_json(args.receipt, receipt)
        return 2

    if os.path.lexists(args.result_json):
        receipt["error"] = "completion artifact predates watcher attachment"
        receipt["manualReconcile"] = True
        atomic_json(args.receipt, receipt)
        return 3

    observed_start_ticks = process_start_ticks(args.worker_pid)
    if observed_start_ticks is None or observed_start_ticks != args.worker_start_ticks:
        receipt["error"] = "worker PID identity mismatch or worker not live at watcher startup"
        receipt["manualReconcile"] = True
        atomic_json(args.receipt, receipt)
        return 3
    expected_ticks = args.worker_start_ticks
    receipt["workerStartTicks"] = expected_ticks

    attached_pidfd: int | None = None
    if hasattr(os, "pidfd_open"):
        try:
            attached_pidfd = os.pidfd_open(args.worker_pid)
        except OSError:
            # A process can exit between the initial identity read and pidfd_open.
            # Fail closed if its exact identity is no longer observable; otherwise
            # the bounded start-ticks polling fallback remains safe.
            if process_start_ticks(args.worker_pid) != expected_ticks:
                receipt["error"] = "worker exited or changed identity during watcher attachment"
                receipt["manualReconcile"] = True
                atomic_json(args.receipt, receipt)
                return 3
        else:
            if process_start_ticks(args.worker_pid) != expected_ticks:
                os.close(attached_pidfd)
                receipt["error"] = "worker exited or changed identity after pidfd attachment"
                receipt["manualReconcile"] = True
                atomic_json(args.receipt, receipt)
                return 3

    if os.path.lexists(args.result_json):
        if attached_pidfd is not None:
            os.close(attached_pidfd)
        receipt["error"] = "completion artifact appeared during watcher attachment"
        receipt["manualReconcile"] = True
        atomic_json(args.receipt, receipt)
        return 3

    deadline = started_monotonic + args.timeout_seconds
    try:
        exited = wait_for_exit(args.worker_pid, expected_ticks, deadline, attached_pidfd)
    finally:
        if attached_pidfd is not None:
            os.close(attached_pidfd)
    if not exited:
        receipt["error"] = "worker completion timeout"
        receipt["manualReconcile"] = True
        atomic_json(args.receipt, receipt)
        return 4
    exit_observed_monotonic = time.monotonic()
    receipt["workerExitObserved"] = True
    receipt["workerExitObservedAt"] = utc_now()

    valid, error = wait_for_valid_artifact(
        args.result_json,
        args.marker_key,
        args.marker_value,
        deadline,
    )
    if not valid:
        receipt["error"] = error
        receipt["manualReconcile"] = True
        receipt["completionToWakeSeconds"] = time.monotonic() - exit_observed_monotonic
        atomic_json(args.receipt, receipt)
        return 5
    receipt["completionArtifactValidated"] = True
    receipt["completionArtifactValidatedAt"] = utc_now()

    pane = run_herdr(args.herdr_bin, ["pane", "get", args.conductor_pane])
    if pane.returncode != 0:
        receipt["error"] = f"conductor pane unavailable: {pane.stderr.strip()}"
        receipt["manualReconcile"] = True
        atomic_json(args.receipt, receipt)
        return 6

    message = (
        f"Conductor completion event: task {args.task_id} worker PID {args.worker_pid} exited "
        "and its worker-created completion artifact passed marker validation. "
        "Reconcile evidence and Beads now, resample resources, run scheduler_decision.py, "
        "and immediately refill every safe productive lane."
    )
    receipt["wakeMessage"] = message
    sent = run_herdr(args.herdr_bin, ["pane", "send-text", args.conductor_pane, message])
    if sent.returncode != 0:
        receipt["error"] = f"wake text failed: {sent.stderr.strip()}"
        receipt["manualReconcile"] = True
        atomic_json(args.receipt, receipt)
        return 7
    entered = run_herdr(args.herdr_bin, ["pane", "send-keys", args.conductor_pane, "ENTER"])
    if entered.returncode != 0:
        receipt["error"] = f"wake enter failed: {entered.stderr.strip()}"
        receipt["manualReconcile"] = True
        atomic_json(args.receipt, receipt)
        return 8

    receipt["conductorWakeDelivered"] = True
    receipt["wakeDeliveredAt"] = utc_now()
    receipt["completionToWakeSeconds"] = time.monotonic() - exit_observed_monotonic
    atomic_json(args.receipt, receipt)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
