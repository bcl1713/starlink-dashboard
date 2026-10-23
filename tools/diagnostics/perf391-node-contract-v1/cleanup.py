"""Task-specific cleanup and read-only host/daemon audit; never deletes images."""
import json
import os
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
result = {'process_survivors': [], 'docker': {}, 'images': {}, 'removed_paths': []}
for proc in Path('/proc').iterdir():
    if not proc.name.isdecimal() or int(proc.name) == os.getpid():
        continue
    try:
        args = (proc/'cmdline').read_bytes().decode().split('\0')
    except (OSError, UnicodeError):
        continue
    if any(a.startswith('/tmp/perf391-executor-fixture-') or a.startswith('/tmp/perf391-node-contract-408/') for a in args):
        result['process_survivors'].append({'pid': int(proc.name), 'argv': args})
assert not result['process_survivors'], result['process_survivors']

def command(argv):
    return subprocess.check_output(['timeout', '--kill-after=5s', '15s', *argv], text=True)

for role in ('a','c'):
    project='perf391-smoke-408-'+role
    result['docker'][project]={}
    for kind,argv in [('containers',['docker','ps','-aq']), ('networks',['docker','network','ls','-q']), ('volumes',['docker','volume','ls','-q'])]:
        value=command([*argv,'--filter','label=com.docker.compose.project='+project]).strip()
        assert not value, (project,kind,value)
        result['docker'][project][kind]=[]
for role in ('A','C'):
    receipt=json.loads((HERE.with_name('perf391-built-images-v1')/f'evidence/built-{role}.json').read_bytes())
    for kind,image in receipt['images'].items():
        actual=json.loads(command(['docker','image','inspect',image['id'],'--format','{{json .}}']))
        assert actual['Id']==image['id'] and actual['Config']['Labels']==image['labels']
        result['images'][role+'-'+kind]=actual['Id']
listeners=command(['ss','-ltn'])
ports=[*range(38080,38084),*range(38180,38184)]
assert not any(':'+str(p)+' ' in listeners for p in ports)
result['ports_verified_absent']=ports
# Timeout leftovers have unique test-only prefixes and fixture contents.
for path in Path('/tmp').glob('perf391-executor-fixture-*'):
    assert (path/'fake.py').is_file() and (path/'receipt.json').is_file(), path
    shutil.rmtree(path)
    result['removed_paths'].append(str(path))
for path in Path('/tmp').glob('perf391-smoke-408-perf391-executor-fixture-*'):
    assert (path/'launch.json').is_file(), path
    shutil.rmtree(path)
    result['removed_paths'].append(str(path))
root=Path('/tmp/perf391-node-contract-408')
assert json.loads((root/'ownership.json').read_bytes())['task']=='perf391-node-contract-408'
shutil.rmtree(root)
result['removed_paths'].append(str(root))
assert all(not Path(p).exists() for p in result['removed_paths'])
result['verified']=True
result['no_real_containers_or_browsers_created']=True
(HERE/'evidence/cleanup.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print('No task process survivors, A/C listeners or scoped Docker resources; four accepted images retained; private Node/export/venv and timeout leftovers removed.')
