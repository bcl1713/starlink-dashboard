"""One-shot operational probe; do not rerun without separate authorization."""
import datetime
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time

HERE = Path(__file__).resolve().parent
PROJECT = 'p391-net-20261023-1149'
IMAGE = 'sha256:892bb2152464f0c5d8972593a5f5afaf8054552580b699d95f8ff4af08c2d33d'
PORTS = (43891, 43892)
started = time.monotonic()
deadline = started + 50
records = HERE / 'commands.jsonl'

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def run(name, argv, limit=4):
    before = now()
    allowance = min(limit, deadline - time.monotonic())
    if allowance <= 0:
        raise TimeoutError('overall probe deadline')
    p = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    owner = {'name': name, 'argv': argv, 'pid': p.pid, 'pgid': p.pid, 'start': before}
    with (HERE / 'process-ownership.jsonl').open('a') as f:
        f.write(json.dumps(owner) + '\n')
    try:
        out, err = p.communicate(timeout=allowance)
        timed_out = False
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(p.pid, signal.SIGTERM)
        try:
            out, err = p.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            out, err = p.communicate()
    (HERE / (name + '.stdout')).write_bytes(out)
    (HERE / (name + '.stderr')).write_bytes(err)
    with records.open('a') as f:
        f.write(json.dumps({**owner, 'end': now(), 'exit': p.returncode, 'timeout': timed_out}) + '\n')
    if timed_out:
        raise TimeoutError(name)
    return p.returncode, out.decode()

def interrupted(signum, frame):
    raise InterruptedError(signum)

signal.signal(signal.SIGTERM, interrupted)
signal.signal(signal.SIGINT, interrupted)
owner = {'project': PROJECT, 'runner_pid': os.getpid(), 'runner_pgid': os.getpgrp(),
         'ports': PORTS, 'temporary_files': [str(HERE / 'case1.json'), str(HERE / 'case2.json')],
         'volumes': [], 'start': now(), 'budget_seconds': 60,
         'per_case_seconds': 15, 'image': IMAGE,
         'environment': {k: os.environ.get(k) for k in ['DOCKER_HOST', 'DOCKER_CONTEXT', 'XDG_RUNTIME_DIR', 'COMPOSE_FILE', 'COMPOSE_PROJECT_NAME', 'COMPOSE_PROFILES']}}
(HERE / 'ownership.json').write_text(json.dumps(owner, indent=2) + '\n')
configs = []
for index, (internal, port) in enumerate(zip((True, False), PORTS), 1):
    config = {'services': {'http': {'image': IMAGE, 'pull_policy': 'never',
              'entrypoint': ['nginx'], 'command': ['-g', 'daemon off;'],
              'ports': [{'target': 80, 'published': str(port), 'host_ip': '127.0.0.1', 'protocol': 'tcp'}],
              'labels': {'probe.owner': PROJECT}}},
              'networks': {'default': {'internal': internal, 'labels': {'probe.owner': PROJECT}}}}
    path = HERE / f'case{index}.json'
    path.write_text(json.dumps(config, indent=2) + '\n')
    configs.append(path)

def dc(path):
    return ['docker', 'compose', '-p', PROJECT, '-f', str(path)]

try:
    for port in PORTS:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', port))
    run('daemon', ['docker', 'info', '--format', '{{.ID}} {{.Name}} {{.ServerVersion}} {{.Driver}} {{json .SecurityOptions}}'])
    run('compose-version', ['docker', 'compose', 'version'])
    run('context', ['docker', 'context', 'show'])
    run('images-before', ['docker', 'image', 'ls', '--no-trunc', '--format', '{{.Repository}}:{{.Tag}} {{.ID}}'])
    run('host-processes-before', ['ps', '-eo', 'pid,ppid,pgid,comm'])
    run('listeners-before', ['ss', '-H', '-ltnp', 'sport = :43891 or sport = :43892'])
    for index, path in enumerate(configs, 1):
        case_deadline = time.monotonic() + 15
        deadline = min(started + 50, case_deadline)
        prefix = f'case{index}'
        run(prefix + '-config', dc(path) + ['config', '--format', 'json'])
        rc, _ = run(prefix + '-up', dc(path) + ['up', '-d', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '3'], 6)
        if rc:
            raise RuntimeError(prefix + ' up failed; no retry')
        time.sleep(0.5)
        rc, cid = run(prefix + '-cid', dc(path) + ['ps', '-q', 'http'])
        cid = cid.strip()
        run(prefix + '-inspect', ['docker', 'inspect', '--format', '{"Id":{{json .Id}},"HostConfig.PortBindings":{{json .HostConfig.PortBindings}},"Config.ExposedPorts":{{json .Config.ExposedPorts}},"NetworkSettings.Ports":{{json .NetworkSettings.Ports}},"Networks":{{json .NetworkSettings.Networks}},"State":{{json .State}}}', cid])
        run(prefix + '-network', ['docker', 'network', 'inspect', PROJECT + '_default'])
        run(prefix + '-ps', dc(path) + ['ps', '--all', '--format', 'json'])
        run(prefix + '-port', ['docker', 'port', cid])
        run(prefix + '-top', ['docker', 'top', cid, '-eo', 'pid,ppid,pgid,comm'])
        run(prefix + '-listeners', ['ss', '-H', '-ltnp', 'sport = :43891 or sport = :43892'])
        run(prefix + '-http', ['curl', '--noproxy', '*', '--retry', '0', '--connect-timeout', '1', '--max-time', '2', '--fail', '--show-error', '--verbose', f'http://127.0.0.1:{PORTS[index-1]}/'], 3)
        run(prefix + '-logs', dc(path) + ['logs', '--no-color', '--timestamps'])
        deadline = started + 50
        run(prefix + '-down', dc(path) + ['down', '--volumes', '--remove-orphans', '--timeout', '1'], 5)
finally:
    deadline = started + 60
    try:
        run('final-down', dc(configs[-1]) + ['down', '--volumes', '--remove-orphans', '--timeout', '1'], 5)
    finally:
        for path in configs:
            path.unlink(missing_ok=True)
        (HERE / 'timing.json').write_text(json.dumps({'start': owner['start'], 'end': now(), 'elapsed_seconds': time.monotonic()-started}, indent=2)+'\n')
