import json,os,signal,subprocess,time
from pathlib import Path
root=Path.cwd(); evidence=root/'tools/diagnostics/perf391-diagnostic-integration-v1/evidence/correction'
node=str(Path('/home/oracle-worker/.local/bin/node'))
base={'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':str(root/'tools/diagnostics/perf391-runtime-preparation-v1'),'PERF391_CORRECTION_EXECUTOR_EVIDENCE':str(evidence/'executor')}
commands=[('python-focused',[str(root/'.venv/bin/python'),'-B','-m','unittest','test_executor','test_node_identity'],{}),('node-focused',[node,'--test','--experimental-test-isolation=none','tools/diagnostics/perf391-diagnostic-integration-v1/tests/browser.test.mjs','tools/diagnostics/perf391-diagnostic-integration-v1/tests/collection.test.mjs'],{}),('authentic-final',[node,'node_modules/vitest/vitest.mjs','run','--config','tools/diagnostics/perf391-diagnostic-integration-v1/tests/frontend/vitest.config.mjs','tests/frontend/probe.test.ts'],{'PERF391_CORRECTION_EVIDENCE':str(evidence/'authentic')})]
for role in ('A','C'):
 commands.append(('frontend-'+role+'-qualified',[node,'node_modules/vitest/vitest.mjs','run','--config','tools/diagnostics/perf391-diagnostic-integration-v1/tests/frontend/vitest.config.mjs','tests/frontend/application.test.tsx','tests/frontend/request.test.tsx'],{'PERF391_FRONTEND_ROOT':str(root/'tools/diagnostics/perf391-diagnostic-integration-v1/artifacts/correction-roles'/(role+'-effective')/'frontend/mission-planner')}))
ledger={'kind':'offline-only; every Docker/browser argv in executor tests is replaced by fake Python commands','runner_pid':os.getpid(),'runner_pgid':os.getpgid(0),'runs':[]}; current=None
path=evidence/'qualification-processes.json'
def save(): path.write_text(json.dumps(ledger,indent=2)+'\n')
def interrupt(sig,frame):
 if current is not None and current.poll() is None: os.killpg(current.pid,signal.SIGTERM)
 raise KeyboardInterrupt
signal.signal(signal.SIGINT,interrupt);signal.signal(signal.SIGTERM,interrupt)
save()
for name,argv,env in commands:
 record={'name':name,'argv':argv,'timeout_seconds':90,'kill_grace_seconds':5,'intent_before_spawn':True};ledger['runs'].append(record);save()
 began=time.monotonic()
 with (evidence/(name+'.log')).open('w') as output:
  current=subprocess.Popen(argv,stdout=output,stderr=subprocess.STDOUT,env={**os.environ,**base,**env},start_new_session=True)
  record.update(pid=current.pid,pgid=os.getpgid(current.pid),start_id=Path(f'/proc/{current.pid}/stat').read_text().rsplit(')',1)[1].split()[19]);save()
  try: current.wait(timeout=90)
  except BaseException:
   if current.poll() is None:
    os.killpg(current.pid,signal.SIGTERM)
    try: current.wait(timeout=5)
    except subprocess.TimeoutExpired: os.killpg(current.pid,signal.SIGKILL);current.wait()
   record['interrupted']=True
   raise
  finally:
   record.update(returncode=current.poll(),elapsed_seconds=round(time.monotonic()-began,3),reaped=current.poll() is not None)
   save()
 if current.returncode:
  print(name,'FAIL',flush=True);raise SystemExit(current.returncode)
 print(name,'PASS',flush=True)
current=None
ledger['complete']=True;save()
