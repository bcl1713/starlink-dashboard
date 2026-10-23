"""Independent host audit and removal of recorded preflight scratch only."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent
E = HERE / 'evidence'
TASK = Path('/tmp/perf391-a-functional-20261023')
RUNTIME = Path('/tmp/perf391-smoke-408-a')

def command(argv):
    return subprocess.check_output(['timeout', '--kill-after=5s', '15s', *argv], text=True).strip()

def write(p, row):
    p.write_text(json.dumps(row, indent=2, sort_keys=True) + '\n')

assert command(['hostname']) == 'forge'
assert Path('/proc/1/comm').read_text().strip() == 'systemd'
assert json.loads((TASK/'ownership.json').read_text())['task'] == 'perf391-a-functional-20261023'
report = {'utc': time.strftime('%FT%TZ', time.gmtime()), 'actor_uid': os.getuid(), 'pid_namespace': os.readlink('/proc/self/ns/pid'), 'docker': {}, 'images': {}, 'process_survivors': [], 'listeners': [], 'removed_paths': []}
ancestors = set()
pid = os.getpid()
while pid > 0 and pid not in ancestors:
    ancestors.add(pid)
    try:
        pid = int(Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[1])
    except OSError:
        break
report['excluded_audit_ancestors'] = sorted(ancestors)
markers = [str(TASK), str(HERE.parents[2]), str(RUNTIME), str(HERE/'preflight.py')]
for p in Path('/proc').glob('[0-9]*'):
    if int(p.name) in ancestors:
        continue
    try:
        cmd = (p/'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
        cwd = os.readlink(p/'cwd')
        if any(marker in cmd or cwd.startswith(marker) for marker in markers):
            fields = (p/'stat').read_text().rsplit(')', 1)[1].split()
            report['process_survivors'].append({'pid': int(p.name), 'pgid': fields[2], 'start_id': fields[19], 'command': cmd, 'cwd': cwd})
    except (OSError, IndexError):
        pass
report['preflight_command_pids_absent'] = {str(pid): not Path(f'/proc/{pid}').exists() for pid in (1116214,1116225,1116226,1116725)}
for role in ('a', 'c'):
    project = 'perf391-smoke-408-' + role
    report['docker'][project] = {}
    for kind, argv in [('containers', ['docker','ps','-aq']), ('networks', ['docker','network','ls','-q']), ('volumes', ['docker','volume','ls','-q'])]:
        report['docker'][project][kind] = command([*argv,'--filter','label=com.docker.compose.project='+project]).splitlines()
for role in ('A','C'):
    receipt = json.loads((HERE.with_name('perf391-built-images-v1')/f'evidence/built-{role}.json').read_text())
    for kind, image in receipt['images'].items():
        actual = json.loads(command(['docker','image','inspect',image['id'],'--format','{{json .}}']))
        assert all(actual[key] == image[key.lower()] for key in ('Id',))
        assert actual['Config']['Labels'] == image['labels'] and actual['RepoDigests'] == image['repo_digests']
        report['images'][role+'-'+kind] = image['id']
ports = set(range(38080,38084)) | set(range(38180,38184))
for line in command(['ss','-H','-ltnp']).splitlines():
    fields = line.split()
    if len(fields) > 3 and fields[3].rsplit(':',1)[-1] in {str(p) for p in ports}:
        report['listeners'].append(line)
report['ports_checked'] = sorted(ports)
report['runtime_root_absent'] = not RUNTIME.exists()
report['lock_absent'] = not Path('/tmp/perf391-smoke-408.lock').exists()
assert not report['process_survivors'] and not report['listeners']
assert all(report['preflight_command_pids_absent'].values())
assert not any(values for project in report['docker'].values() for values in project.values())
assert report['runtime_root_absent'] and report['lock_absent']
shutil.rmtree(TASK)
assert not TASK.exists()
report['removed_paths'].append(str(TASK))
report['clean'] = True
write(E/'final-host-cleanup.json', report)
print('Independent Forge host audit clean; private preflight scratch removed, no runtime resources, four immutable images retained.')
