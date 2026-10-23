"""Offline verification of the retained failed smoke; never runs the application."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(name):
    return json.loads((HERE / name).read_bytes())


manifest = read('artifact-manifest.json')
actual = {
    p.relative_to(HERE).as_posix()
    for p in HERE.rglob('*')
    if p.is_file() and p != HERE / 'artifact-manifest.json'
}
assert actual == set(manifest['files']), 'artifact closure differs'
for name, expected in manifest['files'].items():
    p = HERE / name
    assert not p.is_symlink()
    assert hashlib.sha256(p.read_bytes()).hexdigest() == expected, name
assert read('evidence/preflight.json')['status'] == 'PASS_PREFLIGHT_NO_RUNTIME_STARTED'
assert read('evidence/execution-exit.json')['exit'] == 1
result = read('evidence/runtime/runtime-result.json')
assert result['failure'] == "RuntimeError: command failure: ['docker', 'compose', '-p']"
assert result['cleanup_error'] is None and result['owner_status'] == 'clean'
assert 'compression cannot be enabled when max file count is 1' in (
    HERE / 'evidence/runtime/command-08.log'
).read_text()
for name in ('manifest.json', 'verification-owner/manifest.json', 'cleanup-owner/manifest.json'):
    owner = read('evidence/runtime/' + name)
    assert owner['status'] == 'clean' and not owner['errors']
    assert not owner['adopted_survivors']
    assert all(p['reaped'] and not p['survivors'] for p in owner['processes'])
assert read('evidence/runtime/cleanup-audit.json')['clean']
cleanup = read('evidence/final-host-cleanup.json')
assert cleanup['clean'] and not cleanup['process_survivors']
assert not cleanup['path_process_survivors']
assert all(not values for project in cleanup['docker'].values() for values in project.values())
assert all(not Path(p).exists() for p in cleanup['removed_paths'])
built = HERE.with_name('perf391-built-images-v1') / 'evidence'
receipt = json.loads((built / 'built-A.json').read_bytes())
assert read('evidence/extracted-asset-hashes.json') == receipt['assets']
assert hashlib.sha256((built / 'built-A.json').read_bytes()).hexdigest() == (
    '7d337809082015880bb51e69bcf8973fd5036518286b876dda77145543c9c24f'
)
streams = read('evidence/stream-status.json')
assert streams['attempts'] == {'A': 1, 'C': 0}
assert streams['browser_launch_attempts'] == streams['compositor_screenshot_attempts'] == 0
assert not streams['instrumentation_end_to_end'] and not streams['C_ready']
assert streams['dropped_event_counts'] is None
assert streams['observer_cadence_gate_seconds'] == 1.5
print(f"Verified {len(actual)} retained artifact hashes and exact closure; expected startup failure, unavailable runtime streams, immutable receipt/assets, owner reaping and independent cleanup evidence confirmed.")
