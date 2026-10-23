"""Independent read-only host cleanup audit after offline preflight has exited."""
import json
import os
from pathlib import Path
import subprocess
import time

HERE = Path(__file__).resolve().parent
E = HERE / 'evidence'
OWNER = 'perf391-corrected-a-preflight'
TASK = Path('/tmp') / OWNER
result = {'utc':time.strftime('%FT%TZ',time.gmtime()), 'commands':[], 'process_checks':[]}


def command(argv):
    proc = subprocess.run(['timeout','--kill-after=10s','30s',*argv], capture_output=True, text=True)
    result['commands'].append({'argv':argv,'exit':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr})
    proc.check_returncode()
    return proc.stdout


assert Path('/proc/1/comm').read_text().strip() == 'systemd', 'host namespace required'
for row in [json.loads((E / 'ownership.json').read_bytes()), *json.loads((E / 'commands.json').read_bytes())]:
    if 'pid' not in row:
        continue
    same = False
    try:
        same = Path('/proc',str(row['pid']),'stat').read_text().rsplit(')',1)[1].split()[19] == row['start_identity'].rsplit(')',1)[1].split()[19]
    except OSError:
        pass
    result['process_checks'].append({'pid':row['pid'],'live_same_identity':same})
    assert not same, row['pid']
ancestors = {os.getpid()}
pid = os.getpid()
while pid > 1:
    pid = int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[1])
    ancestors.add(pid)
survivors = []
for proc in Path('/proc').iterdir():
    if not proc.name.isdecimal() or int(proc.name) in ancestors:
        continue
    try:
        args = proc.joinpath('cmdline').read_bytes()
        if any(token in args for token in (str(TASK).encode(), b'tools/diagnostics/perf391-corrected-a-runtime-v2/')):
            survivors.append({'pid':int(proc.name),'comm':proc.joinpath('comm').read_text().strip()})
    except OSError:
        pass
assert not survivors, survivors
result['process_survivors'] = survivors
for kind, argv in [('containers',['docker','ps','-aq']),('networks',['docker','network','ls','-q']),('volumes',['docker','volume','ls','-q'])]:
    for label in ('perf391.owner='+OWNER,'com.docker.compose.project='+OWNER,'com.docker.compose.project=perf391-smoke-408-a'):
        assert not command([*argv,'--filter','label='+label]).strip()
    result[kind] = []
listeners = command(['ss','-ltnp'])
assert not any(':'+str(port)+' ' in listeners for port in range(38080,38084))
result['listeners'] = listeners
result['task_listeners'] = []
assert not TASK.exists()
result['temporary_root_removed'] = str(TASK)
result['container_states'] = []
for path in E.glob(OWNER+'-*.container.json'):
    container = json.loads(path.read_bytes())
    state = container['State']
    assert state['Status'] == 'created' and state['Pid'] == 0 and state['StartedAt'].startswith('0001-')
    result['container_states'].append({'id':container['Id'],'name':container['Name'],'state':state})
assert len(result['container_states']) == 2
# Confirm no tag/config/layer or old image changed after all checks.
built = HERE.with_name('perf391-corrected-images-v2') / 'evidence'
result['preserved_images'] = []
for role in ('A','C'):
    for kind in ('backend','frontend'):
        for prefix in ('historical-',''):
            retained = json.loads((built / f'{prefix}{role}-{kind}.image.json').read_bytes())[0]
            actual = json.loads(command(['docker','image','inspect',retained['Id']]))[0]
            assert all(actual[k] == retained[k] for k in ('Id','RepoTags','RepoDigests','Config','RootFS'))
            result['preserved_images'].append(actual['Id'])
result['cleanup_verified'] = True
(E / 'cleanup.json').write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
print('PASS: host PID/start identities, listeners, containers, networks, volumes and temporary paths clear; eight images preserved.')
