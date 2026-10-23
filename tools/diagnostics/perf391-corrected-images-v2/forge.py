"""Bounded offline forge; never starts application containers or browsers."""
import contextlib
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
E = HERE / 'evidence'
ROOT = Path('/tmp/perf391-corrected-forge')
SOURCE = '31b1fbbfded503344e9df653ba148850a2e69f95'
DELIVERY = 'e40b9ff240ce97af0c03ac254b52a8af084634bd'
ORIGINAL = 'f9cf80bd4fe7915863cf7e0ed5a6bc52616c377b'
CORRECTION = '43a28519858ed545e5fe2ed8720a1437985b40e4dd49f8d3675b5ea5f954a970'
OWNER = 'perf391-corrected-forge'
HIST = REPO / 'tools/diagnostics/perf391-built-images-v1'
RUNTIME = REPO / 'tools/diagnostics/perf391-runtime-preparation-v1'
INTEGRATION = REPO / 'tools/diagnostics/perf391-diagnostic-integration-v1'
sys.path.insert(0, str(RUNTIME))
import prepare
import correction
from launcher import validate_receipt


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(p, v):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(v, indent=2, sort_keys=True) + '\n')


def files(root):
    result = {}
    for p in sorted(root.rglob('*')):
        if p.is_file():
            assert not p.is_symlink(), p
            result[p.relative_to(root).as_posix()] = sha(p)
    return result


ledger = []
active = None


