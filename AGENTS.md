# Workspace instructions

## Git workflow

Start each task in an isolated Git worktree on its own feature branch, based on
`origin/dev`. Keep the primary checkout on `dev` and use `.worktrees/` for local
feature worktrees. Do not make feature changes in the primary checkout.

Push the feature branch and submit a pull request against `dev`. After the PR
merges, remove the task worktree, delete its local and remote feature branches,
and remove task-owned acceptance projects and temporary files. Keep worktrees
for open PRs so review changes stay isolated. Preserve `dev`, `main`, shared
runtime configuration, and credentials.

See [Development workflow](docs/development/workflow.md) for commands.

## Workspace runtime

In the managed cloud environment, use the actor's configured Docker daemon.
Preserve `DOCKER_HOST` and the active context when checking `docker info`. The
oracle-worker service uses `unix:///run/user/1002/docker.sock`; discover the
current user's socket through `XDG_RUNTIME_DIR` or `/run/user/$(id -u)`. Failure
at `/var/run/docker.sock` does not establish that this service is down. Do not
clear the actor's configuration to force the root socket.

See [Cloud Docker runtime](docs/development/cloud-docker.md) for discovery,
verification and isolated acceptance projects.
