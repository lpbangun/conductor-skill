#!/usr/bin/env python3
import importlib.util
import json
import os
import subprocess
import tempfile
import time
import unittest
from unittest import mock
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "controller_idle_watchdog.py"


class WatchdogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="conductor-watchdog-")
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        (self.repo / ".hermes" / "conductor").mkdir(parents=True)
        (self.repo / ".hermes" / "conductor" / "mission.json").write_text(
            json.dumps({"mission": {"status": "active"}, "ledger": {"missionId": "mission-1"}})
        )
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.proc = self.root / "proc"
        self.proc.mkdir()
        self.herdr_state = self.root / "herdr-state.json"
        self.herdr_log = self.root / "herdr.log"
        self.bd_state = self.root / "bd-state.json"
        self.bd_log = self.root / "bd.log"
        self.state = self.root / "watchdog-state.json"
        self.herdr_state.write_text(json.dumps({
            "status": "idle", "agent": "hermes", "cwd": str(self.repo), "session": "session-1"
        }))
        self.bd_state.write_text(json.dumps({"ready": [], "tasks": []}))
        self._write_fake_herdr()
        self._write_fake_bd()

    def tearDown(self):
        self.tmp.cleanup()

    def _write_exe(self, name, content):
        path = self.bin / name
        path.write_text(content)
        path.chmod(0o755)

    def _write_fake_herdr(self):
        self._write_exe(
            "herdr",
            """#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
state=Path(os.environ['FAKE_HERDR_STATE'])
log=Path(os.environ['FAKE_HERDR_LOG'])
data=json.loads(state.read_text())
args=sys.argv[1:]
if args[:2] == ['pane','get']:
 if data.get('status_sequence'):
  data['status'] = data['status_sequence'].pop(0)
  state.write_text(json.dumps(data))
 if data.get('pending_gets', 0) > 0:
  data['pending_gets'] -= 1
  if data['pending_gets'] == 0: data['status'] = 'working'
  state.write_text(json.dumps(data))
 print(json.dumps({'result':{'pane':{
  'pane_id':args[2], 'agent':data.get('agent','hermes'), 'agent_status':data['status'],
  'cwd':data.get('cwd'), 'foreground_cwd':data.get('cwd'),
  'agent_session':{'value':data.get('session','session-1')}
 }}}))
elif args[:2] == ['pane','run']:
 with log.open('a') as f: f.write(json.dumps(args)+"\\n")
 if data.get('accept_run', True):
  if not data.get('ack_never', False):
   if data.get('accept_delay_gets', 0): data['pending_gets'] = data['accept_delay_gets']
   else: data['status']='working'
   state.write_text(json.dumps(data))
 else:
  print(json.dumps({'error':'rejected'})); sys.exit(1)
else:
 print(json.dumps({'error':'unexpected','args':args})); sys.exit(2)
""",
        )

    def _write_fake_bd(self):
        self._write_exe(
            "bd",
            """#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
data=json.loads(Path(os.environ['FAKE_BD_STATE']).read_text())
args=sys.argv[1:]
with Path(os.environ['FAKE_BD_LOG']).open('a') as f: f.write(json.dumps(args)+"\\n")
if 'ready' in args: print(json.dumps(data['ready']))
elif 'list' in args: print(json.dumps(data['tasks']))
else: print(json.dumps({'error':'unexpected','args':args})); sys.exit(2)
""",
        )

    def _env(self):
        env = os.environ.copy()
        env.update(
            PATH=f"{self.bin}:{env['PATH']}",
            FAKE_HERDR_STATE=str(self.herdr_state),
            FAKE_HERDR_LOG=str(self.herdr_log),
            FAKE_BD_STATE=str(self.bd_state),
            FAKE_BD_LOG=str(self.bd_log),
        )
        return env

    def _set_herdr(self, status="idle", **changes):
        data = {"status":status, "agent":"hermes", "cwd":str(self.repo), "session":"session-1"}
        data.update(changes)
        self.herdr_state.write_text(json.dumps(data))

    def _set_bd(self, ready=None, tasks=None):
        self.bd_state.write_text(json.dumps({"ready": ready or [], "tasks": tasks or []}))

    def _run(self, *extra, check=True):
        cmd = [
            "python3", str(SCRIPT), "--once", "--repo", str(self.repo),
            "--mission-id", "mission-1", "--pane", "w2N:p1",
            "--session-id", "session-1",
            "--state", str(self.state), "--proc-root", str(self.proc),
            "--min-repeat-seconds", "300", *extra,
        ]
        cp = subprocess.run(cmd, env=self._env(), text=True, capture_output=True)
        if check and cp.returncode != 0:
            self.fail(f"exit={cp.returncode}\nstdout={cp.stdout}\nstderr={cp.stderr}")
        payload = json.loads(cp.stdout.strip().splitlines()[-1]) if cp.stdout.strip() else {}
        return cp, payload

    def _fake_process(self, pid, argv, start_ticks=12345):
        p = self.proc / str(pid)
        p.mkdir()
        (p / "cmdline").write_bytes(b"\0".join(x.encode() for x in argv) + b"\0")
        # Field 2 may contain spaces; start ticks is field 22.
        fields = ["S"] + ["0"] * 18 + [str(start_ticks)] + ["0"] * 5
        (p / "stat").write_text(f"{pid} (fake process name) " + " ".join(fields))

    def _watcher_metadata(self, result_json, pane="w2N:p1", worker_pid=200, worker_start=12345):
        return {
            "result_json": result_json, "watcher_pid": 201, "watcher_start_ticks": 777,
            "process_pid": worker_pid, "process_start_ticks": worker_start,
            "completion_token": "a" * 32, "watcher_receipt": str(self.repo / ".hermes/conductor/watchers/task-1.json"),
            "conductor_pane": pane,
        }

    def _live_watcher(self, pane="w2N:p1", result_json=None, worker_pid=200, worker_start=12345):
        result_json = result_json or str(self.repo / ".hermes/conductor/results/task-1.json")
        receipt = str(self.repo / ".hermes/conductor/watchers/task-1.json")
        self._fake_process(worker_pid, ["python3", "worker.py"], worker_start)
        self._fake_process(201, [
            "python3", "watch_worker_completion.py", "--worker-pid", str(worker_pid),
            "--worker-start-ticks", str(worker_start), "--task-id", "task-1",
            "--result-json", result_json, "--conductor-pane", pane,
            "--marker-value", "a" * 32, "--receipt", receipt,
        ], 777)

    def test_idle_ready_frontier_is_submitted_and_verified(self):
        self._set_bd(ready=[{"id": "task-1", "status": "open"}])
        _, out = self._run()
        self.assertTrue(out["wakeDelivered"])
        self.assertEqual(out["reason"], "ready_without_live_watcher")
        logged = [json.loads(x) for x in self.herdr_log.read_text().splitlines()]
        self.assertEqual(logged[0][:3], ["pane", "run", "w2N:p1"])
        self.assertIn("reconcile", logged[0][3].lower())

    def test_working_controller_is_never_interrupted(self):
        self._set_herdr("working")
        self._set_bd(ready=[{"id": "task-1"}])
        _, out = self._run()
        self.assertFalse(out["wakeDelivered"])
        self.assertEqual(out["reason"], "controller_working")
        self.assertFalse(self.herdr_log.exists())

    def test_pane_agent_session_and_cwd_are_bound(self):
        cases = ({"agent":"codex"}, {"session":"other-session"}, {"cwd":str(self.root / "other")})
        for changes in cases:
            with self.subTest(changes=changes):
                self._set_herdr("idle", **changes)
                self._set_bd(ready=[{"id":"task-1"}])
                cp, out = self._run(check=False)
                self.assertNotEqual(cp.returncode, 0)
                self.assertFalse(out["wakeDelivered"])
                self.assertFalse(self.herdr_log.exists())

    def test_contract_mission_id_mismatch_fails_closed(self):
        contract = {"mission":{"status":"active"}, "ledger":{"missionId":"other-mission"}}
        (self.repo / ".hermes/conductor/mission.json").write_text(json.dumps(contract))
        self._set_bd(ready=[{"id":"task-1"}])
        cp, out = self._run(check=False)
        self.assertNotEqual(cp.returncode, 0)
        self.assertEqual(out["reason"], "watchdog_error")
        self.assertFalse(self.herdr_log.exists())

    def test_controller_is_revalidated_before_submission(self):
        self._set_herdr("idle", status_sequence=["idle", "working"])
        self._set_bd(ready=[{"id":"task-1"}])
        _, out = self._run()
        self.assertFalse(out["wakeDelivered"])
        self.assertEqual(out["reason"], "controller_changed_before_wake")
        self.assertFalse(self.herdr_log.exists())

    def test_complete_frontier_queries_disable_default_limits(self):
        self._set_bd(ready=[{"id":"task-1"}])
        self._run()
        calls = [json.loads(line) for line in self.bd_log.read_text().splitlines()]
        self.assertTrue(all("--limit" in call and call[call.index("--limit") + 1] == "0" for call in calls))

    def test_malformed_beads_json_shape_fails_closed(self):
        self.bd_state.write_text(json.dumps({"ready":{"unexpected":[]}, "tasks":[]}))
        cp, out = self._run(check=False)
        self.assertNotEqual(cp.returncode, 0)
        self.assertEqual(out["reason"], "watchdog_error")
        self.assertFalse(self.herdr_log.exists())

    def test_malformed_beads_task_entry_fails_closed(self):
        self.bd_state.write_text(json.dumps({"ready":[], "tasks":[{"status":"in_progress"}]}))
        cp, out = self._run(check=False)
        self.assertNotEqual(cp.returncode, 0)
        self.assertEqual(out["reason"], "watchdog_error")
        self.assertFalse(self.herdr_log.exists())

    def test_unreadable_proc_root_fails_closed(self):
        self._set_bd(tasks=[{"id":"task-1","status":"in_progress","metadata":{}}])
        cp, out = self._run("--proc-root", str(self.root / "missing-proc"), check=False)
        self.assertNotEqual(cp.returncode, 0)
        self.assertEqual(out["reason"], "watchdog_error")
        self.assertFalse(self.herdr_log.exists())

    def test_idle_with_qualified_live_watcher_waits_for_event(self):
        expected = ".hermes/conductor/results/task-1.json"
        self._set_bd(tasks=[{"id":"task-1","status":"in_progress","metadata":self._watcher_metadata(expected)}])
        self._live_watcher(result_json=str(self.repo / expected))
        _, out = self._run()
        self.assertFalse(out["wakeDelivered"])
        self.assertEqual(out["reason"], "productive_worker_has_live_wake")

    def test_ready_lane_wakes_even_while_another_worker_is_safely_watched(self):
        expected = ".hermes/conductor/results/task-1.json"
        self._set_bd(
            ready=[{"id":"task-2","status":"open"}],
            tasks=[
                {"id":"task-1","status":"in_progress","metadata":self._watcher_metadata(expected)},
                {"id":"task-2","status":"open","metadata":{}},
            ],
        )
        self._live_watcher(result_json=str(self.repo / expected))
        _, out = self._run()
        self.assertTrue(out["wakeDelivered"])
        self.assertEqual(out["reason"], "ready_without_live_watcher")
        self.assertEqual(out["ready"], ["task-2"])

    def test_stale_watcher_destination_wakes_controller(self):
        expected = ".hermes/conductor/results/task-1.json"
        self._set_bd(tasks=[{"id":"task-1","status":"in_progress","metadata":{"result_json":expected}}])
        self._live_watcher(pane="w1T:p1", result_json=str(self.repo / expected))
        _, out = self._run()
        self.assertTrue(out["wakeDelivered"])
        self.assertEqual(out["reason"], "in_progress_without_qualified_watcher")

    def test_result_path_mismatch_wakes_controller(self):
        expected = ".hermes/conductor/results/task-1.json"
        self._set_bd(tasks=[{"id":"task-1","status":"in_progress","metadata":{"result_json":expected}}])
        self._live_watcher(result_json=str(self.repo / "wrong/results/task-1.json"))
        _, out = self._run()
        self.assertTrue(out["wakeDelivered"])
        self.assertEqual(out["reason"], "in_progress_without_qualified_watcher")

    def test_dead_worker_makes_watcher_unqualified(self):
        expected = ".hermes/conductor/results/task-1.json"
        self._set_bd(tasks=[{"id":"task-1","status":"in_progress","metadata":{"result_json":expected}}])
        self._fake_process(201, [
            "python3", "watch_worker_completion.py", "--worker-pid", "999",
            "--worker-start-ticks", "12345", "--task-id", "task-1",
            "--result-json", str(self.repo / expected), "--conductor-pane", "w2N:p1",
            "--marker-value", "a" * 32,
            "--receipt", str(self.repo / ".hermes/conductor/watchers/task-1.json"),
        ], 777)
        _, out = self._run()
        self.assertTrue(out["wakeDelivered"])

    def test_spoofed_watcher_pid_does_not_qualify(self):
        expected = ".hermes/conductor/results/task-1.json"
        md = self._watcher_metadata(expected)
        md["watcher_pid"] = 999
        self._set_bd(tasks=[{"id":"task-1","status":"in_progress","metadata":md}])
        self._live_watcher(result_json=str(self.repo / expected))
        _, out = self._run()
        self.assertTrue(out["wakeDelivered"])
        self.assertEqual(out["reason"], "in_progress_without_qualified_watcher")

    def test_in_progress_without_watcher_wakes_even_when_ready_is_empty(self):
        self._set_bd(tasks=[{"id":"task-1","status":"in_progress","metadata":{}}])
        _, out = self._run()
        self.assertTrue(out["wakeDelivered"])
        self.assertEqual(out["reason"], "in_progress_without_qualified_watcher")

    def test_same_unchanged_frontier_is_rate_limited(self):
        self._set_bd(ready=[{"id":"task-1","status":"open"}])
        _, first = self._run()
        self.assertTrue(first["wakeDelivered"])
        self._set_herdr("idle")
        _, second = self._run()
        self.assertFalse(second["wakeDelivered"])
        self.assertEqual(second["reason"], "wake_rate_limited")

    def test_rate_limit_state_is_bound_to_mission_pane_session_and_version(self):
        self._set_bd(ready=[{"id":"task-1"}])
        self._run()
        saved = json.loads(self.state.read_text())
        self.assertEqual(saved["missionId"], "mission-1")
        self.assertEqual(saved["pane"], "w2N:p1")
        self.assertEqual(saved["sessionId"], "session-1")
        self.assertEqual(saved["version"], "1.5.0")
        saved["pane"] = "old:p1"
        self.state.write_text(json.dumps(saved))
        self._set_herdr("idle")
        _, out = self._run()
        self.assertTrue(out["wakeDelivered"])

    def test_malformed_rate_limit_timestamp_does_not_kill_wake(self):
        self._set_bd(ready=[{"id":"task-1"}])
        self._run()
        saved = json.loads(self.state.read_text())
        saved["lastWakeAt"] = "not-a-number"
        self.state.write_text(json.dumps(saved))
        self._set_herdr("idle")
        _, out = self._run()
        self.assertTrue(out["wakeDelivered"])

    def test_changed_frontier_bypasses_previous_fingerprint(self):
        self._set_bd(ready=[{"id":"task-1","status":"open"}])
        self._run()
        self._set_herdr("idle")
        self._set_bd(ready=[{"id":"task-2","status":"open"}])
        _, out = self._run()
        self.assertTrue(out["wakeDelivered"])

    def test_inactive_mission_never_wakes(self):
        (self.repo / ".hermes/conductor/mission.json").write_text(json.dumps({"mission":{"status":"complete"}}))
        self._set_bd(ready=[{"id":"task-1"}])
        _, out = self._run()
        self.assertFalse(out["wakeDelivered"])
        self.assertEqual(out["reason"], "mission_not_active")

    def test_missing_or_unknown_mission_status_fails_closed(self):
        for status in (None, "mystery"):
            mission = {"mission": {}}
            if status is not None:
                mission["mission"]["status"] = status
            (self.repo / ".hermes/conductor/mission.json").write_text(json.dumps(mission))
            self._set_bd(ready=[{"id":"task-1"}])
            _, out = self._run()
            self.assertFalse(out["wakeDelivered"])
        self.assertFalse(self.herdr_log.exists())

    def test_control_text_in_task_id_fails_before_herdr_submission(self):
        self._set_bd(ready=[{"id":"task-1\n/exit"}])
        cp, out = self._run(check=False)
        self.assertNotEqual(cp.returncode, 0)
        self.assertEqual(out["reason"], "watchdog_error")
        self.assertFalse(self.herdr_log.exists())

    def test_invalid_pane_fails_before_any_herdr_action(self):
        cp, _ = self._run("--pane", "w2N:p1;rm", check=False)
        self.assertNotEqual(cp.returncode, 0)
        self.assertFalse(self.herdr_log.exists())

    def test_invalid_mission_id_fails_before_any_herdr_action(self):
        cp, _ = self._run("--mission-id", "mission-1\n/exit", check=False)
        self.assertNotEqual(cp.returncode, 0)
        self.assertFalse(self.herdr_log.exists())

    def test_rejected_submission_is_failure_not_claimed_wake(self):
        self._set_herdr("idle", accept_run=False)
        self._set_bd(ready=[{"id":"task-1"}])
        cp, out = self._run(check=False)
        self.assertNotEqual(cp.returncode, 0)
        self.assertFalse(out.get("wakeDelivered", False))

    def test_successful_unacknowledged_submission_is_rate_limited(self):
        self._set_herdr("idle", ack_never=True)
        self._set_bd(ready=[{"id":"task-1"}])
        cp, first = self._run(check=False)
        self.assertNotEqual(cp.returncode, 0)
        self.assertEqual(first["reason"], "wake_not_acknowledged")
        self.assertTrue(self.state.exists())
        first_count = len(self.herdr_log.read_text().splitlines())
        self._set_herdr("idle", ack_never=True)
        _, second = self._run()
        self.assertEqual(second["reason"], "wake_rate_limited")
        self.assertEqual(len(self.herdr_log.read_text().splitlines()), first_count)

    def test_delayed_herdr_status_acknowledgement_is_polled(self):
        self._set_herdr("idle", accept_delay_gets=2)
        self._set_bd(ready=[{"id":"task-1"}])
        _, out = self._run()
        self.assertTrue(out["wakeDelivered"])
        self.assertEqual(out["controllerStatus"], "working")


class DaemonLoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("controller_idle_watchdog", SCRIPT)
        assert spec is not None and spec.loader is not None
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_daemon_retries_transient_error_instead_of_exiting(self):
        outcomes = iter([(1, {"reason":"watchdog_error"}), (0, {"reason":"controller_working"})])
        sleeps = []

        class Args:
            once = False
            interval_seconds = 0.01

        code = self.module.run_loop(
            Args(), evaluate=lambda _args: next(outcomes), sleeper=sleeps.append, max_iterations=2
        )
        self.assertEqual(code, 0)
        self.assertEqual(sleeps, [0.01])

    def test_terminal_mission_stops_daemon_without_sleep(self):
        sleeps = []

        class Args:
            once = False
            interval_seconds = 30

        code = self.module.run_loop(
            Args(), evaluate=lambda _args: (0, {"reason":"mission_not_active"}), sleeper=sleeps.append
        )
        self.assertEqual(code, 0)
        self.assertEqual(sleeps, [])

    def test_duplicate_watchdog_lock_fails_immediately(self):
        with tempfile.TemporaryDirectory(prefix="conductor-watchdog-lock-") as tmp:
            repo = Path(tmp)
            (repo / ".hermes" / "conductor").mkdir(parents=True)
            first = self.module.acquire_instance_lock(repo, "mission-1")
            try:
                with self.assertRaises(RuntimeError):
                    self.module.acquire_instance_lock(repo, "mission-1")
            finally:
                os.close(first)

    def test_external_commands_have_a_timeout(self):
        response = mock.Mock(returncode=0, stdout="{}", stderr="")
        with mock.patch.object(self.module.subprocess, "run", return_value=response) as run:
            self.module.run_json(["tool", "arg"])
        self.assertEqual(run.call_args.kwargs["timeout"], self.module.COMMAND_TIMEOUT_SECONDS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
