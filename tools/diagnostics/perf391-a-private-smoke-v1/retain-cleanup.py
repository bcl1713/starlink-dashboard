"""Independently inspect host identities/resources, retain raw evidence, remove owned scratch."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

HERE=Path(__file__).resolve().parent
E=HERE/'evidence'
TASK=Path('/tmp/perf391-a-private-smoke')
RUNTIME=Path('/tmp/perf391-smoke-408-a')
def command(argv):
    return subprocess.check_output(['timeout','--kill-after=2s','15s',*argv],text=True).strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert command(['hostname'])=='forge'
assert Path('/proc/1/comm').read_text().strip()=='systemd'
assert json.loads((TASK/'ownership.json').read_text())['task']==TASK.name
report={'utc':time.strftime('%FT%TZ',time.gmtime()),'actor_uid':os.getuid(),'pid_namespace':os.readlink('/proc/self/ns/pid'),'docker_host':os.environ.get('DOCKER_HOST'),'docker':{},'images':{},'process_survivors':[],'listeners':[],'removed_paths':[]}
identities=set();groups=set();manifests=[]
if RUNTIME.exists():
    for p in RUNTIME.rglob('manifest.json'):
        if any(x in p.relative_to(RUNTIME).parts for x in ('image-assets','host-collector')):continue
        m=json.loads(p.read_text())
        if 'owner' not in m:continue
        manifests.append({'path':str(p),'status':m.get('status')})
        for row in [m['owner'],*m.get('processes',[]),*m.get('adopted_processes',[])]:
            if row.get('pid') and row.get('start_id'):identities.add((row['pid'],row['start_id']))
            if row.get('pid')==row.get('pgid'):groups.add(row['pgid'])
    mapping=RUNTIME/'host-mapping.json'
    if mapping.exists():
        for row in json.loads(mapping.read_text()):identities.add((row['host_pid'],row['host_start_id']))
    browser=RUNTIME/'browser/browser-process.json'
    if browser.exists():
        row=json.loads(browser.read_text());identities.add((row['pid'],row['start_id']))
intent=E/'execution-intent.json'
if intent.exists():
    d=json.loads(intent.read_text());identities.add((d['supervisor_pid'],d['supervisor_start_id']));groups.add(d['timeout_pgid'])
ancestors=set();pid=os.getpid()
while pid and pid not in ancestors:
    ancestors.add(pid)
    try:pid=int(Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[1])
    except OSError:break
for p in Path('/proc').glob('[0-9]*'):
    if int(p.name) in ancestors:continue
    try:
        fields=(p/'stat').read_text().rsplit(')',1)[1].split()
        cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace');cwd=os.readlink(p/'cwd')
        if (int(p.name),fields[19]) in identities or int(fields[2]) in groups or any(marker in cmd or cwd.startswith(marker) for marker in (str(TASK),str(RUNTIME),str(HERE.parents[2]))):
            report['process_survivors'].append({'pid':int(p.name),'pgid':fields[2],'start_id':fields[19],'command':cmd,'cwd':cwd})
    except (OSError,IndexError):pass
report['checked_process_identities']=[{'pid':p,'start_id':s} for p,s in sorted(identities)]
report['owner_manifests']=manifests
for role in ('a','c'):
    project='perf391-smoke-408-'+role
    report['docker'][project]={kind:command([*argv,'--filter','label=com.docker.compose.project='+project]).splitlines() for kind,argv in [('containers',['docker','ps','-aq']),('networks',['docker','network','ls','-q']),('volumes',['docker','volume','ls','-q'])]}
for role in ('A','C'):
    receipt=json.loads((HERE.with_name('perf391-built-images-v1')/f'evidence/built-{role}.json').read_text())
    for kind,image in receipt['images'].items():
        actual=json.loads(command(['docker','image','inspect',image['id'],'--format','{{json .}}']))
        assert actual['Id']==image['id'] and actual['Config']['Labels']==image['labels'] and actual['RepoDigests']==image['repo_digests']
        report['images'][role+'-'+kind]=image['id']
ports=set(range(38080,38084))|set(range(38180,38184));report['ports_checked']=sorted(ports)
for line in command(['ss','-H','-ltnp']).splitlines():
    fields=line.split()
    if len(fields)>3 and fields[3].rsplit(':',1)[-1] in {str(p) for p in ports}:report['listeners'].append(line)
assert not report['process_survivors'] and not report['listeners'] and not any(v for project in report['docker'].values() for v in project.values()),report
assert all(m['status']=='clean' for m in manifests),manifests
inventory={};omitted={}
if RUNTIME.exists():
    assert json.loads((RUNTIME/'cleanup-audit.json').read_text())['clean']
    for p in RUNTIME.rglob('*'):
        assert not p.is_symlink(),p
        if not p.is_file():continue
        relative=p.relative_to(RUNTIME)
        row={'sha256':sha(p),'bytes':p.stat().st_size}
        inventory[str(relative)]=row
        if relative.parts[0] in ('image-assets','host-collector') or p.name=='history.openmetrics':
            omitted[str(relative)]=row
            continue
        dest=E/'runtime'/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
        assert sha(dest)==row['sha256']
    (E/'runtime-inventory.json').write_text(json.dumps({'all_files':inventory,'omitted_reproducible_inputs':omitted,'note':'Image assets and pinned collector retained in immutable packages; synthetic seed is reproducible from retained seed command.'},indent=2)+'\n')
for p in (RUNTIME,TASK):
    if p.exists():shutil.rmtree(p)
    assert not p.exists();report['removed_paths'].append(str(p))
lock=Path('/tmp/perf391-smoke-408.lock')
if lock.exists():
    assert lock.is_file() and lock.stat().st_size==0
    lock.unlink();report['removed_paths'].append(str(lock))
report['temporary_paths_absent']=all(not Path(p).exists() for p in report['removed_paths'])
report['clean']=True
(E/'final-host-cleanup.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
print('PASS: independent host cleanup; all recorded resources absent, evidence retained, private scratch removed')
