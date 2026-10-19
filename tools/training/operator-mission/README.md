
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
