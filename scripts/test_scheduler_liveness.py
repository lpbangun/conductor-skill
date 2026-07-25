#!/usr/bin/env python3
"""Regression tests for speed-first dispatch and autonomous completion wake."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from unittest import mock

SCRIPT_DIR = Path(__file__).resolve().parent
TOKEN = "a" * 32
sys.path.insert(0, str(SCRIPT_DIR))


def safe_resources(**overrides):
    data = {
        "availableRamGb": 6.4,
        "memoryPsiFullAvg10": 0.0,
        "swapOutMiBPerSecond": 0.0,
        "sampleAgeSeconds": 0.1,
    }
    data.update(overrides)
    return data


def budgets(**overrides):
    data = {
        "maxWorkers": 3,
        "maxWeightedSlots": 3.0,
        "minAvailableRamGb": 2.0,
        "maxMemoryPsiFullAvg10": 5.0,
        "maxSwapOutMiBPerSecond": 64.0,
        "resourceSampleSeconds": 10,
    }
    data.update(overrides)
    return data


def task(task_id, slot=1.0, reserve=2.0, priority=1, owners=()):
    return {
        "id": task_id,
        "priority": priority,
        "productive": True,
        "slotCost": slot,
        "ramReserveGb": reserve,
        "ownershipKeys": list(owners or (task_id,)),
    }


class SpeedFirstSchedulerTests(unittest.TestCase):
    def plan(self, **snapshot_overrides):
        from scheduler_decision import plan_dispatch

        snapshot = {
            "ready": [],
            "active": [],
            "resources": safe_resources(),
            "budgets": budgets(),
        }
        snapshot.update(snapshot_overrides)
        return plan_dispatch(snapshot)

    def test_two_safe_standard_lanes_are_both_selected(self):
        result = self.plan(ready=[task("c"), task("d")])
        self.assertEqual(["c", "d"], result["selectedTaskIds"])
        self.assertEqual("maximize_useful_throughput", result["objective"])
        self.assertFalse(result["underfilled"])

    def test_scheduler_maximizes_productive_count_up_to_safe_capacity(self):
        result = self.plan(
            ready=[task("a"), task("b"), task("c")],
            resources=safe_resources(availableRamGb=10.0),
        )
        self.assertEqual(["a", "b", "c"], result["selectedTaskIds"])

    def test_one_worker_is_accepted_when_it_is_the_only_useful_lane(self):
        result = self.plan(ready=[task("only")])
        self.assertEqual(["only"], result["selectedTaskIds"])
        self.assertTrue(result["underfilled"])
        self.assertEqual("no_second_productive_dependency_ready_lane", result["underfillReason"])

    def test_nonproductive_duplicate_verification_does_not_fill_second_slot(self):
        duplicate = task("duplicate-suite")
        duplicate["productive"] = False
        result = self.plan(ready=[task("real"), duplicate])
        self.assertEqual(["real"], result["selectedTaskIds"])
        self.assertEqual("no_second_productive_dependency_ready_lane", result["underfillReason"])

    def test_complete_ready_queue_does_not_materialize_all_combinations(self):
        ready = [task(f"t{i:03}", slot=0.25, reserve=0.5, priority=i % 5, owners=(f"k{i}",)) for i in range(40)]
        started = time.monotonic()
        result = self.plan(
            ready=ready,
            budgets=budgets(maxWorkers=6, maxWeightedSlots=6.0),
        )
        elapsed = time.monotonic() - started
        self.assertEqual(6, len(result["selectedTaskIds"]))
        self.assertLess(elapsed, 1.0, "planner must not enumerate every feasible six-lane combination")

    def test_equal_throughput_prefers_p0_p0_over_p0_p1(self):
        first = task("first", priority=0, owners=("shared",))
        second = task("second", priority=0, owners=("second",)) | {"conflictsWith": ["first"]}
        third = task("third", priority=0, owners=("shared",))
        lower = task("lower", priority=1, owners=("lower",))
        result = self.plan(
            ready=[first, second, third, lower],
            budgets=budgets(maxWorkers=2, maxWeightedSlots=2.0),
        )
        self.assertEqual(["second", "third"], result["selectedTaskIds"])

    def test_equal_throughput_set_does_not_skip_p0_for_lower_priority_sum(self):
        urgent = task("urgent", priority=0, owners=("urgent",)) | {"conflictsWith": ["normal-a", "normal-b"]}
        normal_a = task("normal-a", priority=1, owners=("a",))
        normal_b = task("normal-b", priority=1, owners=("b",))
        fallback = task("fallback", priority=4, owners=("fallback",))
        result = self.plan(
            ready=[urgent, normal_a, normal_b, fallback],
            budgets=budgets(maxWorkers=2, maxWeightedSlots=2.0),
        )
        self.assertEqual(["urgent", "fallback"], result["selectedTaskIds"])

    def test_one_heavy_and_one_standard_fit_three_weighted_slots(self):
        result = self.plan(
            ready=[task("heavy", 2.0, 4.0), task("standard")],
            resources=safe_resources(availableRamGb=10.0),
        )
        self.assertEqual(["heavy", "standard"], result["selectedTaskIds"])

    def test_two_heavy_lanes_do_not_fit_three_weighted_slots(self):
        result = self.plan(
            ready=[task("heavy-a", 2.0, 4.0), task("heavy-b", 2.0, 4.0)],
            resources=safe_resources(availableRamGb=12.0),
        )
        self.assertEqual(1, len(result["selectedTaskIds"]))
        self.assertEqual("weighted_capacity_blocks_second_lane", result["underfillReason"])

    def test_disjoint_light_lane_is_not_starved_by_active_heavy_lane(self):
        active = [task("review", 2.0, 4.0, owners=("review",)) | {"live": True}]
        result = self.plan(active=active, ready=[task("docs", 0.5, 1.0, owners=("docs",))])
        self.assertEqual(["docs"], result["selectedTaskIds"])
        self.assertEqual(2, result["productiveWorkersAfter"])
        self.assertFalse(result["underfilled"])

    def test_nonproductive_active_work_consumes_capacity_but_not_productive_target(self):
        active = [task("duplicate-review", owners=("review",)) | {"live": True, "productive": False}]
        result = self.plan(active=active, ready=[task("implementation", owners=("src",))])
        self.assertEqual(["implementation"], result["selectedTaskIds"])
        self.assertEqual(1, result["productiveWorkersAfter"])
        self.assertTrue(result["underfilled"])
        self.assertEqual("no_second_productive_dependency_ready_lane", result["underfillReason"])

    def test_malformed_active_liveness_fails_closed_instead_of_freeing_capacity(self):
        active = [task("unknown-worker") | {"live": "yes"}]
        result = self.plan(active=active, ready=[task("a"), task("b"), task("c")])
        self.assertEqual([], result["selectedTaskIds"])
        self.assertEqual("invalid_active_worker_evidence", result["dispatchBlockedReason"])

    def test_malformed_priority_fails_closed(self):
        for value in (None, True, -1, 5, "1"):
            with self.subTest(value=value):
                malformed = task("a") | {"priority": value}
                result = self.plan(ready=[malformed])
                self.assertEqual([], result["selectedTaskIds"])
                self.assertEqual("invalid_ready_task_evidence", result["dispatchBlockedReason"])

    def test_empty_ownership_evidence_fails_closed(self):
        malformed = task("a") | {"ownershipKeys": []}
        result = self.plan(ready=[malformed, task("b")])
        self.assertEqual([], result["selectedTaskIds"])
        self.assertEqual("invalid_ready_task_evidence", result["dispatchBlockedReason"])

    def test_malformed_conflict_evidence_fails_closed(self):
        malformed = task("a") | {"conflictsWith": "b"}
        result = self.plan(ready=[malformed, task("b")])
        self.assertEqual([], result["selectedTaskIds"])
        self.assertEqual("invalid_ready_task_evidence", result["dispatchBlockedReason"])

    def test_duplicate_ready_or_active_task_identity_fails_closed(self):
        duplicate_ready = self.plan(ready=[task("same"), task("same")])
        self.assertEqual([], duplicate_ready["selectedTaskIds"])
        self.assertEqual("duplicate_task_identity", duplicate_ready["dispatchBlockedReason"])

        active = [task("same") | {"live": True}]
        duplicate_active = self.plan(active=active, ready=[task("same")])
        self.assertEqual([], duplicate_active["selectedTaskIds"])
        self.assertEqual("duplicate_task_identity", duplicate_active["dispatchBlockedReason"])

    def test_overlapping_ownership_is_not_parallelized(self):
        result = self.plan(ready=[task("a", owners=("src/shared.js",)), task("b", owners=("src/shared.js",))])
        self.assertEqual(1, len(result["selectedTaskIds"]))
        self.assertEqual("ownership_conflict_blocks_second_lane", result["underfillReason"])

    def test_sticky_cumulative_swap_occupancy_does_not_block(self):
        resources = safe_resources(swapUsedPercent=99.0)
        result = self.plan(ready=[task("a"), task("b")], resources=resources)
        self.assertEqual(["a", "b"], result["selectedTaskIds"])

    def test_batch_ram_reserve_preserves_emergency_floor(self):
        result = self.plan(
            ready=[task("a", reserve=2.0), task("b", reserve=2.0)],
            resources=safe_resources(availableRamGb=6.0),
        )
        self.assertEqual(1, len(result["selectedTaskIds"]))
        self.assertEqual("ram_reserve_blocks_second_lane", result["underfillReason"])

    def test_low_ram_blocks_new_dispatch(self):
        result = self.plan(ready=[task("a")], resources=safe_resources(availableRamGb=1.9))
        self.assertEqual([], result["selectedTaskIds"])
        self.assertEqual("resource_pressure", result["dispatchBlockedReason"])

    def test_high_psi_blocks_new_dispatch(self):
        result = self.plan(ready=[task("a")], resources=safe_resources(memoryPsiFullAvg10=5.0))
        self.assertEqual([], result["selectedTaskIds"])

    def test_active_swap_out_blocks_new_dispatch(self):
        result = self.plan(ready=[task("a")], resources=safe_resources(swapOutMiBPerSecond=64.0))
        self.assertEqual([], result["selectedTaskIds"])

    def test_packaged_mission_budget_is_scheduler_compatible(self):
        template = json.loads((SCRIPT_DIR.parent / "templates" / "mission.json").read_text())
        budgets = template["budgets"]
        fresh = self.plan(
            ready=[task("a"), task("b")],
            budgets=budgets,
            resources=safe_resources(sampleAgeSeconds=budgets["resourceSampleSeconds"]),
        )
        self.assertEqual(["a", "b"], fresh["selectedTaskIds"])
        stale = self.plan(
            ready=[task("a")],
            budgets=budgets,
            resources=safe_resources(sampleAgeSeconds=budgets["resourceSampleSeconds"] + 0.001),
        )
        self.assertEqual([], stale["selectedTaskIds"])
        self.assertEqual("resource_pressure", stale["dispatchBlockedReason"])

    def test_missing_malformed_nonfinite_or_boolean_metric_fails_closed(self):
        bad_values = [None, "6.4", float("nan"), float("inf"), True]
        for value in bad_values:
            with self.subTest(value=value):
                resources = safe_resources(availableRamGb=value)
                result = self.plan(ready=[task("a")], resources=resources)
                self.assertEqual([], result["selectedTaskIds"])
                self.assertEqual("invalid_or_stale_resource_evidence", result["dispatchBlockedReason"])

    def test_pressure_does_not_suppress_harvest_or_cleanup_actions(self):
        result = self.plan(
            ready=[task("a")],
            resources=safe_resources(availableRamGb=1.0),
            pendingControlActions=[{"type": "harvest", "taskId": "done"}, {"type": "close_pane", "paneId": "p1"}],
        )
        self.assertEqual([], result["selectedTaskIds"])
        self.assertEqual(2, len(result["controlActions"]))


class CompletionWakeTests(unittest.TestCase):
    def test_completion_token_must_be_dispatch_unique_shape(self):
        from watch_worker_completion import valid_completion_token

        self.assertFalse(valid_completion_token("PASS"))
        self.assertFalse(valid_completion_token("a" * 31))
        self.assertTrue(valid_completion_token(TOKEN))

    def test_terminal_identifiers_reject_control_text_before_herdr(self):
        from watch_worker_completion import process_start_ticks

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt = root / "receipt.json"
            log = root / "herdr-log.json"
            fake = self.make_fake_herdr(root)
            ticks = process_start_ticks(os.getpid())
            assert ticks is not None
            env = os.environ.copy()
            env["FAKE_HERDR_LOG"] = str(log)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "watch_worker_completion.py"),
                    "--worker-pid", str(os.getpid()),
                    "--worker-start-ticks", str(ticks),
                    "--task-id", "bad\nwhoami",
                    "--result-json", str(root / "result.json"),
                    "--marker-key", "completionMarker",
                    "--marker-value", TOKEN,
                    "--conductor-pane", "w9:p1",
                    "--receipt", str(receipt),
                    "--herdr-bin", str(fake),
                    "--timeout-seconds", "1",
                ],
                env=env,
                text=True,
                capture_output=True,
                timeout=3,
            )
            self.assertEqual(2, result.returncode)
            self.assertFalse(log.exists(), "unsafe terminal text must be rejected before any Herdr call")

    def test_process_start_ticks_handles_spaces_in_comm(self):
        from watch_worker_completion import process_start_ticks

        worker = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import os,time; open('/proc/self/comm','w').write('worker space\\n'); print('READY',flush=True); time.sleep(2)",
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            assert worker.stdout is not None
            self.assertEqual("READY", worker.stdout.readline().strip())
            self.assertIsNotNone(process_start_ticks(worker.pid))
        finally:
            worker.terminate()
            worker.wait(timeout=2)
            if worker.stdout is not None:
                worker.stdout.close()

    def make_fake_herdr(self, root: Path) -> Path:
        path = root / "herdr"
        path.write_text(textwrap.dedent("""\
            #!/usr/bin/env python3
            import json, os, pathlib, sys
            args = sys.argv[1:]
            if len(args) < 3 or args[:2] not in (["pane", "get"], ["pane", "send-text"], ["pane", "send-keys"]):
                print("unsupported fake herdr command", file=sys.stderr)
                raise SystemExit(2)
            required = [pathlib.Path(item) for item in os.environ.get("FAKE_HERDR_REQUIRE", "").split(os.pathsep) if item]
            if any(not item.exists() for item in required):
                print("wake attempted before launcher lifecycle completed", file=sys.stderr)
                raise SystemExit(9)
            forbidden_pid = os.environ.get("FAKE_HERDR_FORBID_PID")
            forbidden_ticks = os.environ.get("FAKE_HERDR_FORBID_START_TICKS")
            if forbidden_pid and forbidden_ticks:
                try:
                    raw = pathlib.Path(f"/proc/{forbidden_pid}/stat").read_text()
                    tail = raw[raw.rfind(")") + 2:].split()
                    if tail[0] != "Z" and int(tail[19]) == int(forbidden_ticks):
                        print("wake attempted while exact launcher identity was still live", file=sys.stderr)
                        raise SystemExit(9)
                except FileNotFoundError:
                    pass
            log = pathlib.Path(os.environ["FAKE_HERDR_LOG"])
            rows = json.loads(log.read_text()) if log.exists() else []
            rows.append(args)
            log.write_text(json.dumps(rows))
            if args[:2] == ["pane", "get"]:
                print(json.dumps({"result": {"pane": {"pane_id": args[2]}}}))
            else:
                print(json.dumps({"result": {"type": "ok"}}))
        """))
        path.chmod(0o755)
        return path

    def run_watcher(self, root: Path, worker_code: str, marker_value=TOKEN, required_wake_files=()):
        result_path = root / "result.json"
        receipt_path = root / "receipt.json"
        log_path = root / "herdr-log.json"
        fake_herdr = self.make_fake_herdr(root)
        from watch_worker_completion import process_start_ticks

        worker = subprocess.Popen([sys.executable, "-c", worker_code, str(result_path)])
        start_ticks = process_start_ticks(worker.pid)
        assert start_ticks is not None
        cmd = [
            sys.executable,
            str(SCRIPT_DIR / "watch_worker_completion.py"),
            "--worker-pid", str(worker.pid),
            "--worker-start-ticks", str(start_ticks),
            "--task-id", "task-1",
            "--result-json", str(result_path),
            "--marker-key", "completionMarker",
            "--marker-value", marker_value,
            "--conductor-pane", "w9:p1",
            "--receipt", str(receipt_path),
            "--herdr-bin", str(fake_herdr),
            "--timeout-seconds", "5",
        ]
        env = os.environ.copy()
        env["FAKE_HERDR_LOG"] = str(log_path)
        env["FAKE_HERDR_REQUIRE"] = os.pathsep.join(str(path) for path in required_wake_files)
        env["FAKE_HERDR_FORBID_PID"] = str(worker.pid)
        env["FAKE_HERDR_FORBID_START_TICKS"] = str(start_ticks)
        started = time.monotonic()
        watcher = subprocess.run(cmd, env=env, text=True, capture_output=True, timeout=8)
        elapsed = time.monotonic() - started
        worker.wait(timeout=2)
        return watcher, elapsed, result_path, receipt_path, log_path

    def test_real_worker_exit_and_worker_artifact_wake_conductor(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            worker_code = (
                "import json,pathlib,sys,time; time.sleep(.2); "
                "pathlib.Path(sys.argv[1]).write_text(json.dumps({'completionMarker':'" + TOKEN + "','status':'PASS'}))"
            )
            watcher, elapsed, _, receipt, log = self.run_watcher(root, worker_code)
            self.assertEqual(0, watcher.returncode, watcher.stderr)
            self.assertGreaterEqual(elapsed, 0.15, "watcher must observe the external worker; it cannot synthesize completion")
            data = json.loads(receipt.read_text())
            self.assertTrue(data["workerExitObserved"])
            self.assertIsNotNone(data["workerStartTicks"], "watcher must attach to the live worker identity")
            self.assertTrue(data["completionArtifactValidated"])
            self.assertTrue(data["conductorWakeDelivered"])
            self.assertLess(data["completionToWakeSeconds"], 1.0)
            self.assertFalse(data["manualReconcile"])
            calls = json.loads(log.read_text())
            self.assertIn(["pane", "send-text", "w9:p1", data["wakeMessage"]], calls)
            self.assertIn(["pane", "send-keys", "w9:p1", "ENTER"], calls)

    def test_fallback_capable_launcher_is_watched_through_replacement_child(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            failed_done = root / "failed-child-done"
            replacement_done = root / "replacement-child-done"
            launcher_exiting = root / "launcher-exiting"
            launcher_code = textwrap.dedent(f"""\
                import pathlib, subprocess, sys, time
                root = pathlib.Path(sys.argv[1]).parent
                failed = subprocess.run([
                    sys.executable, '-c',
                    "import pathlib,sys; pathlib.Path(sys.argv[1]).write_text(str(__import__('os').getpid())); raise SystemExit(73)",
                    str(root / 'failed-child-done'),
                ])
                assert failed.returncode == 73
                replacement = "import json,os,pathlib,sys,time; result=pathlib.Path(sys.argv[1]); result.write_text(json.dumps({{'completionMarker':'{TOKEN}','status':'PASS'}})); time.sleep(.15); pathlib.Path(sys.argv[2]).write_text(str(os.getpid()))"
                subprocess.run([sys.executable, '-c', replacement, sys.argv[1], str(root / 'replacement-child-done')], check=True)
                (root / 'launcher-exiting').write_text('complete')
                time.sleep(.1)
            """)
            required = (failed_done, replacement_done, launcher_exiting)
            watcher, _, _, receipt, log = self.run_watcher(
                root,
                launcher_code,
                required_wake_files=required,
            )
            self.assertEqual(0, watcher.returncode, watcher.stderr)
            self.assertTrue(all(path.exists() for path in required))
            self.assertNotEqual(failed_done.read_text(), replacement_done.read_text())
            data = json.loads(receipt.read_text())
            self.assertTrue(data["workerExitObserved"])
            self.assertTrue(data["completionArtifactValidated"])
            self.assertTrue(data["conductorWakeDelivered"])

    def test_artifact_appearing_during_pidfd_attachment_is_rejected(self):
        import watch_worker_completion as watcher_module

        if not hasattr(os, "pidfd_open"):
            self.skipTest("pidfd_open unavailable")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result_path = root / "result.json"
            receipt_path = root / "receipt.json"
            worker = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(3)"])
            try:
                start_ticks = watcher_module.process_start_ticks(worker.pid)
                assert start_ticks is not None
                real_pidfd_open = os.pidfd_open

                def racing_pidfd_open(pid):
                    fd = real_pidfd_open(pid)
                    result_path.write_text(json.dumps({"completionMarker": TOKEN, "status": "PASS"}))
                    return fd

                argv = [
                    "watch_worker_completion.py",
                    "--worker-pid", str(worker.pid),
                    "--worker-start-ticks", str(start_ticks),
                    "--task-id", "attach-race",
                    "--result-json", str(result_path),
                    "--marker-key", "completionMarker",
                    "--marker-value", TOKEN,
                    "--conductor-pane", "w9:p1",
                    "--receipt", str(receipt_path),
                    "--timeout-seconds", "1",
                ]
                with mock.patch.object(sys, "argv", argv), mock.patch.object(
                    watcher_module.os, "pidfd_open", side_effect=racing_pidfd_open
                ):
                    self.assertEqual(3, watcher_module.main())
                receipt = json.loads(receipt_path.read_text())
                self.assertFalse(receipt["completionArtifactValidated"])
                self.assertTrue(receipt["manualReconcile"])
            finally:
                worker.terminate()
                worker.wait(timeout=2)

    def test_stale_valid_artifact_cannot_wake_without_live_pid_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result_path = root / "result.json"
            receipt_path = root / "receipt.json"
            result_path.write_text(json.dumps({"completionMarker": TOKEN, "status": "PASS"}))
            watcher = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "watch_worker_completion.py"),
                    "--worker-pid", "99999999",
                    "--worker-start-ticks", "123",
                    "--task-id", "stale-task",
                    "--result-json", str(result_path),
                    "--marker-key", "completionMarker",
                    "--marker-value", TOKEN,
                    "--conductor-pane", "w9:p1",
                    "--receipt", str(receipt_path),
                    "--timeout-seconds", "1",
                ],
                text=True,
                capture_output=True,
                timeout=3,
            )
            self.assertEqual(3, watcher.returncode)
            data = json.loads(receipt_path.read_text())
            self.assertFalse(data["workerExitObserved"])
            self.assertFalse(data["completionArtifactValidated"])
            self.assertFalse(data["conductorWakeDelivered"])
            self.assertTrue(data["manualReconcile"])

    def test_preexisting_valid_artifact_is_rejected_before_live_attachment(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result_path = root / "result.json"
            receipt_path = root / "receipt.json"
            log_path = root / "herdr-log.json"
            fake_herdr = self.make_fake_herdr(root)
            result_path.write_text(json.dumps({"completionMarker": TOKEN, "status": "PASS"}))
            from watch_worker_completion import process_start_ticks

            worker = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(3)"])
            try:
                start_ticks = process_start_ticks(worker.pid)
                assert start_ticks is not None
                env = os.environ.copy()
                env["FAKE_HERDR_LOG"] = str(log_path)
                watcher = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPT_DIR / "watch_worker_completion.py"),
                        "--worker-pid", str(worker.pid),
                        "--worker-start-ticks", str(start_ticks),
                        "--task-id", "replay-task",
                        "--result-json", str(result_path),
                        "--marker-key", "completionMarker",
                        "--marker-value", TOKEN,
                        "--conductor-pane", "w9:p1",
                        "--receipt", str(receipt_path),
                        "--herdr-bin", str(fake_herdr),
                        "--timeout-seconds", "1",
                    ],
                    env=env,
                    text=True,
                    capture_output=True,
                    timeout=3,
                )
                self.assertEqual(3, watcher.returncode)
                data = json.loads(receipt_path.read_text())
                self.assertIn("predates watcher attachment", data["error"])
                self.assertFalse(data["workerExitObserved"])
                self.assertFalse(data["completionArtifactValidated"])
                self.assertFalse(data["conductorWakeDelivered"])
                self.assertTrue(data["manualReconcile"])
                self.assertFalse(log_path.exists())
            finally:
                worker.terminate()
                worker.wait(timeout=2)

    def test_invalid_artifact_never_wakes_conductor(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            worker_code = (
                "import json,pathlib,sys; "
                "pathlib.Path(sys.argv[1]).write_text(json.dumps({'completionMarker':'WRONG','status':'PASS'}))"
            )
            watcher, _, _, receipt, log = self.run_watcher(root, worker_code)
            self.assertNotEqual(0, watcher.returncode)
            data = json.loads(receipt.read_text())
            self.assertFalse(data["completionArtifactValidated"])
            self.assertFalse(data["conductorWakeDelivered"])
            self.assertTrue(data["manualReconcile"])
            self.assertFalse(log.exists(), "invalid evidence must not call Herdr")


class PolicyContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = (SCRIPT_DIR.parent / "SKILL.md").read_text().lower()
        cls.reference = (SCRIPT_DIR.parent / "references" / "speed-first-liveness.md").read_text().lower()

    def test_speed_is_objective_and_resources_are_constraints(self):
        self.assertIn("useful throughput is the scheduling objective", self.skill)
        self.assertIn("resource policy is an admission constraint", self.skill)

    def test_delegated_mode_requires_verified_completion_wake(self):
        self.assertIn("every active worker has a verified completion-wake handle", self.skill)
        self.assertIn("watch_worker_completion.py", self.skill)

    def test_idle_return_with_unwatched_worker_is_forbidden(self):
        self.assertIn("never return idle while an active worker is unwatched", self.skill)

    def test_reference_defines_tight_end_to_end_eval(self):
        required = [
            "external worker process",
            "worker-created completion artifact",
            "separate watcher process",
            "actual conductor pane",
            "completion-to-wake latency",
            "two productive lanes",
            "direct reconcile calls cannot satisfy",
        ]
        for phrase in required:
            self.assertIn(phrase, self.reference)

    def test_reference_requires_replay_safe_verified_attachment(self):
        self.assertIn("must not exist at watcher attachment", self.reference)
        self.assertIn("after opening the pidfd", self.reference)
        self.assertIn("manual reconciliation", self.reference)


if __name__ == "__main__":
    unittest.main(verbosity=2)
