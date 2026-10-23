"""Private dependency preparation only. No application or browser activation."""
import hashlib, json, os, signal, subprocess, time, urllib.request, zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
E=HERE/'evidence'
TASK=Path('/tmp/perf391-corrected-a-smoke-20261023')
PINNED=HERE.with_name('perf391-python-preflight-v1')
def write(p,v): p.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
assert not TASK.exists()
row={'pid':os.getpid(),'pgid':os.getpgrp(),'start_identity':Path('/proc/self/stat').read_text(),'temporary_root':str(TASK),'context_root':'/tmp/perf391-corrected-a-preflight','runtime_root':'/tmp/perf391-smoke-408-a','lock':'/tmp/perf391-smoke-408.lock','compose_project':'perf391-smoke-408-a','ports':[38080,38081,38082,38083],'volumes':['perf391-smoke-408-a_data','perf391-smoke-408-a_routes','perf391-smoke-408-a_metrics'],'extraction_containers':['perf391-corrected-a-preflight-frontend','perf391-corrected-a-preflight-backend','perf391-smoke-408-a-assets'],'utc':time.strftime('%FT%TZ',time.gmtime()),'commands':[]}
write(E/'preparation-ownership.json',row)
TASK.mkdir(); (TASK/'wheels').mkdir()
active=None
def stop(sig,frame):raise SystemExit(128+sig)
for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,stop)
def run(argv):
 global active
 item={'argv':list(map(str,argv)),'state':'intent'};row['commands'].append(item);write(E/'preparation-ownership.json',row)
 with (E/('dependency-command-%02d.log'%len(row['commands']))).open('wb') as f:
  active=subprocess.Popen(['timeout','--kill-after=10s','60s',*map(str,argv)],env=env,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
  item.update(pid=active.pid,pgid=os.getpgid(active.pid),start_identity=Path('/proc',str(active.pid),'stat').read_text(),state='running');write(E/'preparation-ownership.json',row)
  try:rc=active.wait()
  finally:
   if active.poll() is None:
    os.killpg(active.pid,signal.SIGTERM)
    try:active.wait(timeout=10)
    except subprocess.TimeoutExpired:os.killpg(active.pid,signal.SIGKILL);active.wait()
  item.update(exit=rc,state='exited');write(E/'preparation-ownership.json',row);active=None
  assert rc==0,item
rows=json.loads((PINNED/'evidence/wheels.json').read_bytes())
for wheel in rows:
 blob=urllib.request.urlopen(wheel['url'],timeout=30).read()
 assert hashlib.sha256(blob).hexdigest()==wheel['sha256']
 (TASK/'wheels'/wheel['filename']).write_bytes(blob)
write(E/'wheels.json',rows)
env={k:v for k,v in os.environ.items() if k!='PYTHONPATH'};env.update(PYTHONNOUSERSITE='1',PYTHONDONTWRITEBYTECODE='1',UV_CACHE_DIR=str(TASK/'uv-cache'))
python=Path('/home/oracle-worker/.local/share/uv/python/cpython-3.11.16-linux-x86_64-gnu/bin/python3.11')
assert python.exists()
run(['uv','venv','--python',python,TASK/'venv'])
run(['uv','pip','sync','--python',TASK/'venv/bin/python','--offline','--no-index','--find-links',TASK/'wheels','--require-hashes','--only-binary',':all:',PINNED/'requirements.lock'])
run([TASK/'venv/bin/python','-B',PINNED/'verify-environment.py'])
run(['uv','pip','check','--python',TASK/'venv/bin/python'])
run([TASK/'venv/bin/python','-B','-c',f'''import importlib.metadata as m,json,zipfile
from pathlib import Path
for row in json.loads(Path({str(E/'wheels.json')!r}).read_bytes()):
 d=m.distribution(row['name'])
 with zipfile.ZipFile(Path({str(TASK/'wheels')!r})/row['filename']) as z:
  for f in d.files:
   s=str(f)
   if s in z.namelist() and not s.endswith('/RECORD'):assert d.locate_file(f).read_bytes()==z.read(s),s
print('PASS: all six installed payloads match pinned wheel archives')'''])
print('PASS_PRIVATE_ENVIRONMENT')
