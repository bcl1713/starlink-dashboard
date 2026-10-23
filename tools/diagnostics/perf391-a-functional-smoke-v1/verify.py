"""Offline artifact integrity audit; no runtime or regression test execution."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

manifest = json.loads((HERE/'artifact-manifest.json').read_text())
actual = {p.relative_to(HERE).as_posix() for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name != 'artifact-manifest.json'}
assert actual == set(manifest['files'])
for name, digest in manifest['files'].items():
    p = HERE/name
    assert not p.is_symlink() and HERE in p.resolve().parents and sha(p) == digest, name
for name, digest in manifest['external_files'].items():
    p = REPO/name
    assert not p.is_symlink() and REPO in p.resolve().parents and sha(p) == digest, name
preflight = json.loads((HERE/'evidence/preflight.json').read_text())
assert preflight['status'] == 'STOP_PREFLIGHT' and preflight['runtime_attempts'] == 0
assert preflight['starting_commit'] == manifest['starting_commit']
diff = json.loads((HERE/'evidence/plan-differences.json').read_text())
assert {r['path'] for r in diff['differences']} == {'/roles/A/compose_sha256/override','/roles/C/compose_sha256/override'}
plan_path = REPO/'tools/diagnostics/perf391-built-images-v1/evidence/runtime-build-plan.json'
assert sha(plan_path) == diff['retained_plan_sha256']
assert sha(HERE/'evidence/regenerated-build-plan.json') == diff['regenerated_plan_sha256']
a = json.loads(plan_path.read_text())
b = json.loads((HERE/'evidence/regenerated-build-plan.json').read_text())
for role in ('A','C'):
    assert a['roles'][role]['compose_sha256']['override'] == next(r['retained'] for r in diff['differences'] if r['path'] == f'/roles/{role}/compose_sha256/override')
    a['roles'][role]['compose_sha256']['override'] = b['roles'][role]['compose_sha256']['override']
assert a == b
logging = json.loads((HERE/'evidence/logging-comparison.json').read_text())
approved = json.loads((REPO/'tools/diagnostics/perf391-logging-compat-v1/evidence/config-hashes.json').read_text())
for role in logging['roles']:
    assert role['compiled_override_canonical_sha256'] == approved['roles'][role['role']]['compose_override_sha256']
    assert all(service['equal'] and service['generated'] == {'driver':'local','options':{'compress':'false','max-file':'1','max-size':'10m'}} for service in role['services'].values())
status = json.loads((HERE/'evidence/stream-status.json').read_text())
assert status['A_attempts'] == status['C_attempts'] == status['screenshot_attempts'] == 0
assert status['observer_cadence_seconds'] == 1.5 and status['dropped_event_counts'] is None
cleanup = json.loads((HERE/'evidence/final-host-cleanup.json').read_text())
assert cleanup['clean'] and not cleanup['listeners'] and not cleanup['process_survivors']
assert cleanup['runtime_root_absent'] and cleanup['lock_absent']
assert all(cleanup['preflight_command_pids_absent'].values())
assert not any(v for project in cleanup['docker'].values() for v in project.values())
assert not Path('/tmp/perf391-a-functional-20261023').exists()
assert not Path('/tmp/perf391-smoke-408-a').exists()
print(f"PASS: {len(manifest['files'])} package hashes and {len(manifest['external_files'])} immutable external pins; exact two-field preflight mismatch, no runtime attempts, independent cleanup clean.")
