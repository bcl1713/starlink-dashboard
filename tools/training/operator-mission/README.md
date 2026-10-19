# Private Operator candidate

Tested private RC1 runtime source: `c3ff657f2bfc91f2351956088ca5e15dc5efb227`.
Use a nonproduction Linux computer with Git, an updated Python 3.11 or newer,
Docker Engine and the Compose plugin. The launcher builds committed application
source; initial builds need registry access. Preserve the computer's configured
Docker context and `DOCKER_HOST`.

From an existing repository clone, keep the test checkout isolated:

```sh
git fetch origin feat/issue-376-operator-workspace
git worktree add --detach .worktrees/operator-rc-c3ff657f c3ff657f2bfc91f2351956088ca5e15dc5efb227
cd .worktrees/operator-rc-c3ff657f
docker info
export operator_training_root="$(mktemp -d /tmp/operator-training-XXXXXX)"
timeout --kill-after=10s 20m scripts/operator-training.sh start \
  --root "$operator_training_root" --disposable
```

Open the printed `origin`, including `/operator?workspace=1`. Select
**Fictional Meridian 21**, then **Help → Guided mission walkthrough**. The packaged
procedure supplies the native backup warmup, checkpoints, restart and archive
commands using this private root. Managed-cloud sessions whose Docker daemon
cannot expose loopback need the existing `--relay` option; local Docker normally
does not. The source root contains the command/resource ownership and launch logs.

The linked production run at this SHA passes all ten browser cases, including
original ZIP/PDF/checksums, both isolated imports, actual conflicts, source/restart
continuity, storage recovery, a timed-out mission read with explicit retry, and
native backup/changed-epoch recovery using the private one-response receipt-loss
control. See the retained private-rc report. Guide navigation and human
observations remain separate from these automated facts.

For the required uncoached first use, use the application and its packaged Help
without outside verbal coaching:

1. Before reading a procedure, identify what Operator represents and find how to
   schedule a call and create/establish/verify a conference. Record the first point
   of uncertainty instead of having someone point out the control.
2. Conduct the complete T01–T11 synthetic mission. Perform the backup/epoch warmup
   before the first flight, then return to T01 in the restored epoch. Use real
   controls and the guide's explicit evidence checks; keep missing, skipped and
   unavailable outcomes honest.
3. For each lesson record completion, Help retrieval, wrong selections, recovery
   and elapsed time. Record pauses separately. Review the original extracted PDF
   yourself and supply only human observations you actually made.
4. Repeat the mission on mobile portrait/landscape. On a real device, inspect the
   soft keyboard, scrolling, retained focus and recovery while editing. Desktop
   viewport emulation is a separate automated check and does not certify this.
5. Return the exact SHA, device/browser, lesson, expected next action, what you
   actually found, Help used, errors/recovery and approximate elapsed time. Use
   fictional data only. Uncoached use and physical-device accessibility remain
   pending until a real person supplies these observations.

Current verification update: all 323 parity entries are reconciled as an evidence
crosswalk. Original ZIP/PDF/import/backup and guide adapters pass the linked RC1
run. Connected native weather reversal, replay panels and restart pass later
checkpoints; the diagnosed wind restoration issue is fixed by one bounded grid
retry. Original/candidate task comparisons, sixty-second CPU/polling samples and
retained-work backout also pass. The current workspace revision
`9b07dbb48c6036c3c3c217dc46f88583eb682fdd` adds persistent Save/Discard actions;
its dedicated browser and canonical checks are recorded separately from RC1's
complete guide run. No human acceptance is inferred from either checkpoint.

Remaining release gates are final canonical verification and actual uncoached
human desktop/mobile use, including physical keyboard, screen reader and contrast
observations. This private checkpoint is for testing, with no merge/cutover or
human-usability acceptance claimed. The old shell remains the default;
`?workspace=1` selects the candidate. The launcher binds loopback; real-phone access
requires a separately chosen private connection to the nonproduction computer.

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

Archive evidence retains distinct destination records/history/H before and after each import, actual ready-preparation responses and the downloaded response fingerprint/briefing status/ZIP hash. The inspector retains expected and computed member checksums. These raw facts support the guide handoff; a single post-import snapshot or a generic success flag is not that evidence.

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
commands and the managed-cloud relay option. The combined exact-source CLI/browser handoff passes at
`3fa1c2d8ea3a9206f867b8a23d397dbaf13b1724`, including both imports, selected-file
rejection, three-size guide revalidation and explicit missing human observations.
The same run verifies raw parked-draft, offline/reconnect and native storage-quota
recovery evidence with actual saved revisions. The complete course and human
usability gates remain open; see the retained course-archive report.

Normal re-import can replace a mission under the same ID. The private checker
records actual destination plan-file hashes and device/inode/modification facts
before and after the UI import. A new installed generation with the same content
establishes replacement; an unchanged check does not. The complete installed
mission must still match the original legs/transports, and every destination
Operator record, immutable revision and H must remain unchanged. Read-time leg
stub timestamps are excluded from catalog consistency checks; saved mission
metadata and identities remain checked.

For a targeted client-recovery check on a fresh owned disposable proof root,
`prove.py ROOT --clients-only` runs the three-size parked-draft/offline/storage and
actual two-browser conflict cases, then tears down the source. The proof summary
labels this narrower scope explicitly; it does not certify the full course or
archive. The normal `--archive` proof still includes every linked phase.
