"""One authorized corrected-A attempt through the unchanged bound executor."""
import asyncio,json,os,shutil,signal,subprocess,sys,time
from pathlib import Path
from types import SimpleNamespace
HERE=Path(__file__).resolve().parent;E=HERE/'evidence/completed-a'
AUTH='https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6373144033'
def write(p,v):p.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
def stop(sig,frame):raise SystemExit(128+sig)
for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,stop)
if len(sys.argv)>1 and sys.argv[1]=='execute-once':
 sys.path.insert(0,str(HERE.with_name('perf391-corrected-a-runtime-v2')))
 from binding import bound_executor,PLAN,RECEIPT,TASK,verify_binding,prepare,PREP
 verify_binding();module=bound_executor()
 assert Path(module.execute.__code__.co_filename).resolve()==PREP/'execute.proposed.py'
 args=SimpleNamespace(launch_plan=E/'launch-A.json',build_plan=PLAN,receipt=RECEIPT,node=TASK/'backend/node',authorization=AUTH)
 write(E/'activation.json',{'factory':'binding.bound_executor','executor_sha256':prepare.sha(PREP/'execute.proposed.py'),'binding_sha256':prepare.sha(HERE.with_name('perf391-corrected-a-runtime-v2')/'binding.py'),'authorization':AUTH,'A_invocations':1,'C_invocations':0,'pid':os.getpid(),'pgid':os.getpgrp(),'start_identity':Path('/proc/self/stat').read_text()})
 asyncio.run(module.execute(args));sys.exit(0)
# Supervising runner: bounded child groups; always preserve evidence before removal.
python='/tmp/perf391-corrected-a-smoke-20261023/venv/bin/python'
active=None;ledger=json.loads((E/'supervisor.json').read_bytes()) if any(flag in sys.argv for flag in ('--continue-owner','--continue-activation')) else []
def run(argv,seconds,name):
 global active
 row={'argv':list(map(str,argv)),'seconds':seconds,'grace_seconds':10};ledger.append(row)
 # Preparation creates the evidence directory before any resource allocation.
 with (HERE/(name+'.supervisor.log')).open('wb') as f:
  active=subprocess.Popen(['timeout','--kill-after=10s',str(seconds)+'s',*map(str,argv)],stdout=f,stderr=subprocess.STDOUT,start_new_session=True,env={**{k:v for k,v in os.environ.items() if k!='PYTHONPATH'},'PYTHONNOUSERSITE':'1','PYTHONDONTWRITEBYTECODE':'1'})
  row.update(pid=active.pid,pgid=os.getpgid(active.pid),start_identity=Path('/proc',str(active.pid),'stat').read_text())
  while not E.exists() and active.poll() is None:time.sleep(.02)
  if E.exists():write(E/'supervisor.json',ledger)
  try:rc=active.wait()
  finally:
   if active.poll() is None:
    os.killpg(active.pid,signal.SIGTERM)
    try:active.wait(timeout=10)
    except subprocess.TimeoutExpired:os.killpg(active.pid,signal.SIGKILL);active.wait()
  row['exit']=rc;active=None
  if E.exists():write(E/'supervisor.json',ledger)
 return rc
status={}
try:
 if any(flag in sys.argv for flag in ('--continue-owner','--continue-activation')):
  shutil.copyfile(E/'supervisor-outcome.json',E/('supervisor-before-activation.json' if '--continue-activation' in sys.argv else 'supervisor-before-owner.json'))
  status['setup_exit']=0
  status['owner_continuation_exit']=run([python,'-B',HERE/'preflight-checks.py',('--continue-activation' if '--continue-activation' in sys.argv else '--continue-owner')],60,('activation-continuation' if '--continue-activation' in sys.argv else 'owner-continuation'))
  status['preflight_exit']=status['owner_continuation_exit']
 else:
  status['setup_exit']=run([sys.executable,'-B',HERE/'prepare-environment.py'],240,'setup')
  assert status['setup_exit']==0,'private dependency setup failed'
  status['preflight_exit']=run([python,'-B',HERE/'preflight-checks.py'],600,'preflight')
 assert status['preflight_exit']==0,'substantive preflight failure'
 status['runtime_exit']=run([python,'-B',__file__,'execute-once'],90,'runtime')
 status['result']='RUNTIME_FINISHED' if status['runtime_exit']==0 else 'STOP_RUNTIME_FAILURE'
except BaseException as error:
 status.update(result='STOP',error=type(error).__name__+': '+str(error))
finally:
 if E.exists():
  root=Path('/tmp/perf391-smoke-408-a')
  if root.exists():
   shutil.copytree(root,E/'runtime',symlinks=True)
  write(E/'supervisor-outcome.json',status)
  for name in ('setup','preflight','owner-continuation','activation-continuation','runtime'):
   log=HERE/(name+'.supervisor.log')
   if log.exists():shutil.move(log,E/log.name)
print(json.dumps(status))