def run(argv, name, seconds=120, env=None):
    global active
    log = E / (name + '.log')
    row = {'argv': list(map(str, argv)), 'name': name, 'seconds': seconds, 'grace_seconds': 10, 'state': 'intent'}
    ledger.append(row)
    write(E / 'commands.json', ledger)
    start = time.monotonic()
    with log.open('wb') as out:
        active = subprocess.Popen(['timeout', '--kill-after=10s', str(seconds)+'s', *map(str, argv)], cwd=REPO, env=env, stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
        row.update(pid=active.pid, pgid=os.getpgid(active.pid), start_identity=Path('/proc', str(active.pid), 'stat').read_text(), state='running')
        write(E / 'commands.json', ledger)
        try:
            rc = active.wait()
        except BaseException:
            if active.poll() is None:
                os.killpg(active.pid, signal.SIGTERM)
                try:
                    active.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(active.pid, signal.SIGKILL)
                    active.wait()
            active = None
            raise
        active = None
    row.update(exit=rc, wall_seconds=time.monotonic()-start, state='exited')
    write(E / 'commands.json', ledger)
    assert rc == 0, (name, rc, log)
    return log.read_bytes()


def stop(sig, frame):
    raise SystemExit(128 + sig)


for s in (signal.SIGINT, signal.SIGTERM):
    signal.signal(s, stop)


@contextlib.contextmanager
def stopped(image, suffix):
    name = OWNER + '-' + suffix
    # Intent is persisted before Docker creates any container.
    cid = run(['docker', 'create', '--pull=never', '--name', name, '--label', 'perf391.owner='+OWNER, '--entrypoint', '/bin/false', image], name+'-create').decode().strip()
    try:
        yield cid
    finally:
        state = json.loads(run(['docker', 'inspect', cid], name+'-inspect'))[0]
        write(E / (name+'.container.json'), state)
        assert state['State']['Status'] == 'created' and state['State']['Pid'] == 0 and state['State']['StartedAt'].startswith('0001-')
        run(['docker', 'rm', cid], name+'-remove')


def copy(cid, source, target, name):
    target.parent.mkdir(parents=True, exist_ok=True)
    run(['docker', 'cp', cid+':'+source, target], name)


def inspect(image, name):
    data = json.loads(run(['docker', 'image', 'inspect', image], name+'-inspect-image'))[0]
    write(E / (name+'.image.json'), [data])
    return data


def main():
    assert not ROOT.exists()
    ROOT.mkdir()
    shutil.copyfile(E/'ownership.json', ROOT/'ownership.json')
    overlay = json.loads((RUNTIME/'diagnostic-correction-overlay.json').read_bytes())
    assert sha(RUNTIME/'diagnostic-correction-overlay.json') == CORRECTION
    audit = correction.verify_correction()
    # Approved source and delivery agree on every correction source byte.
    for name, entry in overlay['source_files'].items():
        for commit in (SOURCE, DELIVERY):
            assert hashlib.sha256(prepare.build.git(REPO, 'show', commit+':'+name)).hexdigest() == entry['sha256']
    manifest = json.loads((INTEGRATION/'correction-artifact-manifest.json').read_bytes())
    for name, expected in manifest['files'].items():
        assert sha(INTEGRATION/name) == expected, name
    # Retained historical evidence is immutable, including complete file closure.
    old_manifest = json.loads((HIST/'artifact-manifest.json').read_bytes())
    for name, expected in old_manifest['files'].items():
        assert sha(HIST/name) == expected, name
    old_plan_path = HIST/'evidence/runtime-build-plan.json'
    old_plan = json.loads(old_plan_path.read_bytes())
    assert sha(old_plan_path) == overlay['immutable_files']['tools/diagnostics/perf391-built-images-v1/evidence/runtime-build-plan.json']
    historical = {}
    for role in ('A', 'C'):
        receipt = json.loads((HIST/f'evidence/built-{role}.json').read_bytes())
        validate_receipt(receipt, old_plan, sha(old_plan_path))
        for kind, img in receipt['images'].items():
            actual = inspect(img['id'], 'historical-'+role+'-'+kind)
            assert actual['Id'] == img['id'] and actual['Config']['Labels'] == img['labels'] and actual['RepoDigests'] == img['repo_digests']
            historical[role+'-'+kind] = actual
    write(E/'source-verification.json', {'correction':audit, 'correction_sha256':CORRECTION, 'source_commit':SOURCE, 'delivery_commit':DELIVERY, 'correction_evidence_files':len(manifest['files']), 'historical_evidence_files':len(old_manifest['files']), 'historical_plan_sha256':sha(old_plan_path)})
    # Export the original guarded compiler. Keep its source gates intact.
    baseline = ROOT/'baseline'
    baseline.mkdir()
    raw = prepare.build.git(REPO, 'archive', '--format=tar', ORIGINAL, 'tools/diagnostics/perf391-diagnostic-integration-v1', 'tools/diagnostics/perf391-runtime-preparation-v1')
    for name, (data, mode) in prepare.build.archive_files(raw).items():
        p=baseline/name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        p.chmod(0o755 if mode=='100755' else 0o644)
    env = {**os.environ, 'GIT_DIR': str(REPO/'.git'), 'PYTHONDONTWRITEBYTECODE':'1'}
    # Linked-worktree gitdir file is not a directory; select resolved common dir.
    env['GIT_DIR'] = str(REPO.parents[1]/'.git')
    contexts=ROOT/'contexts'
    run(['python3', baseline/'tools/diagnostics/perf391-runtime-preparation-v1/prepare.py', '--output', contexts], 'regenerate-original-plan', 300, env)
    assert (contexts/'runtime-build-plan.json').read_bytes() == old_plan_path.read_bytes(), 'original plan not reproduced'
    shutil.copyfile(contexts/'runtime-build-plan.json', E/'original-runtime-build-plan.json')
    plan=json.loads(old_plan_path.read_bytes())
    plan.update(schema='perf391-corrected-build-plan-v2', qualification='diagnostic_build_only', runtime_authorized=False, correction_source=SOURCE, correction_delivery=DELIVERY, correction_overlay_sha256=CORRECTION, original_plan_sha256=sha(old_plan_path))
    changed=('browser-probe.ts', 'browser.mjs', 'collect.mjs')
    dependency_tag='perf391-diag-408-corrected-dependencies:31b1fbbf'
    dependency_recipe=(RUNTIME/'frontend.Dockerfile').read_text().split('COPY frontend/mission-planner/ ./')[0]
    (E/'cached-dependencies.Dockerfile').write_text(dependency_recipe)
    run(['docker','build','--pull=false','--platform','linux/amd64','--progress','plain','--metadata-file',E/'cached-dependencies.metadata.json','-f',E/'cached-dependencies.Dockerfile','-t',dependency_tag,contexts/'A'],'cached-dependencies',90)
    cache_log=(E/'cached-dependencies.log').read_text()
    assert 'npm ci --engine-strict --strict-ssl=true --no-audit --no-fund\n#10 CACHED' in cache_log
    plan['cached_dependency_image_id']=json.loads((E/'cached-dependencies.metadata.json').read_bytes())['containerimage.digest']
    plan['cached_dependency_recipe_sha256']=sha(E/'cached-dependencies.Dockerfile')
    for role in ('A','C'):
        context=contexts/role
        for name in changed:
            target=context/'.perf391/diagnostic'/name
            assert sha(target)==overlay['source_files'][str((INTEGRATION/name).relative_to(REPO))]['predecessor_sha256']
            shutil.copyfile(INTEGRATION/name,target)
        labels=dict(old_plan['roles'][role]['labels'])
        labels.update({'perf391.correction.source':SOURCE, 'perf391.correction.delivery':DELIVERY, 'perf391.correction.overlay.sha256':CORRECTION, 'perf391.qualification':'diagnostic-build-only', 'perf391.owner':OWNER})
        labels['runtime_frontend_closure_sha256']=prepare.build.digest(prepare.build.canonical({'original':labels['runtime_frontend_closure_sha256'], 'correction_overlay_sha256':CORRECTION, 'probe_sha256':sha(INTEGRATION/'browser-probe.ts')}))
        plan['roles'][role]['labels']=labels
        plan['roles'][role]['diagnostic_modules'].update({n:sha(INTEGRATION/n) for n in changed})
        suffix='\n'.join('LABEL '+k+'='+json.dumps(v) for k,v in labels.items())+'\n'
        backend_base=historical[role+'-backend']['Id']
        # Exact historical rootfs/dependencies plus the three approved diagnostic files.
        backend='FROM perf391-diag-408-'+role.lower()+'-backend:f9cf80bd\n'
        backend+='\n'.join('COPY .perf391/diagnostic/'+n+' /diagnostic/'+n for n in changed)+'\n'
        backend+='LABEL perf391.lineage.parent='+json.dumps(backend_base)+'\n'+suffix
        frontend=(RUNTIME/'frontend.Dockerfile').read_text()+'\nLABEL perf391.lineage.parent='+json.dumps(historical[role+'-frontend']['Id'])+'\n'+suffix
        frontend='FROM '+dependency_tag+' AS builder\n'+frontend.split('COPY frontend/mission-planner/ ./',1)[1]
        frontend=frontend.replace('\nCOPY .perf391/diagnostic/', '\nCOPY frontend/mission-planner/ ./\nCOPY .perf391/diagnostic/',1)
        for kind,recipe in [('backend',backend),('frontend',frontend)]:
            (context/'.perf391'/f'{kind}.Dockerfile').write_text(recipe)
            shutil.copyfile(context/'.perf391'/f'{kind}.Dockerfile', E/f'{role}.{kind}.Dockerfile')
        plan['roles'][role]['context_sha256']=prepare.build.tree_manifest(context)['tree_sha256']
        plan['roles'][role]['overlay_inventory']=prepare.build.tree_manifest(context/'.perf391')
        write(E/f'{role}-context-inventory.json',prepare.build.tree_manifest(context))
    write(E/'corrected-build-plan.json',plan)
    write(E/'backend-decision.json',{'rebuild':True,'application_python_changed':False,'backend_python_probes_changed':False,'host_preservation_changes':['backend_evidence.py','execute.proposed.py','analyze-runtime.py'],'reason':'Host preservation code is not an image payload; both backend images nevertheless bundle the three corrected diagnostic modules. Re-layer those files over historical immutable backend IDs to qualify a consistent corrected module closure without dependency resolution.','changed_image_files':list(changed),'historical_plan_unchanged':True})
    build_stage()


def build_stage():
    old_plan_path=HIST/'evidence/runtime-build-plan.json'
    contexts=ROOT/'contexts'
    plan=json.loads((E/'corrected-build-plan.json').read_bytes())
    historical={role+'-'+kind:json.loads((E/f'historical-{role}-{kind}.image.json').read_bytes())[0] for role in ('A','C') for kind in ('backend','frontend')}
    correction.verify_correction()
    for role in ('A','C'):
        assert prepare.build.tree_manifest(contexts/role)['tree_sha256']==plan['roles'][role]['context_sha256']
        actual=json.loads(run(['docker','image','inspect','perf391-diag-408-'+role.lower()+'-backend:f9cf80bd'],'recheck-base-'+role))[0]
        assert actual['Id']==historical[role+'-backend']['Id']
    # Record the configured daemon and resource bounds, no environment dump.
    run(['docker','info','--format','{{.ID}} {{.Name}} {{.ServerVersion}} {{.Driver}} {{.CgroupVersion}}'],'daemon')
    run(['docker','buildx','du'],'cache-before')
    run(['df','-B1','/tmp','/srv/forge-nvme/oracle/docker'],'disk-before')
    run(['sh','-c','cat /sys/fs/cgroup/user.slice/user-1002.slice/cpu.max /sys/fs/cgroup/user.slice/user-1002.slice/memory.max'],'actor-limits')
    for role in ('A','C'):
        for kind in ('backend','frontend'):
            tag=f'perf391-diag-408-corrected-{role.lower()}-{kind}:31b1fbbf'
            if run(['docker','image','ls','-q',tag],role+'-'+kind+'-tag-check').strip():
                actual=inspect(tag,role+'-'+kind)
                assert all(actual['Config']['Labels'][k]==v for k,v in plan['roles'][role]['labels'].items())
                assert kind=='backend' and (ROOT/(role+'-backend')/'global-site-packages').is_dir()
                continue
            run(['docker','build','--pull=false','--network=none','--platform','linux/amd64','--progress','plain','--metadata-file',E/f'{role}-{kind}.metadata.json','-f',E/f'{role}.{kind}.Dockerfile','-t',tag,contexts/role], 'build-'+role+'-'+kind,600)
            actual=inspect(tag,role+'-'+kind)
            assert actual['Id'] not in [i['Id'] for i in historical.values()]
            assert all(actual['Config']['Labels'][k]==v for k,v in plan['roles'][role]['labels'].items())
            with stopped(actual['Id'],role.lower()+'-'+kind) as cid:
                if kind=='frontend':
                    copy(cid,'/usr/share/nginx/html',E/f'{role}-assets',role+'-assets-copy')
                    copy(cid,'/etc/nginx/conf.d/default.conf',E/f'{role}-nginx.conf',role+'-nginx-copy')
                    copy(cid,'/lib/apk/db/installed',E/f'{role}-frontend-apk-installed.txt',role+'-apk-copy')
                else:
                    for source,name in [('/diagnostic','diagnostic'),('/app','app'),('/acceptance','acceptance'),('/usr/local/bin/node','node'),('/var/lib/dpkg/status','dpkg-status'),('/opt/customer-briefing/assets','renderer-assets'),('/home/appuser/.local/lib/python3.11/site-packages','site-packages'),('/usr/local/lib/python3.11/site-packages','global-site-packages')]:
                        copy(cid,source,ROOT/(role+'-backend')/name,role+'-backend-copy-'+name)
    # Re-run the exact compile in the pinned cached builder, compare every byte.
    frontend=(E/'A.frontend.Dockerfile').read_text()
    marker='FROM nginx:alpine@'
    before,after=frontend.split(marker,1)
    recipe=before+'RUN cp -a dist /tmp/repro-dist && rm -rf dist && ./node_modules/.bin/tsc --noEmit --incremental false -p tsconfig.perf391.json && ./node_modules/.bin/vite build --config vite.perf391.mjs && diff -qr /tmp/repro-dist dist\n'+marker+after
    (E/'reproduce.frontend.Dockerfile').write_text(recipe)
    temp_tag='perf391-diag-408-corrected-builder:31b1fbbf'
    try:
        run(['docker','build','--pull=false','--network=none','--target','builder','--platform','linux/amd64','--progress','plain','-f',E/'reproduce.frontend.Dockerfile','-t',temp_tag,contexts/'A'],'reproduce-compile',600)
        with stopped(temp_tag,'builder') as cid:
            for source,name in [('/workspace/frontend/mission-planner/node_modules','node_modules'),('/workspace/frontend/mission-planner/package-lock.json','package-lock.json'),('/usr/local/bin/node','node'),('/usr/local/lib/node_modules/npm/package.json','npm-package.json'),('/workspace/frontend/mission-planner/dist','dist')]:
                copy(cid,source,ROOT/'builder'/name,'builder-copy-'+name)
        built=files(ROOT/'builder/dist')
        served=files(E/'A-assets')
        assert served==files(E/'C-assets')
        assert {k:served[k] for k in built}==built
        assert set(served)-set(built)=={'50x.html'}
        assert served['50x.html']==json.loads((HIST/'evidence/built-A.json').read_bytes())['assets']['50x.html']
    finally:
        run(['docker','image','rm',temp_tag],'remove-temporary-builder')
    qualify_stage()


def qualify_stage():
    old_plan_path=HIST/'evidence/runtime-build-plan.json'
    contexts=ROOT/'contexts'
    plan=json.loads((E/'corrected-build-plan.json').read_bytes())
    historical={role+'-'+kind:json.loads((E/f'historical-{role}-{kind}.image.json').read_bytes())[0] for role in ('A','C') for kind in ('backend','frontend')}
    built=files(ROOT/'builder/dist')
    served=files(E/'A-assets')
    assert served==files(E/'C-assets')
    assert {k:served[k] for k in built}==built
    assert set(served)-set(built)=={'50x.html'}
    assert served['50x.html']==json.loads((HIST/'evidence/built-A.json').read_bytes())['assets']['50x.html']
    # Qualify actual installed package metadata against the unchanged lock.
    builder=ROOT/'builder'
    assert sha(builder/'node')=='81925c0995b5c1427b5d538e6a90ca2fdc4daffb786b09af749beaf7369d4e90'
    assert run([builder/'node','--version'],'node-version').decode().strip()=='v22.22.2'
    assert json.loads((builder/'npm-package.json').read_bytes())['version']=='10.9.7'
    lock=json.loads((builder/'package-lock.json').read_bytes())
    installed=json.loads((builder/'node_modules/.package-lock.json').read_bytes())
    packages={}
    for name,item in installed['packages'].items():
        package=builder/name/'package.json'
        data=json.loads(package.read_bytes())
        assert data['version']==item['version']==lock['packages'][name]['version']
        assert item.get('integrity')==lock['packages'][name].get('integrity')
        packages[name]={'name':data['name'],'version':data['version'],'package_json_sha256':sha(package),'lock_integrity':item.get('integrity')}
    write(E/'frontend-builder-node-packages.json',packages)
    assert (E/'frontend-builder-node-packages.json').read_bytes()==(HIST/'evidence/frontend-builder-node-packages.json').read_bytes()
    shutil.copyfile(builder/'node_modules/.package-lock.json',E/'frontend-builder-installed-package-lock.json')
    shutil.copyfile(builder/'package-lock.json',E/'package-lock.json')
    write(E/'toolchain.json',{'node_version':'22.22.2','node_sha256':sha(builder/'node'),'npm_version':'10.9.7','packages':len(packages),'package_inventory_sha256':sha(E/'frontend-builder-node-packages.json'),'npm_lock_sha256':sha(E/'package-lock.json'),'network':'none','sourcemaps':False})
    results={}
    for role in ('A','C'):
        root=ROOT/(role+'-backend')
        context=contexts/role
        modules=files(root/'diagnostic')
        assert modules==files(context/'.perf391/diagnostic')
        old_modules=json.loads((HIST/f'evidence/{role}-backend-modules.json').read_bytes())
        assert files(root/'acceptance')==old_modules['acceptance']
        source={n:sha(root/'app'/n) for n in ('main.py','config.yaml')}
        for dirname in ('app','tests'):
            source.update({dirname+'/'+k:v for k,v in files(root/'app'/dirname).items()})
        assert source==old_modules['application']
        assert files(root/'renderer-assets')==json.loads((HIST/f'evidence/{role}-renderer-assets.json').read_bytes())
        assert sha(root/'dpkg-status')==sha(HIST/f'evidence/{role}-backend-dpkg-status.txt')
        assert sha(E/f'{role}-frontend-apk-installed.txt')==sha(HIST/f'evidence/{role}-frontend-apk-installed.txt')
        assert sha(E/f'{role}-nginx.conf')==sha(context/'frontend/mission-planner/nginx.conf')
        found={}
        for dirname in ('global-site-packages','site-packages'):
            for dist in importlib.metadata.distributions(path=[str(root/dirname)]):
                import re
                found[re.sub(r'[-_.]+','-',dist.metadata['Name']).lower()]={'name':dist.metadata['Name'],'version':dist.version}
        package_bytes=(json.dumps([found[k] for k in sorted(found)])+'\n').encode()
        assert package_bytes==(HIST/f'evidence/{role}-python-packages.json').read_bytes()
        (E/f'{role}-python-packages.json').write_bytes(package_bytes)
        write(E/f'{role}-backend-modules.json',{'diagnostic':modules,'acceptance':old_modules['acceptance'],'application':source})
        old_receipt=json.loads((HIST/f'evidence/built-{role}.json').read_bytes())
        receipt=dict(old_receipt)
        receipt.update(plan_sha256=sha(E/'corrected-build-plan.json'),asset_root=str(E/f'{role}-assets'),assets=files(E/f'{role}-assets'),images={})
        for kind in ('backend','frontend'):
            actual=json.loads((E/f'{role}-{kind}.image.json').read_bytes())[0]
            receipt['images'][kind]={'id':actual['Id'],'labels':actual['Config']['Labels'],'repo_digests':actual['RepoDigests']}
            if kind=='backend':
                assert actual['RootFS']['Layers'][:len(historical[role+'-'+kind]['RootFS']['Layers'])]==historical[role+'-'+kind]['RootFS']['Layers']
                assert actual['Config']['Cmd']==historical[role+'-'+kind]['Config']['Cmd']
                assert actual['Config']['Entrypoint']==historical[role+'-'+kind]['Config']['Entrypoint']
        validate_receipt(receipt,plan,sha(E/'corrected-build-plan.json'))
        write(E/f'built-{role}.compat-v1.json',receipt)
        lineage={'schema':'perf391-corrected-image-receipt-v2','role':role,'qualification':'diagnostic-build-only','runtime_authorized':False,'source_commit':SOURCE,'delivery_commit':DELIVERY,'correction_overlay_sha256':CORRECTION,'original_plan_sha256':sha(old_plan_path),'corrected_plan_sha256':sha(E/'corrected-build-plan.json'),'historical_receipt_sha256':sha(HIST/f'evidence/built-{role}.json'),'compatible_receipt_sha256':sha(E/f'built-{role}.compat-v1.json'),'images':{kind:{'original_id':historical[role+'-'+kind]['Id'],'corrected_id':receipt['images'][kind]['id']} for kind in ('backend','frontend')},'assets_sha256':prepare.build.digest(prepare.build.canonical(receipt['assets'])),'backend_module_inventory_sha256':sha(E/f'{role}-backend-modules.json')}
        write(E/f'built-{role}.v2.json',lineage)
        results[role]=lineage
    write(E/'qualification.json',{'schema':'perf391-corrected-build-qualification-v2','runtime_executed':False,'roles':results,'frontend_parity':True,'repeat_compile_byte_identical':True,'asset_count':len(files(E/'A-assets')),'module_closure_sha256':sha(E/'A-assets/perf391-module-closure.json'),'source_maps':'disabled by retained recipe; module graph retained','backend_source_and_dependencies_preserved':True})
    print('Corrected images built and offline receipts qualified; cleanup pending.',flush=True)


if __name__=='__main__':
    if '--qualify-only' in sys.argv:
        ledger.extend(json.loads((E/'commands.json').read_bytes()))
        qualify_stage()
    elif '--resume-build' in sys.argv:
        ledger.extend(json.loads((E/'commands.json').read_bytes()))
        build_stage()
    else:
        main()
