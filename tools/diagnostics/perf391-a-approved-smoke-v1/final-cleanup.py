"""Read-only host checks, then remove only recorded private scratch after retention."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent
E = HERE / 'evidence'
TASK = Path('/tmp/perf391-a-approved-smoke')
RUNTIME = Path('/tmp/perf391-smoke-408-a')

def command(argv):
    return subprocess.check_output(['timeout','--kill-after=5s','15s',*argv],text=True).strip()

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

assert command(['hostname']) == 'forge'
assert Path('/proc/1/comm').read_text().strip() == 'systemd'
assert json.loads((TASK/'ownership.json').read_text())['task'] == 'perf391-a-approved-smoke'
assert json.loads((RUNTIME/'cleanup-audit.json').read_text())['clean']
for p in RUNTIME.rglob('*'):
    if p.is_file() and p.relative_to(RUNTIME).parts[0] not in ('image-assets','host-collector') and p.name != 'history.openmetrics':
        assert sha(p) == sha(E/'runtime'/p.relative_to(RUNTIME)), str(p)
report={'utc':time.strftime('%FT%TZ',time.gmtime()),'actor_uid':os.getuid(),'pid_namespace':os.readlink('/proc/self/ns/pid'),'docker':{},'images':{},'process_survivors':[],'listeners':[],'removed_paths':[]}
identities=set()
groups=set()
for p in (RUNTIME/'manifest.json',RUNTIME/'verification-owner/manifest.json',RUNTIME/'cleanup-owner/manifest.json'):
    manifest=json.loads(p.read_text())
    assert manifest['status']=='clean'
    for row in [manifest['owner'],*manifest['processes'],*manifest['adopted_processes']]:
        if row.get('pid') and row.get('start_id'):identities.add((row['pid'],row['start_id']))
        if row.get('pid') == row.get('pgid'):groups.add(row['pgid'])
for row in json.loads((RUNTIME/'host-mapping.json').read_text()):
    identities.add((row['host_pid'],row['host_start_id']))
ancestors=set();pid=os.getpid()
while pid>0 and pid not in ancestors:
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
assert not report['process_survivors'] and not report['listeners'] and not any(v for project in report['docker'].values() for v in project.values())
for p in (RUNTIME,TASK):
    shutil.rmtree(p);assert not p.exists();report['removed_paths'].append(str(p))
lock=Path('/tmp/perf391-smoke-408.lock')
assert lock.is_file() and lock.stat().st_size==0
lock.unlink();report['removed_paths'].append(str(lock));report['clean']=True
(E/'final-host-cleanup.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
print('Independent Forge host cleanup verified; %d process identities absent; all recorded private scratch removed.' % len(identities))
