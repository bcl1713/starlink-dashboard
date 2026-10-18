# Private Operator training instance

The fixture runs one private nonproduction dashboard with fictional mission
prerequisites. It uses the production journal, mission planner, replay engine,
ETA/PoP adapters and prediction code. It does not control communications hardware
or contact an aircraft.

The guided mission and full operator guide are still being implemented. This
page documents the fixture and its ownership/recovery contract.

## Launch and stop

Use a committed checkout and a new, empty directory. The launcher creates an
explicit training marker, a UUID-derived private Compose project, an immutable
source archive and command/resource ownership records there.

```sh
scripts/operator-training.sh start --root /tmp/operator-learner
scripts/operator-training.sh stop --root /tmp/operator-learner
```

The start command prints the loopback URL, ownership path and stop command.
Normal stop removes containers and the network while retaining the learner's
private data volumes. Start the same root to revisit those records. The launcher
preserves the actor's configured Docker daemon/context; it never selects the
root daemon to work around a connection error.

For the managed environment's isolated Docker network namespace, add `--relay`.
This reuses the acceptance harness's owned loopback relay. The launcher records
its PID/process group and stops that specific process on teardown. See
[Cloud Docker runtime](cloud-docker.md).

Only an empty, marked training root and private volumes are accepted. Shared
projects, external volumes, writable source binds, host networking and a change
of Docker daemon/context are rejected. Live mode is rejected before startup.
Existing unmarked data is preserved rather than adopted or initialized.

## Aircraft progression

Preview and start each leg through **Missions → Simulate leg…**, using multiplier
**1** for this stepped fixture. The normal replay engine owns activation and
flight-phase changes. The launcher advances predefined raw source inputs and the
existing scenario clock; it does not restore a flight phase or seed predictions.

```sh
scripts/operator-training.sh checkpoint --root /tmp/operator-learner --stage leg-one
scripts/operator-training.sh checkpoint --root /tmp/operator-learner --stage leg-one-restriction
scripts/operator-training.sh checkpoint --root /tmp/operator-learner --stage between-legs
# Preview and start the second leg in Missions at the between-legs checkpoint.
scripts/operator-training.sh checkpoint --root /tmp/operator-learner --stage leg-two
scripts/operator-training.sh checkpoint --root /tmp/operator-learner --stage postflight
```

The initial preflight clock is 2026-10-17 16:00 UTC. The first route starts then;
the second starts at 16:45 UTC. Checkpoints move forward only. Back in the guide
must not rewind time or undo journal writes.

The fixture seeds two routes and seven **planned** requirements. Calls,
conferences, customer intervals, transport reports, issue updates, observations,
acknowledgments and completion evidence must come from actual learner actions.
Each private root supplies a stable fixture journal namespace across actual
replay segment IDs. This adaptation exists only in the explicit fixture
entrypoint; normal live and simulation-run isolation remain unchanged.

## Restart and reset

```sh
scripts/operator-training.sh restart --root /tmp/operator-learner
scripts/operator-training.sh reset --root /tmp/operator-learner
```

A backend restart retains persisted input time and journal identity. It stops the
in-memory paced replay. Preview/start the current segment again when needed;
this is not exact-frame replay reconstruction.

Reset stops the old instance and creates a fresh sibling root/project. It prints
the new root and URL and retains the previous root and journal volumes. It does
not erase operational data or silently reinitialize an existing journal. Guide
progress reset is a separate, non-destructive action.

## Temporary ZIP import destination

Run this second dashboard only for the archive import lesson, then stop it:

```sh
scripts/operator-training.sh import-start --root /tmp/operator-learner
scripts/operator-training.sh import-stop --root /tmp/operator-learner
```

It reuses the existing clean archive-destination fixture. Its containers,
network and private data volumes are disposable. Mission export/import continues
to use the existing single ZIP workflow in Missions.

## Automated proof

`--disposable` is reserved for automated checks: stopping that instance removes
its private journal volumes. The exact-source proof runner accepts only an
explicit task-owned disposable root, records browser process ownership separately
from checkpoint commands and always stops the stack on exit or failure.

```sh
scripts/operator-training.sh start --root /tmp/issue-376-training-proof-local --disposable --relay
python tools/training/operator-mission/prove.py /tmp/issue-376-training-proof-local
```

Keep the ownership files, proof summary and synthetic screenshots as acceptance
evidence. A launcher or unit-test pass alone does not establish full training,
visual parity or uncoached human acceptance.
