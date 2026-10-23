"""Read-only checkpoint artifact validation; no regression suite or runtime."""
import json
from pathlib import Path
import subprocess
import sys

from binding import HERE, REPO, BUILT, PREP, HIST, TASK, PLAN, RECEIPT, read, prepare, verify_binding, compile_launch, bound_executor

E = HERE / 'evidence'
verify_binding()
subprocess.run(['timeout','--kill-after=10s','120s',sys.executable,'-B',str(BUILT / 'verify-retained.py')], check=True)
for role in ('A','C'):
    from launcher import validate_receipt
    validate_receipt(read(HIST / f'evidence/built-{role}.json'), read(HIST / 'evidence/runtime-build-plan.json'), prepare.sha(HIST / 'evidence/runtime-build-plan.json'))
report = read(E / 'verification.json')
assert report['status'] == 'PASS_OFFLINE_ONLY' and not report['runtime_executed']
for name, digest in report['hashes'].items():
    assert prepare.sha((HERE if name == 'identity-overlay.json' else E) / name) == digest, name
launch = read(E / 'launch-A.json')
assert compile_launch() == launch
assert bound_executor().launch_plan('A',launch['root'],PLAN,read(RECEIPT)) == launch
for row in read(E / 'commands.json'):
    assert row['state'] == 'exited' and row['exit'] == 0
assert read(E / 'cleanup.json')['cleanup_verified'] and not TASK.exists()
# Every pre-existing tracked byte stays at the requested starting commit.
assert not subprocess.check_output(['git','diff','07c68cda45d541ea2817f750bd56ca3da9de9702','--','.',':(exclude)'+str(HERE.relative_to(REPO))],cwd=REPO)
manifest_path = HERE / 'artifact-manifest.json'
manifest = read(manifest_path)
actual = {p.relative_to(HERE).as_posix() for p in HERE.rglob('*') if p.is_file() and p != manifest_path}
assert actual == set(manifest['files'])
for name, digest in manifest['files'].items():
    path = HERE / name
    assert not path.is_symlink() and prepare.sha(path) == digest, name
print('PASS: closed v2/compatible-v1/historical receipts, source and artifact closure, exact A launch/config hashes, corrected executor binding, and cleanup evidence.')
