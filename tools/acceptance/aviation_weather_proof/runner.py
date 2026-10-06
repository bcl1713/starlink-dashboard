"""Exact-candidate diagnostic lifecycle. Run through run.sh's wall-clock limit."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from .report import evaluate_proofs
from acceptance.platform.evidence import prepare_evidence_parent,write_artifacts,seal_fingerprint,verify_manifest,read_fingerprint_authority

ROOT=Path(__file__).resolve().parents[3]
PROJECT='starlink-290-aviation-proof'
IMAGE='sha256:da6d08532bcd1336d6f3d217859700c96b32efa31c47ac2b6b43b5d3d58bed9a'


def prepare_fixture_mount(products: Path) -> None:
    """Permit app UID traversal inside the read-only normalized-only bind mount."""
    for path in (products, *products.rglob("*")):
        if path.is_symlink():
            raise ValueError("fixture mount cannot contain symlinks")
        path.chmod(0o755 if path.is_dir() else 0o644)


def run(candidate:str,captures:Path,profile:Path)->int:
    if not re.fullmatch('[0-9a-f]{40}',candidate):raise ValueError('clean 40-hex SHA required')
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=candidate or subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip():raise ValueError('candidate must be clean tracked HEAD')
    for port in (15290,18290):
        with socket.socket() as listener:listener.bind(('127.0.0.1',port))
    label=f'com.docker.compose.project={PROJECT}'
    def remaining():
        return {kind:subprocess.check_output(command,text=True).split() for kind,command in {'containers':['docker','ps','-aq','--filter',f'label={label}'],'networks':['docker','network','ls','-q','--filter',f'label={label}'],'volumes':['docker','volume','ls','-q','--filter',f'label={label}']}.items()}
    if any(remaining().values()):raise ValueError('existing private project cannot be adopted')
    stage=Path(tempfile.mkdtemp(prefix='starlink-290-task5-attempt-'))
    os.chmod(stage,0o700)
    source=stage/'source';source.mkdir()
    output=stage/'evidence';output.mkdir()
    children:list[dict]=[];workers:list[str]=[];killed:list[int]=[];active=None;started=False;failure=None
    owner={'candidate':candidate,'pid':os.getpid(),'pgid':os.getpgrp(),'command':sys.argv,'project':PROJECT,'ports':[15290,18290],'temporary_paths':[str(stage)],'private_volumes':['missions','settings','satellites','coverage','routes','simulation-routes','pois','metrics'],'workers':workers,'children':children}
    def write_owner():(output/'runtime-owner.json').write_text(json.dumps(owner,indent=2))
    write_owner()
    def command(argv:list[str],name:str,seconds=120,env=None):
        nonlocal active
        with (output/(name+'.log')).open('wb') as log:
            children.append({'command':argv,'name':name,'state':'starting'});write_owner()
            active=subprocess.Popen(argv,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
            children[-1].update(pid=active.pid,pgid=active.pid);write_owner()
            try:
                code=active.wait(timeout=seconds)
                if code:raise RuntimeError(f'{name} exit {code}; {log.name}')
            finally:
                if active.poll() is None:
                    os.killpg(active.pid,signal.SIGTERM)
                    try:active.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        killed.append(active.pid);os.killpg(active.pid,signal.SIGKILL);active.wait(timeout=5)
                children[-1]['returncode']=active.returncode;write_owner();active=None
    env={**os.environ,'WEATHER_ACCEPTANCE_PROJECT':PROJECT,'WEATHER_ACCEPTANCE_FRONTEND_PORT':'15290','WEATHER_ACCEPTANCE_BACKEND_PORT':'18290','WEATHER_ACCEPTANCE_SOURCE_ROOT':str(source),'WEATHER_ACCEPTANCE_CAPTURE_DIR':str(output/'products'),'WEATHER_ACCEPTANCE_CONTROL_DIR':str(output/'control'),'WEATHER_ACCEPTANCE_MODE':'aviation-proof','ACCEPTANCE_CANDIDATE_SHA':candidate}
    compose=['docker','compose','-p',PROJECT,'-f',str(ROOT/'tools/acceptance/overview-weather/compose.yml')]
    def worker(mode,name):
        worker_name=f'{PROJECT}-{mode}-{name}'
        workers.append(worker_name);write_owner()
        args=['docker','create','--name',worker_name,'--label',f'{PROJECT}.owner={candidate}','--network','none','--cpus','1','--memory','1g','--memory-swap','1g','--pids-limit','64','--entrypoint','python','--mount',f'type=bind,src={source}/tools,dst=/work/tools,readonly','--mount',f'type=bind,src={output},dst=/evidence','--mount',f'type=bind,src={output}/captures,dst=/evidence/captures,readonly','-w','/work','-e','PYTHONPATH=/work/tools','-e','OPENBLAS_NUM_THREADS=1','-e','OMP_NUM_THREADS=1',IMAGE,'-m','acceptance.aviation_weather_proof.worker',mode,name,'/evidence']
        command(args,f'{mode}-{name}-create')
        try:
            command(['timeout','--kill-after=10s','120s','docker','start','--attach',worker_name],f'{mode}-{name}',135)
            command(['docker','inspect',worker_name],f'{mode}-{name}-inspect')
            info=json.loads((output/f'{mode}-{name}-inspect.log').read_text())[0]
            if info['State']['ExitCode']!=0 or info['State']['OOMKilled']:raise RuntimeError('scientific worker failed')
        finally:
            command(['docker','stop','--time','10',worker_name],f'{mode}-{name}-stop',20)
            command(['docker','rm',worker_name],f'{mode}-{name}-remove')
    try:
        command(['git','archive','--format=tar','-o',str(stage/'candidate.tar'),candidate],'archive')
        command(['tar','-xf',str(stage/'candidate.tar'),'-C',str(source)],'extract')
        shutil.copytree(captures/'captures',output/'captures')
        for directory in ('products','oracles','control','browser'):(output/directory).mkdir()
        (output/'control'/'control.json').write_text('{}')
        os.chmod(output/'control',0o777);os.chmod(output/'control'/'control.json',0o666)
        for name in ('gfs','isigmet','goes19-c13'):worker('normalize',name)
        prepare_fixture_mount(output/'products')
        command(['docker','info','--format','{{.ServerVersion}} {{.Name}}'],'docker-runtime')
        command(compose+['config'],'compose',env=env)
        command(['timeout','--kill-after=10s','15m',*compose,'build'],'build',920,env)
        started=True
        command(compose+['up','--no-build','--detach','--wait','--wait-timeout','180'],'start',210,env)
        command(['docker','image','inspect',f'{PROJECT}-backend:{candidate}',f'{PROJECT}-frontend:{candidate}'],'images')
        command([sys.executable,'-m','acceptance.aviation_weather_proof.run_browser','--origin','http://127.0.0.1:15290','--artifacts',str(output/'browser'),'--profile',str(profile)],'browser',650,{**os.environ,'PYTHONPATH':str(ROOT/'tools')})
        for name in ('gfs','goes19-c13'):worker('sample',name)
    except BaseException as error:
        failure=f'{type(error).__name__}: {error}'
        (output/'failure.json').write_text(json.dumps({'error':failure}))
    finally:
        cleanup_errors=[]
        if started:
            for arguments,name in ((['logs','--no-color'],'containers'),(['down','--volumes','--remove-orphans','--timeout','10'],'compose-cleanup')):
                try:command(compose+arguments,name,60,env)
                except BaseException as error:cleanup_errors.append(str(error))
        for name in workers:
            result=subprocess.run(['docker','inspect',name],capture_output=True,text=True)
            if result.returncode==0:
                subprocess.run(['docker','stop','--time','10',name],capture_output=True,timeout=20)
                subprocess.run(['docker','rm',name],capture_output=True,timeout=20)
        remnants=remaining()
        for kind,values in remnants.items():cleanup_errors.extend(f'{kind}:{value}' for value in values)
        for child in children:
            if 'pgid' not in child:continue
            try:os.killpg(child['pgid'],0)
            except ProcessLookupError:pass
            else:cleanup_errors.append(f"process-group:{child['pgid']}")
        for port in (15290,18290):
            try:
                with socket.socket() as listener:listener.bind(('127.0.0.1',port))
            except OSError:cleanup_errors.append(f'listener:{port}')
        (output/'cleanup.json').write_text(json.dumps({'status':'passed' if not cleanup_errors and not killed else 'failed','remaining':cleanup_errors,'killed_descendants':killed,'docker':remnants,'ports':[15290,18290],'verified_at_ms':int(time.time()*1000)},indent=2))
        shutil.rmtree(source)
        (stage/'candidate.tar').unlink(missing_ok=True)
    result=evaluate_proofs(output)
    if failure:result['runner_error']=failure;result['status']='failed'
    (output/'evaluation.json').write_text(json.dumps(result,indent=2))
    parent=prepare_evidence_parent(Path('/srv/starlink-acceptance/evidence/issue-290/diagnostic')/stage.name)
    sealed=parent/candidate
    artifacts={str(p.relative_to(output)):p.read_bytes() for p in output.rglob('*') if p.is_file()}
    write_artifacts(sealed,artifacts)
    seal_fingerprint(sealed,json.dumps({'candidate':candidate,'diagnostic_only':True,'status':result['status'],'source_stage':str(stage)},sort_keys=True).encode())
    verify_manifest(sealed);read_fingerprint_authority(sealed)
    print(json.dumps({'evidence':str(sealed),'stage':str(stage),'result':result},indent=2),flush=True)
    return 0 if result['status']=='passed' else 1


def main():
    def interrupt(signum,_frame):raise SystemExit(128+signum)
    signal.signal(signal.SIGTERM,interrupt);signal.signal(signal.SIGINT,interrupt)
    if len(sys.argv)!=4:raise ValueError('candidate capture-root profile-path required')
    return run(sys.argv[1],Path(sys.argv[2]).resolve(),Path(sys.argv[3]).resolve())


if __name__=='__main__':raise SystemExit(main())
