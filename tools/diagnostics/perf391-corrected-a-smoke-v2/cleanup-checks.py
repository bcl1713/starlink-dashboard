"""Independent Forge-host audit and scoped removal after preflight STOP."""
import hashlib,json,os,shutil,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;E=HERE/'evidence'/'completed-a'
TASK=Path('/tmp/perf391-corrected-a-smoke-20261023')
report={'utc':time.strftime('%FT%TZ',time.gmtime()),'pid':os.getpid(),'pgid':os.getpgrp(),'start_identity':Path('/proc/self/stat').read_text(),'runtime_invocations':int((E/'activation.json').exists()),'commands':[],'process_checks':[]}
def save(): (E/'cleanup.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
def command(argv):
 p=subprocess.run(['timeout','--kill-after=10s','30s',*argv],capture_output=True,text=True)
 report['commands'].append({'argv':argv,'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr});save();p.check_returncode();return p.stdout
assert Path('/proc/1/comm').read_text().strip()=='systemd'
rows=[]
for name in ('preparation-ownership.json','context-ownership.json'):
 r=json.loads((E/name).read_bytes());rows.append(r);rows.extend(r.get('commands',[]))
rows.extend(json.loads((E/'commands.json').read_bytes()))
rows.extend(json.loads((E/'supervisor.json').read_bytes()))
for name in ('owner-continuation-ownership.json','activation.json'):
 if (E/name).exists():rows.append(json.loads((E/name).read_bytes()))
for path in (E/'runtime').rglob('manifest.json'):
 data=json.loads(path.read_bytes())
 if 'owner' in data:
  row=data['owner'];proc=Path('/proc',str(row['pid']),'stat')
  try:same=proc.read_text().rsplit(')',1)[1].split()[19]==row['start_id']
  except OSError:same=False
  report['process_checks'].append({'pid':row['pid'],'pgid':row['pgid'],'live_same_identity':same,'manifest':str(path.relative_to(E))})
  assert not same,row
for row in rows:
 if 'pid' not in row:continue
 try: same=Path('/proc',str(row['pid']),'stat').read_text().rsplit(')',1)[1].split()[19]==row['start_identity'].rsplit(')',1)[1].split()[19]
 except OSError:same=False
 report['process_checks'].append({'pid':row['pid'],'pgid':row['pgid'],'live_same_identity':same})
 assert not same,row
ancestors={os.getpid()};pid=os.getpid()
while pid>1:
 pid=int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[1]);ancestors.add(pid)
survivors=[]
tokens=[str(TASK).encode(),b'/tmp/perf391-corrected-a-preflight',b'/tmp/perf391-smoke-408-a',str(HERE).encode()]
for proc in Path('/proc').iterdir():
 if not proc.name.isdecimal() or int(proc.name) in ancestors:continue
 try:
  raw=(proc/'cmdline').read_bytes()
  if any(token in raw for token in tokens):survivors.append({'pid':int(proc.name),'comm':(proc/'comm').read_text().strip()})
 except OSError:pass
report['process_survivors']=survivors;assert not survivors,survivors
report['task_process_groups']=[]
for row in report['process_checks']:
 try:os.killpg(row['pgid'],0)
 except ProcessLookupError:report['task_process_groups'].append({'pgid':row['pgid'],'absent':True});continue
 # Preparation scripts inherit a caller group; command runners own new sessions.
 # A reused/caller group is not task-owned: no signal is sent to it.
 report['task_process_groups'].append({'pgid':row['pgid'],'exists_but_recorded_task_pid_absent':True})
for kind,argv in [('containers',['docker','ps','-aq']),('networks',['docker','network','ls','-q']),('volumes',['docker','volume','ls','-q'])]:
 for label in ('com.docker.compose.project=perf391-smoke-408-a','com.docker.compose.project=perf391-smoke-408-c','perf391.owner=perf391-corrected-a-preflight','com.docker.compose.project=perf391-corrected-a-preflight'):
  assert not command([*argv,'--filter','label='+label]).strip()
 report[kind]=[]
for name in ('perf391-corrected-a-preflight-frontend','perf391-corrected-a-preflight-backend','perf391-smoke-408-a-assets'):
 assert not command(['docker','ps','-aq','--filter','name=^/'+name+'$']).strip()
listeners=command(['ss','-ltnp'])
assert not any(':'+str(port)+' ' in listeners for port in range(38080,38084));report['task_listeners']=[]
# Evidence is retained in this package before removing disposable runtime/context.
for root in (Path('/tmp/perf391-smoke-408-a'),Path('/tmp/perf391-corrected-a-preflight')):
 if root.exists():
  assert not root.is_symlink()
  if root.name=='perf391-smoke-408-a':assert (E/'runtime/runtime-result.json').is_file()
  shutil.rmtree(root)
lock=Path('/tmp/perf391-smoke-408.lock')
if lock.exists():
 import fcntl
 with lock.open('a') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);lock.unlink()
assert not Path('/tmp/perf391-corrected-a-preflight').exists()
assert not Path('/tmp/perf391-smoke-408-a').exists()
assert not Path('/tmp/perf391-smoke-408.lock').exists()
report['preserved_images']=[]
built=HERE.with_name('perf391-corrected-images-v2')/'evidence'
for role in ('A','C'):
 for kind in ('backend','frontend'):
  for prefix in ('historical-',''):
   old=json.loads((built/f'{prefix}{role}-{kind}.image.json').read_bytes())[0]
   actual=json.loads(command(['docker','image','inspect',old['Id']]))[0]
   assert all(actual[k]==old[k] for k in ('Id','RepoTags','RepoDigests','Config','RootFS','Architecture','Os'))
   report['preserved_images'].append(actual['Id'])
report['temporary_inventory']={}
assert TASK.is_dir() and not TASK.is_symlink()
for path in (TASK/'wheels').iterdir():report['temporary_inventory'][str(path)]={'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
report['removed_paths']=[str(TASK)];report['removal_intent_persisted']=True;save()
shutil.rmtree(TASK)
report['temporary_paths_absent']=[str(path) for path in (TASK,Path('/tmp/perf391-corrected-a-preflight'),Path('/tmp/perf391-smoke-408-a'),Path('/tmp/perf391-smoke-408.lock')) if not path.exists()]
assert len(report['temporary_paths_absent'])==4
report['cleanup_verified']=True;save()
print('PASS: host PID/start identities absent; scoped processes/listeners/containers/networks/volumes absent; private dependencies removed; all eight images unchanged')
