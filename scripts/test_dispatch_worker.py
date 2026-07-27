#!/usr/bin/env python3
from __future__ import annotations
import json, os, subprocess, sys, tempfile, time, unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
SCRIPT=HERE/'dispatch_worker.py'

class DispatchWorkerTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); self.repo=self.root/'repo'; self.repo.mkdir(); self.worktree=self.repo/'wt'; self.worktree.mkdir(); self.bin=self.root/'bin'; self.bin.mkdir(); self.result=self.root/'result.json'; self.receipt=self.root/'receipt.json'; self.brief=self.root/'brief.txt'; self.brief.write_text('token={{COMPLETION_TOKEN}} result={{RESULT_JSON}}')
  hermes=self.bin/'hermes'; hermes.write_text('#!/usr/bin/env python3\nimport time; time.sleep(5)\n'); hermes.chmod(0o755)
 def tearDown(self): self.tmp.cleanup()
 def cmd(self, **override):
  data={'repo':str(self.repo),'worktree':str(self.worktree),'task_id':'task-1','role':'task','provider':'omp','model':'cursor/composer-2.5','brief_file':str(self.brief),'base_sha':'abc123','conductor_pane':'w2X:p1','conductor_session':'session-1','result_json':str(self.result),'receipt':str(self.receipt),'dispatch_dir':str(self.root/'dispatch'),'hermes_bin':str(self.bin/'hermes'),'herdr_bin':'false','timeout_seconds':'60'}; data.update(override); out=[sys.executable,str(SCRIPT)];
  for k,v in data.items(): out += ['--'+k.replace('_','-'),str(v)]
  return out
 def test_launches_stable_waiter_and_qualified_watcher_record(self):
  cp=subprocess.run(self.cmd(),capture_output=True,text=True); self.assertEqual(cp.returncode,0,cp.stderr); d=json.loads(cp.stdout); self.assertRegex(d['completionToken'],r'^[0-9a-f]{32}$'); self.assertEqual(d['requestedProvider'],'omp'); self.assertEqual(d['beadsMetadata']['conductor_session'],'session-1');
  self.assertTrue(Path(f"/proc/{d['launcherPid']}").exists()); self.assertTrue(Path(f"/proc/{d['watcherPid']}").exists());
  os.kill(d['launcherPid'],15); os.kill(d['watcherPid'],15)
 def test_existing_result_fails_before_launch(self):
  self.result.write_text('{}'); cp=subprocess.run(self.cmd(),capture_output=True,text=True); self.assertNotEqual(cp.returncode,0); self.assertIn('already exists',cp.stderr)
 def test_relative_result_fails_before_launch(self):
  cp=subprocess.run(self.cmd(result_json='relative.json'),capture_output=True,text=True); self.assertNotEqual(cp.returncode,0); self.assertIn('absolute',cp.stderr)
 def test_immediate_launcher_exit_fails_without_record(self):
  (self.bin/'hermes').write_text('#!/usr/bin/env python3\nraise SystemExit(1)\n'); cp=subprocess.run(self.cmd(),capture_output=True,text=True); self.assertNotEqual(cp.returncode,0); self.assertIn('launcher failed',cp.stderr)
if __name__=='__main__': unittest.main()
