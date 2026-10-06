"""Mutation tests: each omitted receipt independently closes its report gate."""
import hashlib
import json
from pathlib import Path
import pytest
from acceptance.aviation_weather_proof.report import evaluate_proofs


def write(root,name,data):
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data));return p


@pytest.fixture
def complete(tmp_path:Path)->Path:
    digest=hashlib.sha256(b'x').hexdigest()
    for source in ('gfs','isigmet','goes19-c13'):
        obj={'url':'https://aviationweather.gov/test-unit-only','byte_range':None,'relative_path':'source.bin','sha256':digest,'byte_size':1}
        receipt=write(tmp_path,f'captures/{source}/capture.json',{'source':source,'captured_at_ms':1,'objects':[obj],'attribution':['UNIT TEST SYNTHETIC']})
        (receipt.parent/'source.bin').write_bytes(b'x')
        write(tmp_path,f'products/{source}/descriptor.json',{'capture_manifest_sha256':hashlib.sha256(receipt.read_bytes()).hexdigest(),'source_objects':[obj]})
    sample={'mask':0,'quantity':[0,0,0,255],'value':250,'sampleLatitude':0,'sampleLongitude':0,'quantizationStep':.01,'base':[0,0,0],'color':[51,25.5,51]}
    j={'native_overview':True,'status':'passed','captures':[f'{i}.png' for i in range(12)],'samples':{s:[sample]*10 for s in ('gfs','goes19-c13')},'metrics':[{'allocation':{'peak':{'gpu':8,'decoded':16,'encoded':1}},'viewport':{'width':1},'renderer':{'version':'TEST'}}],'restored':{'allocation':{'current':{'encoded':0,'decoded':0,'gpu':0}}},'controls':{str(i):True for i in range(7)},'advisory_label':'Coverage unverified 2026-10-06T12:07:27.898Z','satellite_label':'2026-10-06T00:00:20.900Z 2026-10-06T00:09:52.800Z'}
    write(tmp_path,'browser/journey.json',j)
    for name in j['captures']:(tmp_path/'browser'/name).write_bytes(b'x'*10001)
    for source in ('gfs','goes19-c13'):write(tmp_path,f'oracles/{source}-gpu.json',[{'mask':0,'values':{'t':250},'latitude':0,'longitude':0}]*10)
    write(tmp_path,'browser/requests.json',[{'allowed':True}])
    for name in ('cleanup.json','browser/browser-cleanup.json'):write(tmp_path,name,{'status':'passed','remaining':[],'killed_descendants':[]})
    return tmp_path


def test_structurally_complete_unit_fixture_passes(complete):
    assert evaluate_proofs(complete)['status']=='passed'


@pytest.mark.parametrize('fault',['missing_capture','hash_mismatch','url_mismatch','gpu_metrics','mask','cleanup','killed_descendant'])
def test_incomplete_proof_never_passes(complete:Path,fault:str):
    if fault=='missing_capture':(complete/'captures/gfs/source.bin').unlink()
    elif fault in ('hash_mismatch','url_mismatch'):
        path=complete/'products/gfs/descriptor.json';d=json.loads(path.read_text());d['source_objects'][0]['sha256' if fault=='hash_mismatch' else 'url']='mismatch';path.write_text(json.dumps(d))
    elif fault in ('gpu_metrics','mask'):
        path=complete/'browser/journey.json';j=json.loads(path.read_text())
        if fault=='gpu_metrics':j['metrics']=[]
        else:j['samples']['gfs'][0]['mask']=3
        path.write_text(json.dumps(j))
    elif fault=='cleanup':(complete/'cleanup.json').unlink()
    else:write(complete,'browser/browser-cleanup.json',{'status':'passed','remaining':[],'killed_descendants':[12345]})
    assert evaluate_proofs(complete)['status']=='failed'


def test_empty_evidence_is_failed(tmp_path:Path):
    assert evaluate_proofs(tmp_path)['status']=='failed'
