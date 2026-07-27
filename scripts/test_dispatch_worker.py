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
 # --- TUI harness (omp/droid) dispatch ---
 def _fake_herdr(self, state):
  path=self.root/'fake-herdr'; path.write_text('#!/usr/bin/env python3\nimport json,os,pathlib,sys\nstate=pathlib.Path(os.environ["FAKE_HERDR_STATE"]); logp=pathlib.Path(os.environ["FAKE_HERDR_LOG"])\ndata=json.loads(state.read_text()); args=sys.argv[1:]\nrows=json.loads(logp.read_text()) if logp.exists() else []; rows.append(args); logp.write_text(json.dumps(rows))\nif args[:2]==["pane","get"]:\n pane={"pane_id":args[2],"cwd":data.get("cwd"),"foreground_cwd":data.get("cwd")}\n if data.get("agent"): pane["agent"]=data["agent"]\n if data.get("status"): pane["agent_status"]=data["status"]\n print(json.dumps({"result":{"pane":pane}}))\nelif args[:2]==["pane","run"]:\n data["agent"]=data.get("run_agent","omp"); state.write_text(json.dumps(data)); print(json.dumps({"result":{"type":"ok"}}))\nelif args[:2] in (["pane","send-text"],["pane","send-keys"]):\n if args[:2]==["pane","send-keys"] and data.get("working_after_enter"): data["status"]="working"; state.write_text(json.dumps(data))\n print(json.dumps({"result":{"type":"ok"}}))\nelse: print(json.dumps({"error":"unsupported"})); sys.exit(2)\n'); path.chmod(0o755); self.state_path=self.root/'herdr-state.json'; self.state_path.write_text(json.dumps(state)); self.herdr_log=self.root/'herdr-log.json'; return str(path)
 def _fake_proc(self, pid, argv, cwd, ticks):
  p=self.root/'proc'/str(pid); p.mkdir(parents=True, exist_ok=True); (p/'cmdline').write_bytes(b'\0'.join(x.encode() for x in argv)+b'\0'); os.symlink(str(cwd), str(p/'cwd')); (p/'stat').write_text(f'{pid} (fake) ' + ' '.join(['S']+['0']*18+[str(ticks)]+['0']*5))
 def _fake_watcher(self):
  path=self.root/'fake-watcher.py'; path.write_text('#!/usr/bin/env python3\nimport json,os,sys,time\nout=os.environ.get("FAKE_WATCHER_ARGV")\nif out: open(out,"w").write(json.dumps(sys.argv))\ntime.sleep(20)\n'); return str(path)
 def test_tui_dispatch_verifies_launch_and_attaches_pane_aware_watcher(self):
  harness_bin=str(self.bin/'omp')
  herdr=self._fake_herdr({'cwd':str(self.worktree),'run_agent':'omp','working_after_enter':True})
  self._fake_proc(4242, ['bun', harness_bin], self.worktree, 999)
  argv_out=self.root/'watcher-argv.json'
  env=os.environ.copy(); env['FAKE_HERDR_STATE']=str(self.state_path); env['FAKE_HERDR_LOG']=str(self.herdr_log); env['FAKE_WATCHER_ARGV']=str(argv_out)
  cp=subprocess.run(self.cmd(harness='omp', worker_pane='w8:p1', harness_bin=harness_bin, watcher_script=self._fake_watcher(), proc_root=str(self.root/'proc'), launch_verify_seconds='10', herdr_bin=herdr), capture_output=True, text=True, env=env)
  self.assertEqual(cp.returncode, 0, cp.stderr)
  d=json.loads(cp.stdout)
  self.assertEqual(d['harness'], 'omp'); self.assertEqual(d['workerPane'], 'w8:p1')
  self.assertEqual(d['launcherPid'], 4242); self.assertEqual(d['beadsMetadata']['process_pid'], 4242)
  self.assertEqual(d['beadsMetadata']['worker_pane'], 'w8:p1')
  argv=json.loads(argv_out.read_text())
  self.assertIn('--worker-pane', argv); self.assertEqual(argv[argv.index('--worker-pane')+1], 'w8:p1')
  self.assertEqual(argv[argv.index('--worker-pid')+1], '4242'); self.assertIn('--idle-after-seconds', argv)
  calls=json.loads(self.herdr_log.read_text())
  self.assertIn(['pane','run','w8:p1',harness_bin], calls)
  send_texts=[c for c in calls if c[:2]==['pane','send-text']]
  self.assertEqual(len(send_texts), 1); self.assertIn('result=', send_texts[0][3]); self.assertNotIn('{{COMPLETION_TOKEN}}', send_texts[0][3])
  self.assertIn(['pane','send-keys','w8:p1','ENTER'], calls)
  os.kill(d['watcherPid'], 15)
 def test_tui_launch_not_verified_fails_closed(self):
  harness_bin=str(self.bin/'omp')
  herdr=self._fake_herdr({'cwd':str(self.worktree)})  # no agent, never working
  (self.root/'proc').mkdir(exist_ok=True)
  env=os.environ.copy(); env['FAKE_HERDR_STATE']=str(self.state_path); env['FAKE_HERDR_LOG']=str(self.herdr_log)
  cp=subprocess.run(self.cmd(harness='omp', worker_pane='w8:p1', harness_bin=harness_bin, proc_root=str(self.root/'proc'), launch_verify_seconds='1', herdr_bin=herdr), capture_output=True, text=True, env=env)
  self.assertEqual(cp.returncode, 2); self.assertIn('not verified', cp.stderr); self.assertEqual(cp.stdout.strip(), '')
 def test_tui_requires_worker_pane(self):
  cp=subprocess.run(self.cmd(harness='omp', harness_bin=str(self.bin/'omp')), capture_output=True, text=True)
  self.assertEqual(cp.returncode, 2); self.assertIn('worker-pane', cp.stderr)
 def test_hermes_forbids_worker_pane(self):
  cp=subprocess.run(self.cmd(worker_pane='w8:p1'), capture_output=True, text=True)
  self.assertEqual(cp.returncode, 2); self.assertIn('headless', cp.stderr)
 def test_tui_busy_pane_fails_closed(self):
  herdr=self._fake_herdr({'cwd':str(self.worktree), 'status':'working'})
  env=os.environ.copy(); env['FAKE_HERDR_STATE']=str(self.state_path); env['FAKE_HERDR_LOG']=str(self.herdr_log)
  cp=subprocess.run(self.cmd(harness='omp', worker_pane='w8:p1', harness_bin=str(self.bin/'omp'), herdr_bin=herdr), capture_output=True, text=True, env=env)
  self.assertEqual(cp.returncode, 2); self.assertIn('already busy', cp.stderr)
 def test_tui_ambiguous_worker_processes_fail_closed(self):
  harness_bin=str(self.bin/'omp')
  herdr=self._fake_herdr({'cwd':str(self.worktree),'working_after_enter':True})
  self._fake_proc(4242, ['bun', harness_bin], self.worktree, 999)
  self._fake_proc(4243, [harness_bin], self.worktree, 998)
  env=os.environ.copy(); env['FAKE_HERDR_STATE']=str(self.state_path); env['FAKE_HERDR_LOG']=str(self.herdr_log)
  cp=subprocess.run(self.cmd(harness='omp', worker_pane='w8:p1', harness_bin=harness_bin, proc_root=str(self.root/'proc'), launch_verify_seconds='5', herdr_bin=herdr), capture_output=True, text=True, env=env)
  self.assertEqual(cp.returncode, 2); self.assertIn('ambiguous', cp.stderr)
if __name__=='__main__': unittest.main()
