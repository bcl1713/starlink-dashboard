"""Bounded Forge-host prerequisite, not a rerun of the two timed-out tests."""
import asyncio, ctypes, json, os, signal, subprocess, sys, time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.with_name('perf391-diagnostic-integration-v1')))
from owner import Owner, start_id, members
E=HERE/'evidence'
assert Path('/proc/1/comm').read_text().strip()=='systemd'
report={'pid':os.getpid(),'pgid':os.getpgrp(),'start_id':start_id(os.getpid()),'namespace':os.readlink('/proc/self/ns/pid'),'utc_ns':time.time_ns(),'status':'intent','old_timeout_tests':'both timed out, not passing','runtime_started':False}
(E/'process-prerequisite.json').write_text(json.dumps(report,indent=2)+'\n')
assert ctypes.CDLL(None).prctl(36,1,0,0,0)==0
async def main():
 owner=Owner(E/'process-prerequisite-owner',run='synthetic-network-preflight',sources={},adopt_descendants=True)
 child=None
 def stop(sig,frame):raise SystemExit(128+sig)
 signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
 try:
  child=owner.spawn([sys.executable,'-c','import time; time.sleep(30)'])
  report['child']={'pid':child.pid,'pgid':os.getpgid(child.pid),'start_id':start_id(child.pid)}
  (E/'process-prerequisite.json').write_text(json.dumps(report,indent=2)+'\n')
 finally:
  result=await owner.close()
 assert child.returncode is not None and result['status']=='clean' and not members(child.pid)
 report.update(status='PASS',child_reaped=True,process_group_absent=True,owner_status=result['status'])
 (E/'process-prerequisite.json').write_text(json.dumps(report,indent=2)+'\n')
asyncio.run(main())
print('PASS host process ownership, TERM termination, reaping, group removal, subreaper capability')
