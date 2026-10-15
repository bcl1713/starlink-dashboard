# Cloud Docker runtime

The managed workspace has an actor-owned rootless Docker service. Use the
configured endpoint before checking the host's root-owned socket. In the
oracle-worker session verified on 2026-10-02, `DOCKER_HOST` and the `rootless`
context both select `unix:///run/user/1002/docker.sock`. The daemon reports
Docker 29.8.1, overlayfs and rootless security options. These are observed
session values; discover them again rather than assuming the UID or version.

## Discover and verify

```sh
printf '%s\n' "${DOCKER_HOST:-<not set>}"
docker context ls
docker info --format '{{.ServerVersion}} {{.Driver}}'
docker ps
```

If configuration is absent, check the current user's runtime directory:

```sh
ls -l "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/docker.sock"
docker -H "unix://${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/docker.sock" info
```

When listed, the context is another explicit path:

```sh
docker --context rootless info
```

Do not unset `DOCKER_HOST` or the configured context merely to force
`/var/run/docker.sock`. That root socket can deny the workspace actor while its
own daemon is healthy. Rootless operation does not require sudo or restarting
the host daemon. A generic plugin example that assumes a root-owned daemon is
not evidence that the actor's configured service is unavailable.

## Acceptance projects

Use a task-specific Compose project, named volumes and loopback ports so browser
smoke checks have a reproducible local environment. Record the socket/context,
candidate SHA, image build inputs and actual API responses with the evidence.
Use the repository's production Nginx/backend/Prometheus configuration for
real-path checks and identify browser-intercepted fixtures separately.

Build and run through the session's configured proxy and CA trust where needed.
Keep TLS verification enabled. The cloud-environment runtime skill describes
proxy/CA build secrets; preserve registry credentials and avoid copying session
credentials into images or committed files.

## Task teardown verification

Stop task-owned runtime resources after their checks finish, including failures
and cancellations, before handing work back. Keep open-PR worktrees and
acceptance evidence without keeping test environments running.

Use the recorded task project, its original configuration, and required
environment inputs to tear down disposable acceptance resources:

```sh
docker compose -p your-task-project -f your-task-compose.yml \
  down --volumes --remove-orphans
docker ps -aq --filter label=com.docker.compose.project=your-task-project
docker network ls -q --filter label=com.docker.compose.project=your-task-project
docker volume ls -q --filter label=com.docker.compose.project=your-task-project
```

Each filtered listing must be empty after teardown. Use `--volumes` only for
disposable task-owned data; preserve shared and deliberately retained volumes.
Check the task's recorded worker PIDs, process groups, and listeners separately.
A sandbox's PID namespace may hide host processes, and socket access may require
an approved host command. An empty sandbox process listing is not evidence that
host workers have stopped.

Send `TERM` to verified task-owned processes first, wait briefly, then send
`KILL` only to verified survivors and reap child processes where possible.
Exit/signal cleanup handlers cannot handle `SIGKILL`; verify resources after
forced termination. Do not use broad `pkill`, `killall`, or Docker prune
commands. Preserve the Docker daemon, shared application services, runtime
configuration, and credentials. Report any resources that could not be cleaned
up.
