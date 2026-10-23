"""Independent retained failure-artifact audit. Does not run the smoke."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
E=HERE/'evidence'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(name):return json.loads((E/name).read_bytes())
m=json.loads((HERE/'artifact-manifest.json').read_bytes())
actual={p.relative_to(HERE).as_posix() for p in HERE.rglob('*') if p.is_file() and p != HERE/'artifact-manifest.json'}
assert actual==set(m['files'])
for name,digest in m['files'].items():assert sha(HERE/name)==digest,name
for name,digest in m['external_pins'].items():
 assert sha(REPO/name)==digest,name
 assert hashlib.sha256(subprocess.check_output(['git','show',m['starting_commit']+':'+name],cwd=REPO)).hexdigest()==digest,name
assert read('preflight.json')['status']=='PASS_PREFLIGHT_NO_RUNTIME_STARTED'
comparison=read('preflight.json')['checks']['build_plan_comparison']
assert comparison['original_fields_identical'] and comparison['approved_override_hashes_match']
assert {d['path'] for d in comparison['differences']}=={'/roles/A/compose_sha256/override','/roles/C/compose_sha256/override'}
source=(HERE.with_name('perf391-a-functional-smoke-v1')/'preflight.py').read_text()
expected=source.replace("TASK = Path('/tmp/perf391-a-functional-20261023')", "TASK = Path('/tmp/perf391-a-approved-smoke')").replace("E = HERE / 'evidence'", "E = HERE.with_name('perf391-a-approved-smoke-v1') / 'evidence'").replace('ae3c8d28fa1e5263fe6d85b0e1a897d3ae339ee9',m['starting_commit']).replace('6356577550','6362494281')
assert (HERE/'preflight-adapted.txt').read_text()==expected
assert (E/'executor-exit.txt').read_text().strip()=='1'
assert read('runtime/runtime-result.json')=={'failure':'RuntimeError: browser smoke failure','cleanup_error':None,'owner_status':'clean','external_host_audit_required':True}
assert read('runtime/browser/failure.json')['reason']=='connect ECONNREFUSED 127.0.0.1:38080'
assert not (E/'runtime/browser/browser-process.json').exists()
assert not (E/'runtime/browser/frontend-final.json').exists()
assert not (E/'runtime/backend/backend-stats.json').exists()
status=read('stream-status.json');assert status['runtime_attempts']==1 and status['C_executions']==0 and status['screenshot_attempts']==0
assert status['cadence_requirement_seconds']==1.5 and not status['cadence_exercised']
assert all(status[k]['final_summary'] is None and status[k]['dropped'] is None for k in ('backend','source','browser'))
host=[json.loads(line) for line in (E/'runtime/host.jsonl').read_text().splitlines()]
assert sum(r['kind']=='resource' for r in host)==1
assert [r for r in host if r['kind']=='summary']==[{'kind':'summary','completed':1,'skipped':0,'complete':False}]
receipt=json.loads((HERE.with_name('perf391-built-images-v1')/'evidence/built-A.json').read_bytes())
omitted=read('omitted-duplicate-inventory.json')['files']
assert {k.removeprefix('image-assets/'):v['sha256'] for k,v in omitted.items() if k.startswith('image-assets/')}==receipt['assets']
launch=read('launch-A.json');del launch['preflight_comparison'];del launch['ownership']['logging_correction']
assert launch==read('executor-launch-A.json')==read('runtime/launch.json')
for name in ('runtime/manifest.json','runtime/verification-owner/manifest.json','runtime/cleanup-owner/manifest.json'):
 owner=read(name);assert owner['status']=='clean' and not owner['errors'] and not owner['adopted_survivors']
assert read('runtime/cleanup-audit.json')['clean']
cleanup=read('final-host-cleanup.json')
assert cleanup['clean'] and len(cleanup['checked_process_identities'])==23
assert not cleanup['process_survivors'] and not cleanup['listeners'] and not any(v for p in cleanup['docker'].values() for v in p.values())
assert all(not Path(p).exists() for p in cleanup['removed_paths'])
for state in read('github-states.json'):
 assert state['state']=='open'
 if state['number'] in (403,405,406,407,408):assert state['draft'] and not state['merged']
print('PASS failure-evidence audit: %d artifact hashes, %d unchanged external pins; one failed A, no C, incomplete streams explicit, 23 process identities and private cleanup verified.' % (len(m['files']),len(m['external_pins'])))
