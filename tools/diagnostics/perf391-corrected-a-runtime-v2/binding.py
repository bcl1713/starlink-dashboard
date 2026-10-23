"""A-only identity adapter over unchanged historical compilers and corrected scripts.

Loading the bound executor does not execute it. This checkpoint's CLI is offline
only; a future runtime still requires separate authorization and host supervision.
"""
import copy
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PREP = HERE.with_name('perf391-runtime-preparation-v1')
INTEGRATION = HERE.with_name('perf391-diagnostic-integration-v1')
BUILT = HERE.with_name('perf391-corrected-images-v2')
HIST = HERE.with_name('perf391-built-images-v1')
TASK = Path('/tmp/perf391-corrected-a-preflight')
CONTEXT = TASK / 'contexts/A'
PLAN = BUILT / 'evidence/corrected-build-plan.json'
RECEIPT = BUILT / 'evidence/built-A.compat-v1.json'
LINEAGE = BUILT / 'evidence/built-A.v2.json'
sys.path.insert(0, str(PREP))
import prepare
import launcher
import correction


def read(path):
    return json.loads(Path(path).read_bytes())


def verify_binding(plan=None):
    """Exact closed inventories; no historical source guard is broadened."""
    overlay = read(HERE / 'identity-overlay.json')
    assert overlay['schema'] == 'perf391-corrected-a-runtime-identity-v2'
    assert overlay['role'] == 'A' and overlay['runtime_authorized'] is False
    for name, digest in overlay['files'].items():
        path = REPO / name
        prepare.build.safe_path(name)
        assert not path.is_symlink() and prepare.sha(path) == digest, name
    for directory, inventory in overlay['source_closures'].items():
        root = REPO / directory
        actual = {p.relative_to(root).as_posix() for p in root.rglob('*')
                  if (p.is_file() or p.is_symlink())
                  and not {'evidence', '__pycache__', 'node_modules', '.ruff_cache', 'artifacts'}.intersection(p.relative_to(root).parts)}
        assert actual == set(inventory), directory
        for name, digest in inventory.items():
            assert not (root / name).is_symlink() and prepare.sha(root / name) == digest, name
    correction.verify_correction()
    corrected = read(PLAN)
    assert plan is None or plan == corrected
    assert prepare.sha(PLAN) == overlay['corrected_plan_sha256']
    assert prepare.sha(RECEIPT) == overlay['compatible_receipt_sha256']
    assert prepare.sha(LINEAGE) == overlay['lineage_sha256']
    from jsonschema import Draft202012Validator
    lineage = read(LINEAGE)
    Draft202012Validator(read(BUILT / 'receipt-schema.json')).validate(lineage)
    assert lineage['role'] == 'A' and not lineage['runtime_authorized']
    assert lineage['corrected_plan_sha256'] == prepare.sha(PLAN)
    assert lineage['compatible_receipt_sha256'] == prepare.sha(RECEIPT)
    assert lineage['historical_receipt_sha256'] == prepare.sha(HIST / 'evidence/built-A.json')
    assert lineage['original_plan_sha256'] == prepare.sha(HIST / 'evidence/runtime-build-plan.json')
    assert lineage['correction_overlay_sha256'] == prepare.sha(PREP / 'diagnostic-correction-overlay.json')
    receipt = read(RECEIPT)
    launcher.validate_receipt(receipt, corrected, prepare.sha(PLAN))
    for kind in ('backend', 'frontend'):
        assert receipt['images'][kind]['id'] == lineage['images'][kind]['corrected_id']
        assert read(HIST / 'evidence/built-A.json')['images'][kind]['id'] == lineage['images'][kind]['original_id']
    return overlay


def compile_launch(role='A', root='/tmp/perf391-smoke-408-a', plan_path=PLAN, receipt=None):
    assert role == 'A', 'corrected runtime binding is A only'
    assert Path(plan_path).resolve() == PLAN
    overlay = verify_binding()
    receipt = receipt if receipt is not None else read(RECEIPT)
    assert receipt == read(RECEIPT), 'only exact closed compatible receipt admitted'
    # Reuse the frozen v1 scheduling compiler without presenting a v2 plan as v1.
    # Receipt validation above uses the REAL corrected plan and its unchanged hash.
    launch = launcher.launch_plan('A', root, HIST / 'evidence/runtime-build-plan.json')
    launch['env'].update(PERF391_CONTEXT=str(CONTEXT),
                         PERF391_BACKEND_IMAGE=receipt['images']['backend']['id'],
                         PERF391_FRONTEND_IMAGE=receipt['images']['frontend']['id'])
    seed = next(s for s in launch['commands'] if s['phase'] == 'seed-file')
    seed['argv'][1] = str(CONTEXT / 'tools/acceptance/overview_history/seed.py')
    launch['browser_options'].update(nodeRoot=receipt['browser']['playwright_root'],
                                     chromiumExecutable=receipt['browser']['chromium_executable'])
    launch['corrected_identity'] = {
        'schema': overlay['schema'], 'overlay_sha256': prepare.sha(HERE / 'identity-overlay.json'),
        'build_plan': str(PLAN), 'build_plan_sha256': prepare.sha(PLAN),
        'receipt': str(RECEIPT), 'receipt_sha256': prepare.sha(RECEIPT),
        'lineage': str(LINEAGE), 'lineage_sha256': prepare.sha(LINEAGE),
        'historical_plan_sha256': overlay['historical_plan_sha256'],
        'executor_adapter': str(HERE / 'binding.py') + ':bound_executor',
        'selected_scripts': overlay['selected_scripts'],
    }
    assert launch['deadlines'] == {'work_seconds':78, 'cleanup_by_seconds':90,
                                   'outer_timeout_seconds':90, 'kill_grace_seconds':10}
    return launch


def validate_bound_receipt(receipt, plan, plan_hash):
    verify_binding(plan)
    assert plan_hash == prepare.sha(PLAN)
    # The executor also validates a stopped-image extraction with a relocated root.
    comparable = {**receipt, 'asset_root': read(RECEIPT)['asset_root']}
    assert comparable == read(RECEIPT), 'unapproved receipt difference'
    launcher.validate_receipt(receipt, plan, plan_hash)


def bound_executor():
    """Select corrected code with A-only preflight hooks; never start it here.

    All process ownership, work/cleanup deadlines, readiness and failure-path
    preservation remain the approved executor implementation. No no-op guards.
    """
    verify_binding()
    spec = importlib.util.spec_from_file_location('corrected_a_executor', PREP / 'execute.proposed.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.require_runtime_assets = verify_binding
    module.check_release = verify_binding
    module.verify_runtime_overlay = verify_binding
    module.validate_receipt = validate_bound_receipt
    module.launch_plan = compile_launch
    assert Path(module.preserve_backend.__code__.co_filename).resolve() == PREP / 'backend_evidence.py'
    assert Path(module.wait_ready.__code__.co_filename).resolve() == PREP / 'frontend_readiness.py'
    return module


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.execute:
        parser.error('STOP: offline binding checkpoint only; separate A runtime authorization required')
    print(json.dumps(compile_launch(), indent=2, sort_keys=True))
