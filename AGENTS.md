# Workspace runtime

In the managed cloud environment, use the actor's configured Docker daemon.
Preserve `DOCKER_HOST` and the active context when checking `docker info`. The
oracle-worker service uses `unix:///run/user/1002/docker.sock`; discover the
current user's socket through `XDG_RUNTIME_DIR` or `/run/user/$(id -u)`. Failure
at `/var/run/docker.sock` does not establish that this service is down. Do not
clear the actor's configuration to force the root socket.

See [Cloud Docker runtime](docs/development/cloud-docker.md) for discovery,
verification and isolated acceptance projects.
