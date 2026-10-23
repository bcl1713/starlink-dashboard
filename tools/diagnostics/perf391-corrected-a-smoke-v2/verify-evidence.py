"""Read-only artifact verification for a stopped preflight; never launch runtime."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
E = HERE / 'evidence'
REPO = HERE.parents[2]

def read(path):
    return json.loads(path.read_bytes())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

manifest = read(HERE / 'artifact-manifest.json')
actual = {p.relative_to(HERE).as_posix() for p in HERE.rglob('*')
          if p.is_file() and p != HERE / 'artifact-manifest.json'}
assert actual == set(manifest['files'])
for name, expected in manifest['files'].items():
    path = HERE / name
    assert not path.is_symlink() and sha(path) == expected, name
outcome = read(E / 'outcome.json')
assert outcome['status'] == 'STOP_PREFLIGHT_NO_RUNTIME'
assert outcome['preflight_attempts'] == 1
for name in ('context_regenerations', 'A_executor_invocations', 'C_executor_invocations',
             'application_containers_started', 'browser_launches', 'source_observations',
             'host_observations', 'screenshot_attempts'):
    assert outcome[name] == 0, name
assert not outcome['runtime_gate_pass']
assert outcome['limits_unchanged'] == {
    'work_seconds': 78, 'outer_timeout_seconds': 90,
    'forced_termination_grace_seconds': 10, 'source_samples': 5, 'host_samples': 5,
    'observation_hz': 1, 'max_observer_cadence_seconds': 1.5,
    'network_charts': 1, 'max_bracketed_screenshot_attempts': 1}
preflight = read(E / 'preflight.json')
assert preflight['status'] == 'STOP_PREFLIGHT'
commands = read(E / 'commands.json')
assert len(commands) == 17 and all(x['state'] == 'exited' for x in commands)
assert all(x['exit'] == 0 for x in commands[:-1]) and commands[-1]['exit'] == 1
assert 'assert compile_launch() == launch' in (E / 'host-check-16.log').read_text()
assert 'PASS: correction provenance' in (E / 'host-check-16.log').read_text()
diag = read(E / 'failure-diagnosis.json')
assert diag['reason_code'] == outcome['reason_code']
assert diag['all_differences_exact_worktree_prefix_relocation']
assert len(diag['differences']) == 5 and not diag['binding_factory_called']
for row in diag['differences']:
    assert row['retained'].replace('/.worktrees/perf391-corrected-runtime/',
                                  '/.worktrees/perf391-corrected-a-smoke-20261023/') == row['regenerated']
assert read(E / 'dependency-command-03.log')['status'] == 'PASS'
assert 'All installed packages are compatible' in (E / 'dependency-command-04.log').read_text()
assert 'all six installed payloads match' in (E / 'dependency-command-05.log').read_text()
for name in ('cleanup.json', 'post-cleanup.json'):
    cleanup = read(E / name)
    assert cleanup['cleanup_verified']
cleanup = read(E / 'cleanup.json')
assert not cleanup['process_survivors'] and not cleanup['task_listeners']
assert all(not row['live_same_identity'] for row in cleanup['process_checks'])
assert len(set(cleanup['preserved_images'])) == 8
assert all(not cleanup[name] for name in ('containers', 'networks', 'volumes'))
assert len(cleanup['temporary_paths_absent']) == 4
preservation = read(E / 'source-preservation.json')
assert preservation['all_preexisting_tracked_files_byte_identical']
assert preservation['tracked_files_checked'] == 5548 and not preservation['changed']
for name, expected in preservation['hashes'].items():
    assert sha(REPO / name) == expected, name
for row in read(E / 'github-pr-states.json'):
    assert row['state'] == 'open' and row['draft'] and not row['merged']
for row in read(E / 'github-issue-states.json'):
    assert row['state'] == 'open'
assert not subprocess.check_output([
    'git', 'diff', preservation['starting_commit'], '--', '.',
    ':(exclude)' + str(HERE.relative_to(REPO))], cwd=REPO)
print(f'PASS: {len(actual)} package files hashed; stopped preflight, exact five-path diagnosis, '
      'zero runtime counts, private dependency evidence, unchanged sources/policy and cleanup verified.')
