"""One invocation of the unchanged approved A executor; no retry path."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
E=HERE/'evidence'
PREP=HERE.with_name('perf391-runtime-preparation-v1')
BUILT=HERE.with_name('perf391-built-images-v1')
TASK=Path('/tmp/perf391-a-private-smoke')
assert json.loads((E/'preflight.json').read_text())['status']=='PASS_PREFLIGHT_NO_RUNTIME_STARTED'
assert not (E/'execution-intent.json').exists()
assert not os.environ.get('PYTHONPATH')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
env={**os.environ,'PYTHONNOUSERSITE':'1'}
plan=TASK/'context/original-build-plan.json'
receipt=BUILT/'evidence/built-A.json'
launcher=[sys.executable,'-B',str(PREP/'launcher.py'),'--role','A','--plan',str(plan),'--receipt',str(receipt),'--root','/tmp/perf391-smoke-408-a']
with (E/'executor-launch-A.json').open('w') as out:
    subprocess.run(launcher,stdout=out,env=env,check=True,timeout=15)
argv=['timeout','--kill-after=10s','90s',sys.executable,'-B',str(PREP/'execute.proposed.py'),'--launch-plan',str(E/'executor-launch-A.json'),'--build-plan',str(plan),'--receipt',str(receipt),'--node',str(TASK/'node-22.22.2'),'--authorization','https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6363470295','--execute']
intent={'utc':time.strftime('%FT%TZ',time.gmtime()),'runtime_attempts':1,'C_executions':0,'argv':argv,'supervisor_pid':os.getpid(),'supervisor_pgid':os.getpgid(0),'supervisor_start_id':Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19],'executor_sha256':sha(PREP/'execute.proposed.py'),'launcher_sha256':sha(PREP/'launcher.py'),'launch_sha256':sha(E/'executor-launch-A.json'),'deadlines':{'work_seconds':78,'outer_timeout_seconds':90,'kill_grace_seconds':10},'note':'Exact unchanged launcher output; two-layer provenance retained separately in preflight.'}
(E/'execution-intent.json').write_text(json.dumps(intent,indent=2)+'\n')
with (E/'executor.log').open('w') as out:
    child=subprocess.Popen(argv,stdout=out,stderr=subprocess.STDOUT,env=env,start_new_session=True)
    intent['timeout_pid']=child.pid
    intent['timeout_pgid']=child.pid
    (E/'execution-intent.json').write_text(json.dumps(intent,indent=2)+'\n')
    rc=child.wait()
(E/'execution-exit.json').write_text(json.dumps({'exit_code':rc,'utc':time.strftime('%FT%TZ',time.gmtime()),'A_invocations':1,'C_invocations':0},indent=2)+'\n')
print('A executor exit:',rc)
raise SystemExit(rc)
