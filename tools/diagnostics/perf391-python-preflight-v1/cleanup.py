"""Scoped host audit and removal of this checkpoint's private scratch only."""
import json, os, pathlib, shutil, subprocess
root=pathlib.Path('/tmp/perf391-python-preflight')
e=pathlib.Path(__file__).resolve().parent/'evidence'
def run(argv):
    p=subprocess.run(argv,capture_output=True,text=True,check=True,timeout=20)
    return p.stdout
assert pathlib.Path('/proc/1/comm').read_text().strip()=='systemd'
ancestors=set(); pid=os.getpid()
while pid:
    ancestors.add(pid)
    pid=int(pathlib.Path(f'/proc/{pid}/status').read_text().split('PPid:')[1].splitlines()[0])
processes=run(['ps','-u',str(os.getuid()),'-o','pid=,ppid=,pgid=,args='])
survivors=[line for line in processes.splitlines() if '/tmp/perf391-python-preflight' in line and int(line.split()[0]) not in ancestors]
assert not survivors,survivors
resources={}
for project in ('perf391-preflight-contract','perf391-smoke-408-a','perf391-smoke-408-c'):
    for kind,argv in {'containers':['docker','ps','-aq'],'networks':['docker','network','ls','-q'],'volumes':['docker','volume','ls','-q']}.items():
        result=run([*argv,'--filter','label=com.docker.compose.project='+project]).strip()
        resources[project+'/'+kind]=result
        assert not result
listeners=run(['ss','-ltnp'])
assert not any(':'+str(port)+' ' in listeners for base in (38080,38180) for port in range(base,base+4))
assert root.is_dir() and (e/'ownership.json').is_file()
shutil.rmtree(root)
assert not root.exists()
(e/'cleanup.json').write_text(json.dumps({'status':'PASS','host':run(['hostname']).strip(),'host_pid1':'systemd','task_process_survivors':survivors,'compose_resources':resources,'ports_38080_38083_38180_38183_free':True,'scratch_removed':str(root),'private_venvs_and_wheels_removed':True,'resources_started':False,'worktree_retained_for_review':True},indent=2)+'\n')
