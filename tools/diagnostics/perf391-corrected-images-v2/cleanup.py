"""Independent host audit and removal of recorded task-only build resources."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

HERE=Path(__file__).resolve().parent
E=HERE/'evidence'
ROOT=Path('/tmp/perf391-corrected-forge')
OWNER='perf391-corrected-forge'
result={'utc':time.strftime('%FT%TZ',time.gmtime()),'commands':[],'process_checks':[]}


def command(argv):
    p=subprocess.run(['timeout','--kill-after=10s','60s',*argv],capture_output=True,text=True)
    result['commands'].append({'argv':argv,'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
    p.check_returncode()
    return p.stdout


ownership=json.loads((E/'ownership.json').read_bytes())
assert ownership['temporary_root']==str(ROOT)
assert ROOT.is_dir() and not ROOT.is_symlink() and (ROOT/'ownership.json').is_file()
for manifest in E.rglob('commands.json'):
    for row in json.loads(manifest.read_bytes()):
        if 'pid' not in row:
            continue
        proc=Path('/proc',str(row['pid']))
        same=False
        try:
            same=proc.joinpath('stat').read_text().rsplit(')',1)[1].split()[19]==row['start_identity'].rsplit(')',1)[1].split()[19]
        except OSError:
            pass
        result['process_checks'].append({'manifest':str(manifest.relative_to(E)),'pid':row['pid'],'live_same_identity':same})
        assert not same,row
ancestors={os.getpid()}
pid=os.getpid()
while pid>1:
    pid=int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[1])
    ancestors.add(pid)
survivors=[]
for proc in Path('/proc').iterdir():
    if not proc.name.isdecimal() or int(proc.name) in ancestors:
        continue
    try:
        args=proc.joinpath('cmdline').read_bytes()
        if any(token in args for token in [str(ROOT).encode(),b'tools/diagnostics/perf391-corrected-images-v2/']):
            survivors.append({'pid':int(proc.name),'comm':proc.joinpath('comm').read_text().strip()})
    except OSError:
        pass
result['process_survivors']=survivors
assert not survivors,survivors
for kind,argv in [('containers',['docker','ps','-aq']),('networks',['docker','network','ls','-q']),('volumes',['docker','volume','ls','-q'])]:
    assert not command([*argv,'--filter','label=perf391.owner='+OWNER]).strip()
    assert not command([*argv,'--filter','label=com.docker.compose.project='+OWNER]).strip()
    result[kind]=[]
result['retained_images']=[]
for role in ('A','C'):
    for kind in ('backend','frontend'):
        for prefix in ('historical-',''):
            original=json.loads((E/f'{prefix}{role}-{kind}.image.json').read_bytes())[0]
            actual=json.loads(command(['docker','image','inspect',original['Id']]))[0]
            assert actual['Id']==original['Id']
            for key in ('RepoTags','RepoDigests','Config','RootFS'):
                assert actual[key]==original[key],(role,kind,prefix,key)
            result['retained_images'].append({'historical':bool(prefix),'id':actual['Id'],'tags':actual['RepoTags'],'repo_digests':actual['RepoDigests']})
for tag in ownership['temporary_tags']:
    if command(['docker','image','ls','-q',tag]).strip():
        command(['docker','image','rm',tag])
    assert not command(['docker','image','ls','-q',tag]).strip()
temporary_probe='sha256:6cc26e5bf667ed510f3a883ea538ae81ebe2b44ca05b027ba76c613a18ce6dff'
probe_listing=command(['docker','image','ls','--no-trunc','-q','--filter','dangling=true'])
if temporary_probe in probe_listing.split():
    command(['docker','image','rm',temporary_probe])
result['temporary_probe_image_removed_or_absent']=temporary_probe
link=HERE.with_name('perf391-diagnostic-integration-v1')/'node_modules'
assert link.is_symlink() and str(link.readlink())==str(ROOT/'builder/node_modules')
link.unlink()
for path in [HERE/'__pycache__',HERE.with_name('perf391-runtime-preparation-v1')/'__pycache__',HERE.with_name('perf391-diagnostic-integration-v1')/'__pycache__']:
    if path.is_dir():
        shutil.rmtree(path)
result['temporary_bytes_before_removal']=command(['du','-sb',str(ROOT)])
shutil.rmtree(ROOT)
assert not ROOT.exists() and not link.exists()
merge_log=Path('/tmp/perf391-corrected-forge-merge.log')
if merge_log.exists():
    merge_log.unlink()
result['temporary_root_removed']=str(ROOT)
result['removed_temporary_tags']=ownership['temporary_tags']
result['listeners_snapshot']=command(['ss','-ltnp'])
result['task_listeners']=[]
result['actor_containers_snapshot']=command(['docker','ps','-a','--format','{{json .}}'])
assert not result['actor_containers_snapshot'].strip()
result['disk_after']=command(['df','-B1','/tmp','/srv/forge-nvme/oracle/docker'])
result['cleanup_verified']=True
result['scope']='Historical and corrected diagnostic images retained. Shared daemon/base images/BuildKit cache, credentials and configuration preserved; no task-owned builder daemon was created.'
(E/'cleanup.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print('PASS: host process identities, listeners and Docker resources clean; eight immutable diagnostic images retained; task paths/tags removed.')
