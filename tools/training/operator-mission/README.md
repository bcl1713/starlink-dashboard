
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
