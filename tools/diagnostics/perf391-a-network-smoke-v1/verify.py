"""Offline hash/closure and outcome verification; never launches runtime resources."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[2];E=HERE/'evidence';R=E/'runtime'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
m=read(HERE/'artifact-manifest.json')
actual={str(p.relative_to(HERE)):sha(p) for p in HERE.rglob('*') if p.is_file() and p.name!='artifact-manifest.json'}
assert actual==m['files'],'package closure/hash mismatch'
for name,digest in m['external_files'].items():assert sha(REPO/name)==digest,name
out=read(E/'outcome.json'); pre=read(E/'preflight.json')
assert out['status']=='FAIL_BROWSER_FINALIZATION_STOP' and not out['complete_smoke_pass']
assert out['A_invocations']==1 and out['C_invocations']==0
assert read(E/'execution-exit.json')['exit_code']==1
assert pre['status']=='PASS_PREFLIGHT_NO_RUNTIME_STARTED'
assert len(pre['checks']['build_plan_comparison']['differences'])==4
assert pre['checks']['build_plan_sha256']=='8537bddee63b76d65f08548d447fbc93f42dfbe919b09f4fc9826d4e128954d5'
for role in ('A','C'):
 cfg=read(E/f'{role}.compose.json')
 assert set(cfg['networks'])=={'default'} and not cfg['networks']['default'].get('internal',False)
 assert all(p['host_ip']=='127.0.0.1' for s in cfg['services'].values() for p in s['ports'])
intent=read(E/'execution-intent.json')
assert intent['deadlines']=={'work_seconds':78,'outer_timeout_seconds':90,'kill_grace_seconds':10}
assert intent['executor_sha256']==sha(HERE.with_name('perf391-runtime-preparation-v1')/'execute.proposed.py')
assert intent['launcher_sha256']==sha(HERE.with_name('perf391-runtime-preparation-v1')/'launcher.py')
assert out['screenshot_attempts']==1 and out['screenshot']['outcome']=='unavailable'
assert out['screenshot']['reason']=='deadline'
assert out['actual_plot_commit_records']==0 and out['retained_projection_plot_snapshot_records']==0
assert not out['zero_loss_gate']
assert out['browser_collection']['closed'] and not out['browser_collection']['complete']
assert out['browser_collection']['dropped']==0 and out['browser_collection']['browsers'][0]['lost']==1
clock=read(E/'observations-and-clocks.json')
assert clock['requirement_ns']==1500000000 and clock['cadence_pass'] and len(clock['source_wakes'])==5
assert all(0<n<=clock['requirement_ns'] for n in clock['source_gap_ns'])
assert out['host_summary']==[{'kind':'summary','completed':5,'skipped':0,'complete':True}]
assert not (R/'backend/backend.jsonl').exists() and not (R/'browser/frontend-final.json').exists()
assert read(R/'cleanup-audit.json')['clean'] and read(E/'final-host-cleanup.json')['clean']
assert read(E/'final-host-audit.json')['cleanup_verified'] and read(E/'process-prerequisite.json')['status']=='PASS'
inv=read(E/'runtime-inventory.json')
for relative,entry in inv['all_files'].items():
 if relative not in inv['omitted_reproducible_inputs']:
  p=R/relative;assert sha(p)==entry['sha256'] and p.stat().st_size==entry['bytes'],relative
for relative,digest in read(R/'browser/node/summary.json')['artifacts'].items():assert sha(R/'browser/node'/relative)==digest
for p in read(E/'final-host-cleanup.json')['removed_paths']:assert not Path(p).exists(),p
for p in read(E/'github-states.json')['pull_requests']:assert p['state']=='open' and p['draft'] and not p['merged']
for p in read(E/'github-states.json')['issues']:assert p['state']=='open'
print(f'PASS evidence verification: {len(actual)} package files, {len(m["external_files"])} external pins; A FAILED, cleanup verified; no runtime launched')
