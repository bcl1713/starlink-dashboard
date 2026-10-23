"""Verify this failed-run evidence closure; never launches or retries runtime."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
E=HERE/'evidence'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((HERE/'artifact-manifest.json').read_text())
actual={str(p.relative_to(HERE)) for p in HERE.rglob('*') if p.is_file() and p.name!='artifact-manifest.json' and '__pycache__' not in p.parts}
assert actual==set(m['files'])
for name,digest in m['files'].items():assert sha(HERE/name)==digest,name
for name,digest in m['external_pins'].items():assert sha(REPO/name)==digest,name
assert json.loads((E/'preflight.json').read_text())['status']=='PASS_PREFLIGHT_NO_RUNTIME_STARTED'
env=json.loads((E/'environment.json').read_text())
assert env['status']=='PASS' and env['native_sha256']=='be6a965c619fc93dd16b4094ee63a73ad24e9a1e1915e5120679ea574ea7b7c6'
assert len(env['packages'])==6 and not any('dist-packages' in p for p in env['sys_path'])
assert json.loads((E/'execution-exit.json').read_text())=={'exit_code':1,'utc':json.loads((E/'execution-exit.json').read_text())['utc'],'A_invocations':1,'C_invocations':0}
intent=json.loads((E/'execution-intent.json').read_text())
assert intent['runtime_attempts']==1 and intent['C_executions']==0
assert intent['deadlines']=={'work_seconds':78,'outer_timeout_seconds':90,'kill_grace_seconds':10}
assert intent['executor_sha256']==sha(HERE.with_name('perf391-runtime-preparation-v1')/'execute.proposed.py')
r=json.loads((E/'runtime/runtime-result.json').read_text())
assert r['failure']=='TimeoutError: insufficient command/termination budget' and r['cleanup_error'] is None and r['diagnostic_error'] is None and r['owner_status']=='clean'
readiness=json.loads((E/'runtime/frontend-readiness.json').read_text())
assert readiness['status']=='timeout' and len(readiness['attempts'])==11
raw_refusals=[p for p in (E/'runtime').glob('command-*.log') if 'ConnectionRefusedError: [Errno 111]' in p.read_text()]
assert len(raw_refusals)==10
snapshots=json.loads((E/'runtime/frontend-failure-diagnostics.json').read_text())
assert {s['kind'] for s in snapshots}=={'compose-ps','container-id','inspect','port','frontend-logs','listeners','forwarding'}
inspection=json.loads(next(s['output'] for s in snapshots if s['kind']=='inspect'))
assert inspection['State']['Running'] and inspection['Ports']=={'80/tcp':None}
assert next(s['output'] for s in snapshots if s['kind']=='port')==''
for name in ('browser','host.jsonl','host-mapping.json'):
    assert not (E/'runtime'/name).exists()
assert not list((E/'runtime/backend').glob('*'))
stream=json.loads((E/'stream-status.json').read_text())
assert stream['functional_pass'] is False and stream['screenshot_attempts']==0
assert all(v['dropped_events'] is None for v in stream['streams'].values())
for name in ('runtime/cleanup-audit.json','final-host-cleanup.json'):
    assert json.loads((E/name).read_text())['clean']
cleanup=json.loads((E/'final-host-cleanup.json').read_text())
assert len(cleanup['checked_process_identities'])==52 and len(cleanup['owner_manifests'])==42
assert cleanup['temporary_paths_absent'] and not cleanup['process_survivors'] and not cleanup['listeners']
assert all(not values for project in cleanup['docker'].values() for values in project.values())
inventory=json.loads((E/'runtime-inventory.json').read_text())
for name,row in inventory['all_files'].items():
    if name not in inventory['omitted_reproducible_inputs']:
        assert sha(E/'runtime'/name)==row['sha256']
for row in json.loads((E/'github-state.json').read_text()):
    assert row['state']=='open'
    if row['kind']=='pull_request':assert row['draft'] and not row['merged']
changed=subprocess.check_output(['git','diff','96d48ad7405d2b7b799b4dd62461364f5af1a3a6','--name-only'],cwd=REPO,text=True).splitlines()
assert all(p.startswith(str(HERE.relative_to(REPO))+'/') for p in changed)
print(f'PASS: {len(m["files"])} artifact hashes, {len(m["external_pins"])} external pins; failed A-only readiness evidence, unavailable loss boundaries and independent cleanup verified')
