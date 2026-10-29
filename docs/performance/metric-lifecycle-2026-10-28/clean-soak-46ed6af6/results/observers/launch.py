"""Owned invocation of the committed qualification harness."""
import argparse, json, os, runpy, sys, time, subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--phase',choices=['preflight','sustained'],required=True);p.add_argument('--attempt',type=int,default=1);a=p.parse_args()
s=Path(__file__).resolve().parent
root=Path('/home/oracle-worker/Work/starlink-dashboard/.worktrees/issue-393-clean-soak')
name=f'{a.phase}-{a.attempt:03d}';out=s/name;project='starlink-operator-issue393-clean-'+name
assert a.attempt>0 and not out.exists()
harness=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
record={'pid':os.getpid(),'pgid':os.getpgrp(),'started':time.time(),'phase':a.phase,'candidate_sha':'46ed6af6d431cd7fac8633a9f3d829d5fc24d831','harness_sha':harness,'project':project,'output':str(out),'warmup_seconds':120,'duration_seconds':120 if a.phase=='preflight' else 3620}
(s/(name+'-runner.json')).write_text(json.dumps(record,indent=2)+'\n')
os.environ['PERF_BROWSER_EXECUTABLE']='/srv/starlink-acceptance/browser-store/chromium-1243/chrome-linux64/chrome'
os.environ['PERF_CAPTURE_PROBES']='1' if a.phase=='preflight' else'0'
script=root/'tools/acceptance/performance/run.py'
sys.path.insert(0,str(script.parent))
sys.argv=[str(script),'--sha',record['candidate_sha'],'--project',project,'--output',str(out),'--viewers','1','--operator','--fullscreen','--operations','--window','1800','--warmup','120','--duration',str(record['duration_seconds']),'--instrumentation','off','--total-timeout','1200' if a.phase=='preflight' else'5400']
try:
 runpy.run_path(str(script),run_name='__main__')
 record['exit_code']=0
except BaseException as error:
 record['exit_code']=1;record['exception_type']=type(error).__name__;raise
finally:
 record['ended']=time.time();(s/(name+'-runner.json')).write_text(json.dumps(record,indent=2)+'\n')
