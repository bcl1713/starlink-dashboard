"""Call existing corrected offline validators; retain their exact generated context."""
import asyncio, ctypes, json, os, shutil, socket, subprocess, sys, time
from pathlib import Path
HERE=Path(__file__).resolve().parent; E=HERE/'evidence'/'completed-a'; REPO=HERE.parents[2]
sys.path.insert(0,str(HERE.with_name('perf391-corrected-a-runtime-v2')))
import preflight as p
from binding import bound_executor, verify_binding, compile_launch
p.E=E; p.forge.E=E
report={'scope':'corrected A only; preflight; no services or browser launch','starting_commit':'dce002876b3b04316d3e1b1e0b1ba37b11bf3de6','authorization':'https://github.com/bcl1713/starlink-dashboard/pull/408#issuecomment-6373144033','commands':[],'checks':{}}
def save():p.prepare.write(E/'preflight.json',report)
def command(argv,seconds=30):
 raw=p.run(argv,'host-check-%02d'%len(report['commands']),seconds)
 report['commands'].append({'argv':list(map(str,argv)),'output':raw.decode()});save();return raw.decode()
continuing=any(flag in sys.argv for flag in ('--continue-owner','--continue-activation'))
if continuing:
 shutil.copyfile(E/'preflight.json',E/('preflight-before-activation.json' if '--continue-activation' in sys.argv else 'preflight-before-owner.json'))
 report=p.read(E/'preflight.json')
 assert report['failure']==('NameError: name \'receipt\' is not defined' if '--continue-activation' in sys.argv else 'ValueError: synthetic owner required')
 p.report=report['checks']['corrected_preflight']
 assert p.TASK.is_dir()
 assert p.prepare.build.tree_manifest(p.CONTEXT)['tree_sha256']==p.read(p.PLAN)['roles']['A']['context_sha256']
 verify_binding()
 report['administrative_owner_correction']={'previous_name':'corrected-a-preflight','name':'synthetic-corrected-a-preflight','previous_error':'synthetic owner required','completed_preflight_stages_repeated':False}
 report.pop('failure')
else:
 assert not p.TASK.exists()
