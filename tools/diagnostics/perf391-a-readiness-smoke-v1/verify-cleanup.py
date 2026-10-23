"""Independent read-only host resource audit and scoped scratch removal."""
import json, os, shutil, subprocess, time
from pathlib import Path
HERE=Path(__file__).resolve().parent
TASK=Path('/tmp/perf391-a-readiness-smoke')
RUNTIME=Path('/tmp/perf391-smoke-408-a')
assert subprocess.check_output(['hostname'],text=True).strip()=='forge'
assert Path('/proc/1/comm').read_text().strip()=='systemd'
assert json.loads((TASK/'ownership.json').read_text())['task']=='perf391-a-readiness-smoke'
def command(argv):
    return subprocess.check_output(['timeout','--kill-after=2s','10s',*argv],text=True).strip()
r={'utc':time.strftime('%FT%TZ',time.gmtime()),'pid_namespace':os.readlink('/proc/self/ns/pid'),'docker_host':os.environ.get('DOCKER_HOST'),'docker':{},'process_survivors':[],'listeners':[],'removed_paths':[],'runtime_attempts':0}
ancestors=set();pid=os.getpid()
while pid and pid not in ancestors:
    ancestors.add(pid)
    try:pid=int(Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[1])
    except OSError:break
for p in Path('/proc').glob('[0-9]*'):
    if int(p.name) in ancestors:continue
    try:
        cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace');cwd=os.readlink(p/'cwd')
        if any(marker in cmd or cwd.startswith(marker) for marker in (str(TASK),str(RUNTIME),str(HERE.parents[2]))):
            r['process_survivors'].append({'pid':int(p.name),'command':cmd,'cwd':cwd})
    except OSError:pass
for role in ('a','c'):
    project='perf391-smoke-408-'+role
    r['docker'][project]={k:command([*argv,'--filter','label=com.docker.compose.project='+project]).splitlines() for k,argv in [('containers',['docker','ps','-aq']),('networks',['docker','network','ls','-q']),('volumes',['docker','volume','ls','-q'])]}
ports=set(range(38080,38084))|set(range(38180,38184));r['ports_checked']=sorted(ports)
for line in command(['ss','-H','-ltnp']).splitlines():
    f=line.split()
    if len(f)>3 and f[3].rsplit(':',1)[-1] in {str(p) for p in ports}:r['listeners'].append(line)
r['runtime_root_absent']=not RUNTIME.exists()
r['lock_absent']=not Path('/tmp/perf391-smoke-408.lock').exists()
assert not r['process_survivors'] and not r['listeners'] and not any(v for group in r['docker'].values() for v in group.values()) and r['runtime_root_absent'] and r['lock_absent']
assert set(p.name for p in TASK.iterdir())=={'ownership.json'}
shutil.rmtree(TASK);assert not TASK.exists();r['removed_paths'].append(str(TASK));r['clean']=True
(HERE/'evidence/final-host-cleanup.json').write_text(json.dumps(r,sort_keys=True,indent=2)+'\n')
print('PASS: independent host audit; no task processes/listeners/Docker resources; scratch removed')
