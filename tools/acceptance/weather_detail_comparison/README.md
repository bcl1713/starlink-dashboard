# Weather source comparison

Offline research for issue 288; this does not implement production refinement.
Raw inputs remain server-side. Browser assets are hashed 512-square radar and
absence PNG pairs, with immutable source/frame identities. Coverage alpha is 255
for absent/unknown observations and 0 for valid observations, including covered
zero rain. Raw rain-rate palette thresholds are recorded in capture metadata;
they do not imply equivalence to RainViewer colors.

Create an isolated Python 3.11 environment using `requirements.txt`, plus
`pytest-asyncio` for existing acceptance tests. Use an ignored task-owned output
directory, preserve proxy/CA settings and use explicit wall-clock limits.

```bash
PYTHONPATH=tools timeout --kill-after=10s 5m python -m \
  acceptance.weather_detail_comparison.capture /absolute/capture-directory
```

Build the research Dockerfile from the repository root with the configured
Docker daemon and a combined CA build secret named `proxy_ca`. Generate in one
named task container with `--rm --cpus=1 --memory=2g --network=none`, mounting
captures at `/capture`. The image entrypoint generates only a baseline and three
eight-tile regional levels; it does not run an ingest service.

```bash
PYTHONPATH=tools timeout --kill-after=10s 15m python -m \
  acceptance.weather_detail_comparison.capture_detail \
  /absolute/capture-directory --finish
```

Detail capture checkpoints after each complete pair and respects 30 attempts per
rolling minute, two active requests and 45-second request deadlines. It uses
provider frames within five minutes of each raw observation. Coverage capture
time is recorded separately; RainViewer's current mask has no historical
observation timestamp. Clear or unmatched data cannot establish better detail.

Use clean committed HEAD for native replay:

```bash
WEATHER_COMPARISON_PYTHON=/absolute/research-venv/bin/python \
WEATHER_ACCEPTANCE_CAPTURE_DIR=/absolute/capture-directory \
timeout --kill-after=15s 30m bash \
  tools/acceptance/weather_detail_comparison/run.sh "$(git rev-parse HEAD)"
```

The runner builds the production Dockerfiles, serves Overview through Nginx and
uses project `starlink-288-weather-comparison`, loopback ports 15288/18288 and
private volumes. Only the test backend launcher exposes read-only capture
assets. The browser probe patches the existing native weather material for
research, restores it after each case and closes temporary bitmaps/textures. GPU
weather storage is 32 MiB baseline plus 16 MiB detail; owned decoded storage
includes baseline canvases, restoration copies, detail canvases and one active
bitmap. Screenshots label offline replay; fixture status is not source
freshness.

Retain candidate SHA, image IDs, capture hashes, download events, generation
metrics, browser requests, screenshots and cleanup proof. Raw process peak RSS
is a shared-process high-water mark, not independent per-source RSS. The browser
measurements characterize saved-data replay, not production request scheduling.
Synthetic fixture tests demonstrate alignment and masking, not provider detail.

The owner wrapper reaps its child group on timeout/signals. Compose cleanup
removes only this project's containers, networks and disposable volumes, then
verifies both ports. A cleanup failure fails the run. Before handoff, verify
recorded host PIDs as well; preserve evidence but stop every runtime resource.
