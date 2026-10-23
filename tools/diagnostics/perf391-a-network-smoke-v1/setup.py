"""Recreate only the approved private interpreter dependencies and record ownership."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request
import zipfile

HERE = Path(__file__).resolve().parent
PINNED = HERE.with_name('perf391-python-preflight-v1')
TASK = Path('/tmp/perf391-a-network-smoke')
E = HERE / 'evidence'
assert not TASK.exists()
ownership = {'task': TASK.name, 'scratch': str(TASK), 'pid': os.getpid(), 'pgid': os.getpgid(0), 'start_id': Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19], 'utc': time.strftime('%FT%TZ',time.gmtime()), 'project': 'perf391-smoke-408-a', 'runtime': '/tmp/perf391-smoke-408-a', 'lock': '/tmp/perf391-smoke-408.lock', 'ports': list(range(38080,38084)), 'private_volumes': ['perf391-smoke-408-a_prometheus_data','perf391-smoke-408-a_starlink_data'], 'cleanup': 'approved executor finally, independent host audit, scoped recorded scratch removal'}
(E/'ownership.json').write_text(json.dumps(ownership,indent=2)+'\n')
TASK.mkdir()
(TASK/'ownership.json').write_text(json.dumps(ownership,indent=2)+'\n')
(TASK/'wheels').mkdir()
rows=json.loads((PINNED/'evidence/wheels.json').read_text())
for row in rows:
    blob=urllib.request.urlopen(row['url'],timeout=30).read()
    assert hashlib.sha256(blob).hexdigest()==row['sha256']
    (TASK/'wheels'/row['filename']).write_bytes(blob)
(E/'wheels.json').write_text(json.dumps(rows,indent=2)+'\n')
env={k:v for k,v in os.environ.items() if k!='PYTHONPATH'}
env.update(PYTHONNOUSERSITE='1', UV_CACHE_DIR=str(TASK/'uv-cache'))
python=Path('/home/oracle-worker/.local/share/uv/python/cpython-3.11.16-linux-x86_64-gnu/bin/python3.11')
def run(argv):
    subprocess.run(argv,env=env,check=True,timeout=60)
run(['uv','venv','--python',str(python),str(TASK/'venv')])
private=str(TASK/'venv/bin/python')
run(['uv','pip','sync','--python',private,'--offline','--no-index','--find-links',str(TASK/'wheels'),'--require-hashes','--only-binary',':all:',str(PINNED/'requirements.lock')])
with (E/'environment.json').open('w') as out:
    subprocess.run([private,'-B',str(PINNED/'verify-environment.py')],env=env,stdout=out,check=True,timeout=30)
with (E/'dependency-check.log').open('w') as out:
    subprocess.run(['uv','pip','check','--python',private],env=env,stdout=out,stderr=subprocess.STDOUT,check=True,timeout=30)
payload_script='''import importlib.metadata as m, pathlib, zipfile, json
root=pathlib.Path('/tmp/perf391-a-network-smoke/wheels')
rows=json.loads(pathlib.Path('tools/diagnostics/perf391-a-network-smoke-v1/evidence/wheels.json').read_text())
for row in rows:
 d=m.distribution(row['name'])
 with zipfile.ZipFile(root/row['filename']) as z:
  for f in d.files:
   s=str(f)
   if s in z.namelist() and not s.endswith('/RECORD'): assert d.locate_file(f).read_bytes()==z.read(s),s
print('PASS: all six installed wheel payloads match pinned archives')
'''
run([private,'-B','-c',payload_script])
print('PASS_PRIVATE_ENVIRONMENT')