p.prepare.write(E/('owner-continuation-ownership.json' if continuing else 'context-ownership.json'),{'pid':os.getpid(),'pgid':os.getpgrp(),'start_identity':Path('/proc/self/stat').read_text(),'temporary_root':str(p.TASK),'runtime_resources':[],'containers':[p.OWNER+'-frontend',p.OWNER+'-backend']})
try:
 if not continuing:
  assert command(['hostname']).strip()=='forge'
  assert Path('/proc/1/comm').read_text().strip()=='systemd'
  assert command(['git','rev-parse','HEAD']).strip()==report['starting_commit']
  assert os.environ.get('DOCKER_HOST')=='unix:///run/user/1002/docker.sock'
  assert 'name=rootless' in json.loads(command(['docker','info','--format','{{json .SecurityOptions}}']))
  command(['docker','context','show']);command(['docker','context','inspect','--format','{{.Endpoints.docker.Host}}']);command(['docker','compose','version'])
  report['checks']['daemon']=command(['docker','info','--format','{{.Name}} {{.ServerVersion}} {{.Driver}} {{.NCPU}} {{.MemTotal}} {{.CgroupVersion}}']).strip()
  report['checks']['process_visibility']={'pid1':Path('/proc/1/comm').read_text().strip(),'namespace':os.readlink('/proc/self/ns/pid'),'cgroup':Path('/proc/self/cgroup').read_text()}
  report['checks']['headroom']={'disk_free_bytes':shutil.disk_usage('/tmp').free,'memory_available_bytes':int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024}
  assert report['checks']['headroom']['disk_free_bytes']>4*1024**3
  assert report['checks']['headroom']['memory_available_bytes']>6*1024**3
  group=Path('/sys/fs/cgroup')/Path('/proc/self/cgroup').read_text().strip()[3:].lstrip('/')
  report['checks']['cgroup_limits']={}
  for parent in (group,*group.parents):
   if parent==Path('/sys/fs'):break
   for n in ('cpu.max','memory.max','memory.current','pids.max','pids.current'):
    path=parent/n
    if path.is_file():report['checks']['cgroup_limits'][str(path)]=path.read_text().strip()
  for project in ('perf391-smoke-408-a','perf391-smoke-408-c','perf391-corrected-a-preflight'):
   for argv in (['docker','ps','-aq'],['docker','network','ls','-q'],['docker','volume','ls','-q']):
    assert not command([*argv,'--filter','label=com.docker.compose.project='+project]).strip()
  for port in range(38080,38084):
   with socket.socket() as s:s.bind(('127.0.0.1',port))
  assert not Path('/tmp/perf391-smoke-408-a').exists() and not Path('/tmp/perf391-smoke-408.lock').exists()
  # Read-only historical package validation before this invocation creates its context.
  # Preserve historical evidence; validate its closure and only relocate five roles.
  command([sys.executable,'-B',p.BUILT/'verify-retained.py'],180)
  retained_e=p.HERE/'evidence'
  retained_report=p.read(retained_e/'verification.json')
  assert retained_report['status']=='PASS_OFFLINE_ONLY' and not retained_report['runtime_executed']
  for name,digest in retained_report['hashes'].items():
   assert p.prepare.sha((p.HERE if name=='identity-overlay.json' else retained_e)/name)==digest
  artifact=p.read(p.HERE/'artifact-manifest.json')
  actual={f.relative_to(p.HERE).as_posix() for f in p.HERE.rglob('*') if f.is_file() and f.name!='artifact-manifest.json' and '__pycache__' not in f.parts}
  assert actual==set(artifact['files'])
  for name,digest in artifact['files'].items():
   f=p.HERE/name
   assert not f.is_symlink() and p.prepare.sha(f)==digest
  for role in ('A','C'):
   p.launcher.validate_receipt(p.read(p.HIST/f'evidence/built-{role}.json'),p.read(p.HIST/'evidence/runtime-build-plan.json'),p.prepare.sha(p.HIST/'evidence/runtime-build-plan.json'))
  retained=p.read(retained_e/'launch-A.json');fresh=compile_launch()
  old_root='/home/oracle-worker/Work/starlink-dashboard/.worktrees/perf391-corrected-runtime/'
  roles=[(('commands',4,'argv',1),'tools/diagnostics/perf391-runtime-preparation-v1/browser-owner.proposed.mjs',''),
         (('corrected_identity','build_plan'),'tools/diagnostics/perf391-corrected-images-v2/evidence/corrected-build-plan.json',''),
         (('corrected_identity','executor_adapter'),'tools/diagnostics/perf391-corrected-a-runtime-v2/binding.py',':bound_executor'),
         (('corrected_identity','lineage'),'tools/diagnostics/perf391-corrected-images-v2/evidence/built-A.v2.json',''),
         (('corrected_identity','receipt'),'tools/diagnostics/perf391-corrected-images-v2/evidence/built-A.compat-v1.json','')]
  import copy
  relocated=copy.deepcopy(retained);proof=[]
  for keys,relative,suffix in roles:
   old=retained;new=fresh;target=relocated
   for key in keys[:-1]:old=old[key];new=new[key];target=target[key]
   path=REPO/relative
   assert path.is_file() and path.resolve()==path and path.is_relative_to(REPO)
   assert all(not parent.is_symlink() for parent in (path,*path.parents))
   source=p.prepare.build.git(REPO,'show',report['starting_commit']+':'+relative)
   assert path.read_bytes()==source
   assert old[keys[-1]]==old_root+relative+suffix
   assert new[keys[-1]]==str(path)+suffix
   target[keys[-1]]=new[keys[-1]]
   proof.append({'field':list(keys),'relative_role':relative,'sha256':p.prepare.sha(path),'source_commit':report['starting_commit'],'no_symlink_escape':True})
  assert relocated==fresh,'non-path launch identity drift'
  assert p.prepare.sha(retained_e/'launch-A.json')=='f15d657727bd029e54233e783cfa1acdf18f6889c7180f9dba4158c4182ce0e2'
  report['checks']['path_relocation']={'roles':proof,'all_non_path_fields_exact':True,'historical_launch_unchanged':True}
  save()
  verify_binding();p.prepare.build.verify_collector_release(REPO)
  p.TASK.mkdir()
  p.regenerate();p.inspect_images();p.compile_and_render()
  report['checks']['corrected_preflight']=p.report
  receipt=p.read(p.RECEIPT)
  assert 'not found' not in command(['ldd',receipt['browser']['chromium_executable']])
  historical=Path(shutil.which('node')).resolve()
  report['checks']['historical_node']={'sha256':p.prepare.sha(historical),'version':command([str(historical),'--version']).strip()}
  assert report['checks']['historical_node']['sha256']=='177208bfc4a9403121a40c72d038c670f4fd937fa16ca7df0a720e90be0fe2d9'
 # Exercise existing Owner in host namespace, bounded by this runner's outer timeout.
 assert ctypes.CDLL(None).prctl(36,1,0,0,0)==0
 from owner import Owner,members,start_id
 async def own():
  owner=Owner(E/'prerequisite-owner',run='synthetic-corrected-a-preflight',sources={},adopt_descendants=True)
  child=None
  try:
   child=owner.spawn([sys.executable,'-c','import time; time.sleep(30)'])
   report['checks']['process_prerequisite']={'pid':child.pid,'pgid':os.getpgid(child.pid),'start_id':start_id(child.pid)};save()
  finally:result=await owner.close()
  assert child.returncode is not None and result['status']=='clean' and not members(child.pid)
  report['checks']['process_prerequisite'].update(child_reaped=True,group_absent=True,owner_status=result['status'])
 if '--continue-activation' not in sys.argv:asyncio.run(own())
 else:assert report['checks']['process_prerequisite']['child_reaped'] and report['checks']['process_prerequisite']['group_absent']
 receipt=p.read(p.RECEIPT)
 module=bound_executor()
 assert Path(module.execute.__code__.co_filename).resolve()==p.PREP/'execute.proposed.py'
 assert module.launch_plan('A','/tmp/perf391-smoke-408-a',p.PLAN,receipt)==compile_launch()
 report['checks']['activation']={'factory':'binding.bound_executor','entrypoint':'execute','executor_sha256':p.prepare.sha(p.PREP/'execute.proposed.py'),'binding_sha256':p.prepare.sha(p.HERE/'binding.py'),'overlay_sha256':p.prepare.sha(p.HERE/'identity-overlay.json'),'no_external_hook_replacements':True,'cli_execute_rejection_preserved':True}
 report['status']='PASS_PREFLIGHT_CONTEXT_RETAINED_FOR_ONE_A'
except BaseException as error:
 report.update(status='STOP_PREFLIGHT',failure=type(error).__name__+': '+str(error));save();raise
finally:save()
print(report['status'])
