# Operator display proof

Run a clean committed candidate with the actor's configured Docker endpoint,
existing browser and the cached development plus GFS requirements:

```sh
timeout --kill-after=10s 30m uv run --offline --python 3.11 \
  --with-requirements backend/starlink-location/requirements-dev.txt \
  --with-requirements backend/starlink-location/requirements-gfs.txt \
  python tools/acceptance/operator-display/run.py FULL_SHA /path/to/chrome
```

This reuses the existing weather acceptance owner, provider fixtures and GFS
source transport. The existing `grib_bundle` fixture generates actual small
synthetic GRIB messages, admitted by the normal inventory parser, scientific
child, normalizer, worker, IPC and artifact/API pipeline. Browser tests use the
production Nginx build and inspect native scene objects. They do not mock
settings responses or claim current NOAA availability. A real counterpart write
causes the conflict; a browser connection failure tests unavailable preflight.

The private project is `starlink-operator-display-376`, using loopback ports
56540/56541 and its own volumes. Ownership precedes allocation. The inherited
owner preserves Docker configuration, bounds commands and tears down resources;
the existing Operator relay records and reaps its own process group. A summary
requires empty resource inventories and free ports. Evidence uses the inherited
`test-results/gfs-foundation` parent but writes `operator-display-summary.json`,
never the pinned-source GFS foundation PASS. Capture and source/image identities
remain explicit. The separate training proof checks configured network panels
across actual replay activation, completion and restart.
