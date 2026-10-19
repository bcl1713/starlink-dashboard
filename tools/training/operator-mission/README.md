
Archive acceptance can extend the exact-source browser proof with a separate
private import destination on loopback port 56534:

```sh
timeout --kill-after=10s 35m uv run --offline --python 3.11 \
  --with-requirements backend/starlink-location/requirements-dev.txt \
  python tools/training/operator-mission/prove.py \
  /tmp/issue-376-training-proof-UNIQUE --archive
```

Start that disposable source with the normal launcher first. The proof checks the
four training browser cases, then downloads the original mission ZIP through
Missions and imports unchanged bytes through the destination's Missions UI.
It compares empty and nonempty destination journal sentinels and inspects the
original PDF, complete source revisions and archive checksums. Both stacks are
stopped in the proof's cleanup handler. Telemetry states are reported verbatim;
this slice does not certify the complete narrative, preparation cancellation,
all parity branches, or human PDF review.
