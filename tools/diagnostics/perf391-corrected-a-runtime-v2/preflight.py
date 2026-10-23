"""Offline corrected-A context, stopped-image and Compose integration validation."""
import ast
import copy
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import sys

from binding import (HERE, REPO, PREP, INTEGRATION, BUILT, HIST, TASK, CONTEXT,
                     PLAN, RECEIPT, LINEAGE, read, verify_binding, compile_launch,
                     bound_executor, prepare, launcher)

sys.path.insert(0, str(BUILT))
import forge
from runtime_identity import verify_runtime_identity

E = HERE / 'evidence'
OWNER = 'perf391-corrected-a-preflight'
forge.E, forge.ROOT, forge.OWNER = E, TASK, OWNER
run, files = forge.run, forge.files
report = {'scope':'offline corrected-A runtime preparation', 'runtime_executed':False,
          'starting_commit':'07c68cda45d541ea2817f750bd56ca3da9de9702', 'checks':{}}


def regenerate():
    old_path = HIST / 'evidence/runtime-build-plan.json'
    original = read(old_path)
    baseline = TASK / 'baseline'
    raw = prepare.build.git(REPO, 'archive', '--format=tar', forge.ORIGINAL,
                            str(INTEGRATION.relative_to(REPO)), str(PREP.relative_to(REPO)))
    for name, (data, mode) in prepare.build.archive_files(raw).items():
        path = baseline / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o755 if mode == '100755' else 0o644)
    gitdir = prepare.build.git(REPO, 'rev-parse', '--absolute-git-dir').decode().strip()
    run([sys.executable, '-B', baseline / PREP.relative_to(REPO) / 'prepare.py',
         '--output', CONTEXT.parent], 'historical-regeneration', 300,
        {**os.environ, 'GIT_DIR':gitdir, 'PYTHONDONTWRITEBYTECODE':'1'})
    assert (CONTEXT.parent / 'runtime-build-plan.json').read_bytes() == old_path.read_bytes()
    expected = copy.deepcopy(original)
    expected.update(schema='perf391-corrected-build-plan-v2', qualification='diagnostic_build_only',
                    runtime_authorized=False, correction_source=forge.SOURCE, correction_delivery=forge.DELIVERY,
                    correction_overlay_sha256=forge.CORRECTION, original_plan_sha256=prepare.sha(old_path),
                    cached_dependency_image_id='sha256:fbd74391b8bc2816673a0458194c312b47c7315669c41ea3e514ceaf61a22fd6',
                    cached_dependency_recipe_sha256=prepare.sha(BUILT / 'evidence/cached-dependencies.Dockerfile'))
    # Regenerate both frozen contexts to prove the whole original plan. Only A is selected.
    for role in ('A', 'C'):
        context = CONTEXT.parent / role
        for name in ('browser-probe.ts', 'browser.mjs', 'collect.mjs'):
            target = context / '.perf391/diagnostic' / name
            item = read(PREP / 'diagnostic-correction-overlay.json')['source_files'][str((INTEGRATION / name).relative_to(REPO))]
            assert prepare.sha(target) == item['predecessor_sha256']
            shutil.copyfile(INTEGRATION / name, target)
            expected['roles'][role]['diagnostic_modules'][name] = prepare.sha(target)
        labels = expected['roles'][role]['labels']
        labels.update({'perf391.correction.source':forge.SOURCE, 'perf391.correction.delivery':forge.DELIVERY,
                       'perf391.correction.overlay.sha256':forge.CORRECTION,
                       'perf391.qualification':'diagnostic-build-only', 'perf391.owner':'perf391-corrected-forge'})
        labels['runtime_frontend_closure_sha256'] = prepare.build.digest(prepare.build.canonical({
            'original':labels['runtime_frontend_closure_sha256'], 'correction_overlay_sha256':forge.CORRECTION,
            'probe_sha256':prepare.sha(INTEGRATION / 'browser-probe.ts')}))
        for kind in ('backend', 'frontend'):
            shutil.copyfile(BUILT / f'evidence/{role}.{kind}.Dockerfile', context / f'.perf391/{kind}.Dockerfile')
        inventory = prepare.build.tree_manifest(context)
        assert inventory == read(BUILT / f'evidence/{role}-context-inventory.json')
        expected['roles'][role]['context_sha256'] = inventory['tree_sha256']
        expected['roles'][role]['overlay_inventory'] = prepare.build.tree_manifest(context / '.perf391')
    assert expected == read(PLAN), 'unapproved corrected build-plan delta'
    report['checks']['source_context'] = {
        'historical_plan_byte_identical':True, 'corrected_plan_exact_known_deltas':True,
        'A_application_sha256':expected['roles']['A']['identity']['effective_source_sha256'],
        'A_context_sha256':expected['roles']['A']['context_sha256'],
        'A_context_inventory_sha256':prepare.sha(BUILT / 'evidence/A-context-inventory.json')}


