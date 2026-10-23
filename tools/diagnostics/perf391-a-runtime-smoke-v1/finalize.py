"""Retain partial evidence, independently verify ownership, remove only task files."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

HERE=Path(__file__).resolve().parent
E=HERE/'evidence'
TASK=Path('/tmp/perf391-a-runtime-20261023')
RUNTIME=Path('/tmp/perf391-smoke-408-a')
BUILT=HERE.with_name('perf391-built-images-v1')/'evidence'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,r):p.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
assert json.loads((TASK/'ownership.json').read_text())['task']=='perf391-a-runtime-20261023'
assert json.loads((RUNTIME/'cleanup-audit.json').read_text())['clean']
retained=E/'runtime'
retained.mkdir()
for p in RUNTIME.iterdir():
    if p.name in ('image-assets','tmp'):continue
    if p.is_dir():shutil.copytree(p,retained/p.name)
    else:shutil.copyfile(p,retained/p.name)
assets={p.relative_to(RUNTIME/'image-assets').as_posix():sha(p) for p in (RUNTIME/'image-assets').rglob('*') if p.is_file()}
receipt=json.loads((BUILT/'built-A.json').read_text())
assert assets==receipt['assets']
write(E/'extracted-asset-hashes.json',assets)
shutil.copyfile(TASK/'ownership.json',E/'preparation-ownership.json')
write(E/'stream-status.json',{
    'run_id':'synthetic-408a','attempts':{'A':1,'C':0},'phase_reached':'seed-tsdb',
    'instrumentation_end_to_end':False,'backend_started':False,'browser_launch_attempts':0,
    'scheduled_source_observations':5,'completed_source_observations':0,
    'scheduled_host_observations':5,'completed_host_observations':0,
    'chart_evidence_chains':0,'compositor_screenshot_attempts':0,
    'producer_worker_admission_observer_evidence':'unavailable: application never started',
    'backend_final_summary':None,'browser_final_summary':None,'host_final_summary':None,
    'dropped_event_counts':None,'dropped_event_counts_reason':'unavailable: producers/collectors never started; no zero-loss claim',
    'owner_streams':json.loads((RUNTIME/'manifest.json').read_text())['streams'],
    'expected_unavailable':['raw-wire capture','native Axios parse-start','original-A CAS/final-authority/frame semantics'],
    'observer_cadence_gate_seconds':1.5,'observer_cadence_result':'not exercised; not waived',
    'clock_domains':{'execution_intent_and_exit':'host UTC wall clock; not phase durations',
        'owner_start_id':'Forge Linux /proc stat starttime ticks since boot',
        'ticks_per_second':os.sysconf('SC_CLK_TCK'),
        'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'work_deadline':'executor time.monotonic, 78 seconds; enclosing GNU timeout 90 seconds + 10 seconds kill grace',
        'browser_backend_operation_clocks':'unavailable: neither process launched'},
    'C_ready':False,'stop':'startup failure; no retry; separately reviewed correction required before any future runtime authorization'})
# Independent second host audit checks all recorded owner and child identities/groups.
rows=[]
for name in ('manifest.json','verification-owner/manifest.json','cleanup-owner/manifest.json'):
    m=json.loads((RUNTIME/name).read_text())
    rows.extend([m['owner'],*m['processes'],*m['adopted_processes']])
identities={(r['pid'],r['start_id']) for r in rows}
groups={r['pgid'] for r in rows if r.get('pgid')==r['pid']}
report={'utc':time.strftime('%FT%TZ',time.gmtime()),'recorded_process_identities':len(identities),'process_survivors':[],'path_process_survivors':[],'docker':{},'images':{},'removed_paths':[]}
for p in Path('/proc').iterdir():
    if not p.name.isdecimal() or int(p.name)==os.getpid():continue
    try:
        f=(p/'stat').read_text().rsplit(')',1)[1].split()
        if (int(p.name),f[19]) in identities or int(f[2]) in groups:
            report['process_survivors'].append({'pid':int(p.name),'pgid':int(f[2]),'start_id':f[19]})
        args=(p/'cmdline').read_bytes().split(b'\0')
        if any(a.startswith(str(TASK).encode()+b'/') or a.startswith(str(RUNTIME).encode()+b'/') for a in args):
            report['path_process_survivors'].append(int(p.name))
    except (OSError,IndexError):pass
def command(argv):return subprocess.check_output(['timeout','--kill-after=5s','15s',*argv],text=True)
for role in ('a','c'):
    project='perf391-smoke-408-'+role
    report['docker'][project]={}
    for kind,argv in [('containers',['docker','ps','-aq']),('networks',['docker','network','ls','-q']),('volumes',['docker','volume','ls','-q'])]:
        output=command([*argv,'--filter','label=com.docker.compose.project='+project]).split()
        assert not output,(project,kind,output)
        report['docker'][project][kind]=output
for role in ('A','C'):
    r=json.loads((BUILT/f'built-{role}.json').read_text())
    for kind,image in r['images'].items():
        actual=json.loads(command(['docker','image','inspect',image['id'],'--format','{{json .}}']))
        assert actual['Id']==image['id'] and actual['Config']['Labels']==image['labels']
        report['images'][role+'-'+kind]=image['id']
listeners=command(['ss','-ltn'])
ports=[*range(38080,38084),*range(38180,38184)]
assert not any(':'+str(p)+' ' in listeners for p in ports)
report['ports_absent']=ports
assert not report['process_survivors'] and not report['path_process_survivors']
assert not list((RUNTIME/'tmp').rglob('*'))
for p in (TASK,RUNTIME):
    shutil.rmtree(p)
    assert not p.exists()
    report['removed_paths'].append(str(p))
lock=Path('/tmp/perf391-smoke-408.lock')
if lock.exists():
    import fcntl
    with lock.open('r+') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        assert lock.stat().st_size==0
        lock.unlink()
    report['removed_paths'].append(str(lock))
report['clean']=True
write(E/'final-host-cleanup.json',report)
print('Final host ownership audit clean; partial runtime retained, assets hashed, all task disposable paths removed; four accepted images retained.')
