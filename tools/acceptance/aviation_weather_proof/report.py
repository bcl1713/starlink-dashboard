"""Fail-closed diagnostic gates over retained source, CPU and native GPU evidence."""
from __future__ import annotations
import json
from pathlib import Path
from .model import load_capture, file_hash, confined


def evaluate_proofs(evidence: Path) -> dict:
    gates: dict[str, dict] = {}
    def gate(name, check):
        try:
            check()
            gates[name]={'status':'passed'}
        except (AssertionError, OSError, ValueError, KeyError, TypeError) as error:
            gates[name]={'status':'failed','reason':str(error) or name}
    def read(name):
        return json.loads((evidence/name).read_text())
    def provenance():
        for source in ('gfs','isigmet','goes19-c13'):
            path=evidence/'captures'/source/'capture.json'
            capture=load_capture(path)
            assert capture.source==source
            d=read(f'products/{source}/descriptor.json')
            assert d['capture_manifest_sha256']==file_hash(path),'capture hash mismatch'
            assert {(o['url'],o['sha256'],o['byte_size']) for o in d.get('source_objects',d.get('provenance',{}).get('source_objects',[]))} == {(o.url,o.sha256,o.byte_size) for o in capture.objects},'source URL/hash mismatch'
            payloads=list(d.get('components',{}).values())+[d[k] for k in ('mask','advisories','records') if k in d]
            for p in payloads:
                f=confined(evidence/'products'/source,p['path'])
                assert f.stat().st_size==p['byte_size'] and file_hash(f)==p['sha256'],'payload mismatch'
    def native():
        j=read('browser/journey.json')
        assert j['native_overview'] and j['status']=='passed'
        assert len(j['captures'])>=12 and all((evidence/'browser'/name).stat().st_size>10000 for name in j['captures'])
        for source in ('gfs','goes19-c13'):
            samples=j['samples'][source]
            references=read(f'oracles/{source}-gpu.json')
            assert len(samples)>=10 and len(samples)==len(references)
            for sample,reference in zip(samples,references,strict=True):
                assert sample['mask']==reference['mask']==0,'failed mask readback'
                assert sample['quantity'][2]==sample['mask']
                assert abs(sample['value']-reference['values']['t'])<=sample['quantizationStep']+1e-9,'GPU quantity mismatch'
                assert abs(sample['sampleLatitude']-reference['latitude'])<1e-10
                assert abs(sample['sampleLongitude']-reference['longitude'])<1e-10
                value=reference['values']['t'];t=max(0,min(1,(value-190)/120))
                expected=[sample['base'][i]*.6+255*c*.4 for i,c in enumerate((t,.25,1-t))]
                assert max(abs(sample['color'][i]-expected[i]) for i in range(3))<=3,'palette/opacity mismatch'
        for snapshot in j['metrics']:
            peak=snapshot['allocation']['peak']
            assert 0<peak['gpu']<=16*1024**2 and 0<peak['decoded']<=32*1024**2 and 0<peak['encoded']<=16*1024**2,'GPU metrics missing/budget'
            assert snapshot['viewport']['width']>0 and snapshot['renderer']['version']
        assert j['metrics'],'missing GPU metrics'
        assert j['restored']['allocation']['current']=={'encoded':0,'decoded':0,'gpu':0},'owned allocation remains'
        assert all(r['allowed'] for r in read('browser/requests.json')),'browser provider request'
    def controls():
        j=read('browser/journey.json')
        assert all(j['controls'].values()) and len(j['controls'])>=7,'synthetic controls missing or failed'
        assert 'Coverage unverified' in j['advisory_label'] or 'Coverage incomplete' in j['advisory_label']
        assert '2026-10-06T12:07:27.898Z' in j['advisory_label']
        assert '2026-10-06T00:00:20.900Z' in j['satellite_label'] and '2026-10-06T00:09:52.800Z' in j['satellite_label']
    def cleanup():
        for name in ('cleanup.json','browser/browser-cleanup.json'):
            result=read(name)
            assert result['status']=='passed' and result.get('remaining')==[] and result.get('killed_descendants')==[],'absent cleanup or killed descendant'
    gate('real_source_provenance',provenance)
    gate('native_gpu_quantities_masks_palette',native)
    gate('synthetic_controls_and_time_labels',controls)
    gate('owned_runtime_cleanup',cleanup)
    return {'status':'passed' if all(g['status']=='passed' for g in gates.values()) else 'failed','diagnostic_only':True,'gates':gates,'unproven':['conditional WIFS access','flight-level interpolation','worldwide satellite seams','worldwide advisory completeness']}
