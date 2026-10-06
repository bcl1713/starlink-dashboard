# Workspace instructions

## Git workflow

Start each task in an isolated Git worktree on its own feature branch, based on
`origin/dev`. Keep the primary checkout on `dev` and use `.worktrees/` for local
feature worktrees. Do not make feature changes in the primary checkout.

Push the feature branch and submit a pull request against `dev`. After the PR
merges, remove the task worktree, delete its local and remote feature branches,
and remove remaining task-owned temporary files. Keep worktrees for open PRs so
review changes stay isolated. Stop task-owned runtime resources as soon as their
checks finish; do not wait for PR merge. Preserve `dev`, `main`, shared runtime
configuration, and credentials.

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

## Task resource lifecycle

Record ownership before starting temporary resources: command/session handles,
PID and process group, Compose project, private volumes, and temporary paths.
Use a task-specific Compose project, not a shared development project.

Run tests with a wall-clock limit and forced termination grace period, for
example `timeout --kill-after=10s 10m <test command>`. A tool's output-yield
limit and pytest's `faulthandler_timeout` do not terminate a hung test. Choose a
larger explicit limit for builds or acceptance runs when needed. After a
timeout, stop and verify the old process tree before starting another run.

Use exit and signal cleanup handlers for resource-owning runners. Close browser
contexts and stop their child processes, terminate and reap task-owned workers
and development servers, and remove task-owned Compose containers, networks, and
disposable volumes. Terminate gracefully first; force only verified owned
survivors. Do not use broad `pkill`, `killall`, or Docker prune commands.

Before handing work back, including on failure or cancellation, verify that the
task's processes, listeners, containers, networks, and disposable volumes are
gone. Check host processes through an approved host command if the sandbox's PID
namespace hides them. Preserve acceptance evidence and open-PR worktrees, but do
not keep their runtime resources alive. Leave a temporary service running only
when the user requests it, with its owner, purpose, and stop command reported.
If cleanup is blocked, report the exact remaining resources.
