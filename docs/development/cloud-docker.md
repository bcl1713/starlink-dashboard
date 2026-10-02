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
