"""Read-only host verification after a native qualification runner has exited."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time

STATE = Path(__file__).resolve().parent
p = argparse.ArgumentParser()
p.add_argument('--run-name', required=True)
a = p.parse_args()
assert re.fullmatch(r'(preflight|sustained)-[0-9]{3}', a.run_name)
assert os.geteuid() == 1002
root = STATE / a.run_name
owner = json.loads((root / 'ownership.json').read_text())
runner = json.loads((STATE / (a.run_name + '-runner.json')).read_text())
assert runner['ended'] and owner['project'] == runner['project']
assert runner['candidate_sha'] == '46ed6af6d431cd7fac8633a9f3d829d5fc24d831'
project = owner['project']
result = json.loads((root / 'run.json').read_text())
assert all(not v for v in result['cleanup']['remaining'].values())
assert all(result['cleanup'][k] is True for k in ('composeRemoved', 'childrenReaped', 'listenerRemoved', 'temporaryPathsRemoved', 'imagesRemoved', 'prometheusListenerRemoved'))
groups = {owner['pgid'], runner['pgid']}
groups.update(item['pgid'] for item in owner['commands'] if item.get('pgid'))
assert all(item.get('reaped') and not item.get('groupRemaining') for item in owner['commands'])
browser = json.loads((root / 'browser-owner.json').read_text())
groups.add(browser['pgid'])
markers = [str(root), project]
for argument in browser['command']:
    if argument.startswith('--user-data-dir='):
        profile = argument.split('=', 1)[1]
        assert not Path(profile).exists()
        markers.append(profile)
sampler = STATE / ('cardinality-' + a.run_name + '-owner.json')
if sampler.exists():
    observed = json.loads(sampler.read_text())
    groups.add(observed['pgid'])
ancestors = {os.getpid()}
parent = os.getppid()
while parent > 1 and parent not in ancestors:
    ancestors.add(parent)
    parent = int(Path(f'/proc/{parent}/stat').read_text().rsplit(')', 1)[1].split()[1])
remaining = []
for proc in Path('/proc').iterdir():
    if not proc.name.isdigit() or int(proc.name) in ancestors:
        continue
    try:
        fields = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
        command = (proc / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
        if int(fields[2]) in groups or any(marker in command for marker in markers):
            remaining.append({'pid': int(proc.name), 'pgid': int(fields[2]), 'state': fields[0]})
    except FileNotFoundError:
        pass
assert not remaining, remaining
resources = {}
for kind in ('container', 'network', 'volume'):
    ids = subprocess.check_output(['docker', kind, 'ls', '-q', '--filter', 'label=com.docker.compose.project=' + project], text=True, timeout=15).split()
    ids += subprocess.check_output(['docker', kind, 'ls', '-q', '--filter', 'name=^' + re.escape(project) + '[-_]'], text=True, timeout=15).split()
    resources[kind] = ids
    assert not ids, (kind, ids)
for tag in owner['images']:
    found = subprocess.run(['docker', 'image', 'inspect', tag], text=True, capture_output=True, timeout=15)
    assert found.returncode != 0 and 'No such' in found.stderr, 'Owned image tag still exists or query failed'
ports = [owner['port'], owner['prometheusPort']]
listeners = subprocess.check_output(['ss', '-H', '-ltnup'], text=True, timeout=10)
assert not any(re.search(r':' + str(port) + r'\b', line) for line in listeners.splitlines() for port in ports)
reservation = owner.get('reservation', {})
assert reservation.get('released') is True
unix = subprocess.check_output(['ss', '-H', '-xap'], text=True, timeout=10)
assert reservation['name'] not in unix
for temporary in owner['temporaryPaths']:
    assert not Path(temporary).exists() and not Path(temporary).is_symlink()
receipt = {'checked_at': time.time(), 'status': 'clean', 'actor_uid': os.geteuid(), 'project': project, 'candidate_sha': runner['candidate_sha'], 'run_status': result['status'], 'remaining_processes': remaining, 'remaining_resources': resources, 'closed_ports': ports, 'abstract_reservation_absent': reservation['name'], 'owned_image_tags_absent': owner['images'], 'temporary_inputs_absent': owner['temporaryPaths'], 'method': 'Approved host; exact recorded groups and runtime/profile markers, Docker label/name queries, TCP/UDP listeners; no runtime mutation.'}
target = STATE / (a.run_name + '-independent-cleanup.json')
assert not target.exists()
target.write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'status': 'clean', 'receipt': str(target)}))
