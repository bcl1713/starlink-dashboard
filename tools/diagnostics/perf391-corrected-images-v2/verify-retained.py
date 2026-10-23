"""Revalidate versioned receipts using the existing closed receipt/asset validators."""
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
E=HERE/'evidence'
REPO=HERE.parents[2]
sys.path.insert(0,str(HERE.with_name('perf391-runtime-preparation-v1')))
import correction
import prepare
from launcher import validate_receipt


def verify():
    assert prepare.sha(prepare.HERE/'diagnostic-correction-overlay.json')=='43a28519858ed545e5fe2ed8720a1437985b40e4dd49f8d3675b5ea5f954a970'
    correction.verify_correction()
    hist=HERE.with_name('perf391-built-images-v1')
    old_manifest=json.loads((hist/'artifact-manifest.json').read_bytes())
    for name,expected in old_manifest['files'].items():
        assert prepare.sha(hist/name)==expected,name
    plan_path=E/'corrected-build-plan.json'
    plan=json.loads(plan_path.read_bytes())
    qualification=json.loads((E/'qualification.json').read_bytes())
    provenance=json.loads((E/'image-provenance.json').read_bytes())
    assert plan['runtime_authorized'] is False and qualification['runtime_executed'] is False
    assert (E/'original-runtime-build-plan.json').read_bytes()==(hist/'evidence/runtime-build-plan.json').read_bytes()
    receipts={}
    image_ids=set()
    from jsonschema import Draft202012Validator
    schema=json.loads((HERE/'receipt-schema.json').read_bytes())
    for role in ('A','C'):
        path=E/f'built-{role}.compat-v1.json'
        receipt=json.loads(path.read_bytes())
        validate_receipt(receipt,plan,prepare.sha(plan_path))
        lineage=json.loads((E/f'built-{role}.v2.json').read_bytes())
        Draft202012Validator(schema).validate(lineage)
        assert lineage==qualification['roles'][role]
        assert lineage['compatible_receipt_sha256']==prepare.sha(path)
        assert lineage['corrected_plan_sha256']==prepare.sha(plan_path)
        assert lineage['historical_receipt_sha256']==prepare.sha(hist/f'evidence/built-{role}.json')
        old=json.loads((hist/f'evidence/built-{role}.json').read_bytes())
        assert receipt['dependencies']==old['dependencies'] and receipt['browser']==old['browser']
        assert prepare.sha(E/f'{role}-python-packages.json')=='03cf956e500c08952d7b1a1747f24e391f6d0c5cf32a675a93c55847c92e9a40'
        for kind in ('backend','frontend'):
            img=json.loads((E/f'{role}-{kind}.image.json').read_bytes())[0]
            assert img['Id']==receipt['images'][kind]['id']==lineage['images'][kind]['corrected_id']
            assert old['images'][kind]['id']==lineage['images'][kind]['original_id']
            assert img['Config']['Labels']==receipt['images'][kind]['labels']
            assert img['RepoDigests']==receipt['images'][kind]['repo_digests']
            m=json.loads((E/f'{role}-{kind}.metadata.json').read_bytes())
            assert m['containerimage.digest']==img['Id']==provenance[role+'-'+kind]['id']
            expected=old['images'][kind]['id'] if kind=='backend' else plan['cached_dependency_image_id']
            assert expected.removeprefix('sha256:') in [x['digest']['sha256'] for x in m['buildx.build.provenance']['materials']]
            image_ids.update((img['Id'],old['images'][kind]['id']))
        receipts[role]=receipt
    assert len(image_ids)==8
    assert receipts['A']['assets']==receipts['C']['assets']
    assert qualification['frontend_parity'] and qualification['repeat_compile_byte_identical']
    assert prepare.sha(E/'A-assets/perf391-module-closure.json')==qualification['module_closure_sha256']
    assert (E/'frontend-builder-node-packages.json').read_bytes()==(hist/'evidence/frontend-builder-node-packages.json').read_bytes()
    assert 'npm ci --engine-strict --strict-ssl=true --no-audit --no-fund\n#10 CACHED' in (E/'cached-dependencies.log').read_text()
    assert 'Tests  10 passed (10)' in (E/'compiled-probe-tests.log').read_text()
    assert '# pass 42\n# fail 0' in (E/'node-focused-no-isolation.log').read_text()
    assert 'Exact compiled Finish:' in (E/'compiled-extraction-final.log').read_text()
    invocation=json.loads((E/'compiled-fixture-invocation.json').read_bytes())
    extraction=json.loads((E/'compiled-extraction.json').read_bytes())
    for key,path in [('retained_config_sha256',E/'compiled-vitest.config.mjs'),('compiled_fixture_module_sha256',E/'compiled-probe.mjs'),('log_sha256',E/'compiled-probe-tests.log'),('authentic_output_sha256',E/'compiled-authentic/verified.json')]:
        assert invocation[key]==prepare.sha(path)
    assert invocation['compiled_fixture_module_sha256']==extraction['compiled_fixture_module_sha256']
    assert invocation['fixture_source_sha256']==prepare.sha(HERE.with_name('perf391-diagnostic-integration-v1')/'tests/frontend/probe.test.ts')
    assert invocation['source_import_substitution']=={'../../browser-probe':'exact extracted compiled fixture module'}
    config=json.loads((E/'compiled-vitest.config.mjs').read_text().removeprefix('export default ').removesuffix(';\n'))
    assert config['resolve']['alias']=={'../../browser-probe':'/tmp/perf391-corrected-forge/compiled-probe.mjs'}
    compiled=(E/'A-assets'/extraction['chunk']).read_bytes()
    assert prepare.build.digest(compiled)==extraction['chunk_sha256']
    units=compiled.decode().encode('utf-16-le')
    for declaration in extraction['declarations']:
        exact=units[2*declaration['start']:2*declaration['end']].decode('utf-16-le').encode()
        assert prepare.build.digest(exact)==declaration['sha256']
    cleanup_path=E/'cleanup.json'
    if cleanup_path.exists():
        cleanup=json.loads(cleanup_path.read_bytes())
        assert cleanup['cleanup_verified'] and not cleanup['process_survivors']
        assert not Path(cleanup['temporary_root_removed']).exists()
        assert all(not row['live_same_identity'] for row in cleanup['process_checks'])
    manifest_path=HERE/'artifact-manifest.json'
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_bytes())
        actual={p.relative_to(HERE).as_posix() for p in HERE.rglob('*') if p.is_file() and p!=manifest_path}
        assert actual==set(manifest['files'])
        for name,expected in manifest['files'].items():
            assert prepare.sha(HERE/name)==expected,name
    print('PASS: correction provenance, old/new receipt lineage, 8 image identities, actual compiled closure/parity, dependencies and retained focused checks.')


if __name__=='__main__':
    verify()