def inspect_images():
    # All historical and corrected identities are preserved; extract only corrected A.
    for role in ('A', 'C'):
        for kind in ('backend', 'frontend'):
            for prefix in ('historical-', ''):
                retained = read(BUILT / f'evidence/{prefix}{role}-{kind}.image.json')[0]
                actual = forge.inspect(retained['Id'], prefix + role + '-' + kind)
                assert all(actual[k] == retained[k] for k in ('Id','RepoTags','RepoDigests','Config','RootFS','Architecture','Os'))
    receipt = read(RECEIPT)
    with forge.stopped(receipt['images']['frontend']['id'], 'frontend') as cid:
        for source, target in [('/usr/share/nginx/html', 'assets'),('/etc/nginx/conf.d/default.conf','nginx.conf'),('/lib/apk/db/installed','apk-installed')]:
            forge.copy(cid, source, TASK / target, 'frontend-copy-' + target)
        launcher.validate_receipt({**receipt, 'asset_root':str(TASK / 'assets')}, read(PLAN), prepare.sha(PLAN))
        assert files(TASK / 'assets') == receipt['assets'] and len(receipt['assets']) == 29
        assert prepare.sha(TASK / 'nginx.conf') == prepare.sha(CONTEXT / 'frontend/mission-planner/nginx.conf')
        assert prepare.sha(TASK / 'apk-installed') == prepare.sha(HIST / 'evidence/A-frontend-apk-installed.txt')
        report['checks']['frontend'] = {'served_files':29, 'assets_sha256':read(LINEAGE)['assets_sha256'],
            'module_closure_sha256':prepare.sha(TASK / 'assets/perf391-module-closure.json'),
            'index_sha256':receipt['assets']['index.html'], 'image_bytes_match_receipt':True}
    root = TASK / 'backend'
    with forge.stopped(receipt['images']['backend']['id'], 'backend') as cid:
        for source, target in [('/diagnostic','diagnostic'),('/acceptance','acceptance'),('/app','app'),
                               ('/usr/local/bin/node','node'),('/var/lib/dpkg/status','dpkg-status'),
                               ('/opt/customer-briefing/assets','renderer-assets'),
                               ('/home/appuser/.local/lib/python3.11/site-packages','site-packages'),
                               ('/usr/local/lib/python3.11/site-packages','global-site-packages')]:
            forge.copy(cid, source, root / target, 'backend-copy-' + target)
        old = read(HIST / 'evidence/A-backend-modules.json')
        actual = read(BUILT / 'evidence/A-backend-modules.json')
        assert files(root / 'diagnostic') == actual['diagnostic'] == files(CONTEXT / '.perf391/diagnostic')
        assert files(root / 'acceptance') == old['acceptance']
        source = {n:prepare.sha(root / 'app' / n) for n in ('main.py','config.yaml')}
        for name in ('app','tests'):
            source.update({name+'/'+k:v for k,v in files(root / 'app' / name).items()})
        assert source == old['application']
        assert files(root / 'renderer-assets') == read(HIST / 'evidence/A-renderer-assets.json')
        assert prepare.sha(root / 'dpkg-status') == prepare.sha(HIST / 'evidence/A-backend-dpkg-status.txt')
        found = {}
        for dirname in ('global-site-packages','site-packages'):
            for dist in importlib.metadata.distributions(path=[str(root / dirname)]):
                found[re.sub(r'[-_.]+','-',dist.metadata['Name']).lower()] = {'name':dist.metadata['Name'],'version':dist.version}
        assert (json.dumps([found[k] for k in sorted(found)])+'\n').encode() == (HIST / 'evidence/A-python-packages.json').read_bytes()
        report['checks']['backend'] = {'diagnostic_module_inventory_sha256':prepare.sha(BUILT / 'evidence/A-backend-modules.json'),
                                      'application_fixture_renderer_unchanged':True, 'python_packages':len(found)}
        report['checks']['browser_identity'] = verify_runtime_identity(root / 'node', receipt)
        assert prepare.browser_tree(receipt['browser']['playwright_root'], receipt['browser']['chromium_executable']) == receipt['dependencies']['browser_tree_sha256']
        report['checks']['browser_tree_sha256'] = receipt['dependencies']['browser_tree_sha256']


