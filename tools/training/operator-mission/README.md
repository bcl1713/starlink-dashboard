# Private Operator candidate

Use a nonproduction Linux computer with Git, Python 3, Docker Engine and the
Docker Compose plugin. The launcher builds the committed application source;
initial builds need access to the image and dependency registries. Keep the
computer's configured Docker context and `DOCKER_HOST` unchanged.

From the implementation checkout at the candidate SHA reported on PR #383:

```sh
git rev-parse HEAD
docker info
export operator_training_root="$(mktemp -d /tmp/operator-training-XXXXXX)"
timeout --kill-after=10s 20m scripts/operator-training.sh start \
  --root "$operator_training_root" --disposable
```

Open the printed `origin`, including `/operator?workspace=1`. In Operator, select
**Fictional Meridian 21**, open **Help**, then **Guided mission walkthrough**.
Use the normal Operator/Missions controls for each lesson; **Read this procedure**
opens the packaged offline guide. The root contains the command/resource ownership
and launch logs. Keep its path for the checkpoint, restart and archive commands.
Managed-cloud sessions whose daemon cannot expose its loopback port need the
launcher's existing `--relay` option. A local Docker installation normally does
not need it.

This is an implementation candidate, not a fully accepted release. T01–T11
remain honest about missing machine evidence and manual observations. At this
checkpoint, draft-switch/offline/conflict/backup and the remaining T11 recovery
adapters are unfinished; full parity crosswalk, final performance/accessibility,
mobile-keyboard checks and an actual uncoached person's walkthrough remain open.
The original shell is still the default; `?workspace=1` selects the candidate.
Do not interpret a green lesson or a passing browser test as human usability
acceptance. For the first-use check, note where finding the next action, deciding
what a status means, or recovering a mistake needed outside help. Record screen
size and the lesson; never include operational data.

Stop the private exercise as soon as its checks finish:

```sh
timeout --kill-after=10s 5m scripts/operator-training.sh stop \
  --root "$operator_training_root"
```

With `--disposable`, stopping removes the exercise's private containers, network
and data volumes. Downloaded files and logs under the root remain available for
review. No production service or shared development project is used.

Archive acceptance can extend the exact-source browser proof with a separate
private import destination on loopback port 56534:

```sh
timeout --kill-after=10s 35m uv run --offline --python 3.11 \
  --with-requirements backend/starlink-location/requirements-dev.txt \
  python tools/training/operator-mission/prove.py \
  /tmp/issue-376-training-proof-UNIQUE --archive
```

Start that disposable source with the normal launcher first. The proof checks the
four training browser cases, the three-size call lifecycle and guided
transport/issue/capability history, then downloads the original mission ZIP through
Missions and imports unchanged bytes through the destination's Missions UI.
It compares empty and nonempty destination journal sentinels and inspects the
original PDF, complete source revisions and archive checksums. Both stacks are
stopped in the proof's cleanup handler. The archive exercise explicitly invokes
`scripts/operator-training.sh archive-inputs --root MARKED_PRIVATE_ROOT`.
This reuses #370's existing synthetic operational-format observations and raw
reader with the real detector/capture services. It does not admit replay samples
as live data, overwrite replay flight phase, or seed learner journal records.
Its independent synthetic provenance is included in the mission metadata.
The normal PDF coordinator is owned by the private application's lifespan;
aircraft/provider background discovery stays disabled. Telemetry states are reported verbatim;
The archive browser also cancels a real known preparation before downloading,
then retries and checks immutable destination records/history and H separately
from changing read-time freshness. This slice does not certify the complete
narrative, all parity branches, or human PDF review.

Each browser phase retains successful and failed traces under its own
`ROOT/browser/{training,records,decisions,archive}` directory, so a later phase
does not erase an earlier trace. Retain these synthetic artifacts with the
source/image identities; this does not keep any runtime resource alive.

Archive evidence retains distinct destination records/history/H before and after each import, actual ready-preparation responses and the downloaded response fingerprint/briefing status/ZIP hash. The inspector retains expected and computed member checksums. These raw facts support the pending guide handoff; a single post-import snapshot or a generic success flag is not that evidence.

The private archive handoff uses `archive_evidence.py baseline|check --root ROOT
--label empty|nonempty --browser-origin ORIGIN`. Run it in the existing backend
Python requirements environment. Baseline runs before each normal Missions UI
import; check runs afterward. The empty destination starts with no missions or
journal rows. Before the nonempty exercise, create a fictional note through
Operator, take another baseline, and import the unchanged ZIP again.

Check reads the existing ready preparation SQLite database in read-only mode,
hashes its existing artifact and copies those original bytes for inspection; it
starts no worker and performs no export or journal command. An optional `--zip`
checks the original local browser download instead. Both modes require a matching
ready artifact digest. The existing inspector verifies the PDF, source history
at archive H, telemetry and checksums. Distinct destination before/after health,
records, immutable history and H are retained. Four-minute read/command bounds,
per-request limits and separate per-invocation ownership ledgers apply.

Select the two generated report files and original download in the source T10
guide. It computes the browser file digest and revalidates actual backend source
history before labeling imported tooling evidence. Wrong files and foreign
origin/store/epoch reports remain unavailable. PDF review and a client-visible
failure are explicit human observations; cancellation/ready state cannot prove
that a browser experienced a network failure. Stop the child with `import-stop`
after checking. See the canonical packaged guide's archive procedure for exact
commands and the managed-cloud relay option. This handoff still requires its
new exact-source CLI/browser gate before acceptance is claimed.

Normal re-import can replace a mission under the same ID. The private checker
records actual destination plan-file hashes and device/inode/modification facts
before and after the UI import. A new installed generation with the same content
establishes replacement; an unchanged check does not. The complete installed
mission must still match the original legs/transports, and every destination
Operator record, immutable revision and H must remain unchanged. Read-time leg
stub timestamps are excluded from catalog consistency checks; saved mission
metadata and identities remain checked.
