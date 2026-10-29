"""Lossless publication of FAILED qualification evidence, with separate diagnosis."""
import gzip,hashlib,json
from pathlib import Path
S=Path(__file__).resolve().parent;W=Path('/home/oracle-worker/Work/starlink-dashboard/.worktrees/issue-393-clean-soak');D=W/'docs/performance/metric-lifecycle-2026-10-28/clean-soak-46ed6af6/results'
read=lambda p:json.loads(p.read_text());sha=lambda b:hashlib.sha256(b).hexdigest()
assert read(S/'sustained-001/run.json')['status']=='failed'
assert not read(S/'sustained-001/api-capture-summary.json')['qualification_clean']
assert all(read(S/(n+'-independent-cleanup.json'))['status']=='clean' for n in ['preflight-001','preflight-002','preflight-003','sustained-001'])
assert not D.exists();D.mkdir(parents=True);manifest=[]
def copy(p,target):
 raw=p.read_bytes();compressed=p.suffix=='.log' or (p.suffix in ['.jsonl','.openmetrics'] and len(raw)>262144)
 packed=gzip.compress(raw,compresslevel=6,mtime=0) if compressed else raw
 if compressed:target=target.with_name(target.name+'.gz')
 target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(packed)
 manifest.append({'source':str(p.relative_to(S)),'source_sha256':sha(raw),'source_bytes':len(raw),'artifact':str(target.relative_to(D)),'artifact_sha256':sha(packed),'artifact_bytes':len(packed),'encoding':'gzip' if compressed else 'identity'})
for name in ['preflight-001','preflight-002','preflight-003','sustained-001']:
 for p in sorted((S/name).iterdir()):
  if p.is_file():copy(p,D/name/p.name)
 for suffix in ['-runner.json','-independent-cleanup.json','.log']:
  p=S/(name+suffix)
  if p.exists():copy(p,D/'observers'/p.name)
 for p in sorted(S.glob('cardinality-'+name+'-*')):
  if p.is_file():copy(p,D/'observers'/p.name)
for p in sorted((S/'sustained-001-diagnosis').iterdir()):
 if p.is_file():copy(p,D/'diagnosis'/p.name)
for name in ['harness-v2-tests.log','sample-cardinality.py','verify-run-cleanup.py','launch.py','derive-failed-soak.py','package-failed.py','sustained-001-derived-resource-summary.json','ownership.json']:
 copy(S/name,D/'observers'/name)
(D/'manifest.json').write_text(json.dumps({'protocol':'lossless-publication-v1','native_sustained_status':'failed','clean_sustained_qualification':False,'description':'Exact native files; large JSONL/log/OpenMetrics files use deterministic gzip. Decompressed source hashes bind classifier inputs. Separate diagnosis does not relabel any native result.','files':manifest},indent=2)+'\n')
print(json.dumps({'destination':str(D),'files':len(manifest),'artifact_bytes':sum(x['artifact_bytes'] for x in manifest),'native_sustained_status':'failed'}))