def compile_and_render():
    launch = compile_launch()
    prepare.write(E / 'launch-A.json', launch)
    args = []
    for kind in ('base','override'):
        path = E / f'A.compose.{kind}.json'
        prepare.write(path, launch['compose'][kind])
        args += ['-f', str(path)]
    config = json.loads(run(['docker','compose','-p',launch['project'], *args,'config','--format','json'],
                            'compose-config', 20, {**os.environ, **launch['env']}))
    # Whole-config comparison to the prior approved non-internal/logging config.
    approved = read(HERE.with_name('perf391-network-correction-v1') / 'evidence/A.compose.json')
    old_project = approved['name']
    approved['name'] = launch['project']
    for group in ('networks','volumes'):
        for item in approved.get(group, {}).values():
            if item.get('name','').startswith(old_project+'_'):
                item['name'] = launch['project'] + item['name'][len(old_project):]
    for service, kind in [('starlink-location','backend'),('mission-planner','frontend')]:
        approved['services'][service]['image'] = read(RECEIPT)['images'][kind]['id']
    for volume in approved['services']['prometheus']['volumes']:
        if volume['target'] in ('/etc/prometheus/prometheus.yml','/etc/prometheus/rules'):
            relative = 'monitoring/prometheus/' + ('prometheus.yml' if volume['target'].endswith('.yml') else 'rules')
            volume['source'] = str(CONTEXT / relative)
    assert config == approved, 'unapproved effective Compose difference'
    assert launch['compose']['base']['networks']['default']['internal'] is False
    prepare.write(E / 'A.compose.json', config)
    # Import/AST validation only. The executor coroutine and JS owner are never run.
    module = bound_executor()
    assert module.launch_plan('A', launch['root'], PLAN, read(RECEIPT)) == launch
    assert module.require_runtime_assets() == verify_binding()
    module.validate_receipt(read(RECEIPT), read(PLAN), prepare.sha(PLAN))
    for path in (HERE / 'binding.py', HERE / 'preflight.py', PREP / 'execute.proposed.py'):
        ast.parse(path.read_text(), filename=str(path))
    for path in (PREP / 'browser-owner.proposed.mjs', PREP / 'browser-evidence.mjs', INTEGRATION / 'collect.mjs', INTEGRATION / 'browser.mjs'):
        run([str(TASK / 'backend/node'), '--check', path], 'syntax-' + path.name, 10)
    owner = (PREP / 'browser-owner.proposed.mjs').read_text()
    assert 'from "../perf391-diagnostic-integration-v1/collect.mjs"' in owner
    assert 'from "./browser.mjs"' in (INTEGRATION / 'collect.mjs').read_text()
    observer = (INTEGRATION / 'observer.mjs').read_text()
    assert 'period: 1000000000n' in observer
    assert 'b - a > 1500000000' in (PREP / 'analyze-runtime.py').read_text()
    report['checks']['selection'] = launch['corrected_identity']['selected_scripts']
    report['checks']['compose'] = {'whole_approved_config_matches':True,
        'allowed_differences':['two corrected A image IDs','context paths','project namespace'],
        'limits':{n:{k:s[k] for k in ('cpus','mem_limit','pids_limit','logging')} for n,s in config['services'].items()},
        'deadlines':launch['deadlines'], 'observer_max_cadence_ms':1500,
        'executor_loaded_not_executed':True}
    report['hashes'] = {name:prepare.sha(E / name) for name in ('launch-A.json','A.compose.base.json','A.compose.override.json','A.compose.json')}
    report['hashes']['identity-overlay.json'] = prepare.sha(HERE / 'identity-overlay.json')


def main():
    assert not TASK.exists(), 'audit prior task root before retry'
    prepare.write(E / 'ownership.json', {'pid':os.getpid(),'pgid':os.getpgid(0),
        'start_identity':Path('/proc/self/stat').read_text(), 'temporary_root':str(TASK),
        'containers':[OWNER+'-frontend',OWNER+'-backend'], 'owner_label':OWNER,
        'runtime_resources':[], 'scope':'offline only; stopped extraction containers never started'})
    TASK.mkdir()
    try:
        verify_binding()
        run([sys.executable,'-B',BUILT / 'verify-retained.py'], 'retained-validator', 120,
            {**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        prepare.build.verify_collector_release(REPO)
        regenerate()
        inspect_images()
        compile_and_render()
        report['status'] = 'PASS_OFFLINE_ONLY'
    except BaseException as error:
        report.update(status='STOP', failure=type(error).__name__+': '+str(error))
        raise
    finally:
        # Stopped-container context managers remove only the two recorded containers.
        shutil.rmtree(TASK)
        report['temporary_root_removed'] = not TASK.exists()
        prepare.write(E / 'verification.json', report)
    print(report['status'])


if __name__ == '__main__':
    main()
