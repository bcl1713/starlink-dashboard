"""Offline immutable receipt/release audit and A launch-plan compilation only."""
import json
from pathlib import Path
import runpy
import sys
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
PREP = HERE.with_name('perf391-runtime-preparation-v1')
BUILT = HERE.with_name('perf391-built-images-v1')
sys.path.insert(0, str(PREP))
import prepare
from launcher import launch_plan
from runtime_identity import verify_runtime_overlay

plan_path = BUILT / 'evidence/runtime-build-plan.json'
plan = json.loads(plan_path.read_bytes())
verify_runtime_overlay(plan)
# Reuse every retained-artifact check; replace only the explicitly superseded
# overlay check with its stricter original + corrected inventory check.
with patch.object(prepare, 'verify_overlay', verify_runtime_overlay):
    runpy.run_path(str(BUILT / 'verify-retained.py'), run_name='__offline_audit__')
result = {'release': prepare.check_release(), 'build_plan_sha256': prepare.sha(plan_path),
          'correction_manifest_sha256': prepare.sha(PREP / 'node-contract-overlay.json'), 'receipts': {}}
for role in ('A', 'C'):
    path = BUILT / f'evidence/built-{role}.json'
    receipt = json.loads(path.read_bytes())
    result['receipts'][role] = {'sha256': prepare.sha(path), 'images': receipt['images'], 'browser': receipt['browser']}
receipt = json.loads((BUILT / 'evidence/built-A.json').read_bytes())
launch = launch_plan('A', '/tmp/perf391-smoke-408-a', plan_path, receipt)
prepare.write(HERE / 'evidence/launch-A.proposed.json', launch)
prepare.write(HERE / 'evidence/immutable-identities.json', result)
print('Original receipts, four retained image records, 187-file build manifest, 621-file release and corrected overlay verified; A plan compiled offline.')
