# Aviation weather diagnostic captures

Research dependencies are isolated from the production API. Pin the verified
2026-10-06 00Z F006 GFS inventory, AWC international SIGMET collection, and
recorded GOES-19 C13 full disk. No continuous ingest or implicit latest fallback.

```sh
PYTHONPATH=tools timeout --kill-after=10s 20m python -m acceptance.aviation_weather_proof.capture gfs /tmp/my-evidence/gfs
PYTHONPATH=tools timeout --kill-after=10s 5m python -m pytest tools/tests/test_aviation_weather_proof_capture.py -q
```

Every normalizer worker must call `load_capture(manifest_path)` before using
`object_path(manifest, captured_object)` or `capture_manifest_path(manifest)`.
These helpers reject departed/changed bytes, manifest edits and escaped paths.
The records retain the exact frozen constructors in the approved plan.

Transport: explicit allowlisted HTTPS, no redirects, custom User-Agent, 30-second
absolute exchange deadline, parent-death worker signal, two concurrent exchanges,
20 attempts per 60 seconds, 32 MiB/object and conservative 5 GiB/day reservations.
All transitive research versions are pinned in `requirements.txt`. No topology
dependency is installed; a later advisory proof must verify and pin one if needed.

Admission state is shared across workers under `/tmp/aviation-proof-admission-UID`.
Acquisition publishes a directory only after all objects succeed; staging is
removed on failure/INT/TERM. A new destination creates a new immutable manifest.
Use a dedicated evidence parent: raw staging is capped at 1 GiB, with 0.5 GiB
free reserve; this capture-only step does not allocate normalized publication.
SIGMET HTTP success does not establish completeness or worldwide no hazards.

Build only with the configured actor Docker endpoint and a CA secret mount:

```sh
timeout --kill-after=10s 15m docker build --secret id=proxy_ca,src="$CODEX_PROXY_CERT" -f tools/acceptance/aviation_weather_proof/Dockerfile -t starlink-290-aviation-research:task1 .
```

PyPI upstream metadata confirms Python 3.11 compatibility for these pins.
ecCodes is Apache-2.0, netCDF4/pyproj/pytest MIT; NumPy includes BSD-3-Clause,
0BSD, MIT, Zlib, CC0-1.0 terms. Latest NumPy/pyproj require Python 3.12;
this environment deliberately pins their Python 3.11-compatible releases.
Source attribution is retained in each capture manifest; international issuer
redistribution and feed completeness remain explicit research limitations.

Supported research native initialization: in each fresh worker call
`acceptance.aviation_weather_proof.native.initialize_native()` **before**
importing scientific modules. Keep one source decoder per process. This loads
pyproj's bundled PROJ 9.5.1 before ecCodes/eckit's bundled PROJ 9.8.1. The pinned
wheels exhibit a native symbol collision when ecCodes loads first: pyproj reports
9.8.1, warns about its database, and the process can abort at teardown. The
bootstrap rejects detectable late initialization; it cannot repair an already
mixed process. Satellite/normalized reference imports do not load ecCodes;
`compare_gfs` imports it only when called. Arbitrary external import order is
outside the supported research contract. Dependencies and the verified image
remain unchanged.

Combined research tests use this explicit bootstrap (under the caller's shared
scientific decoder lock when running alongside other source proofs):

```sh
PYTHONPATH=tools OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 timeout --kill-after=10s 5m python -c 'from acceptance.aviation_weather_proof.native import initialize_native; initialize_native(); import pytest; raise SystemExit(pytest.main(["tools/tests/test_aviation_weather_proof_capture.py", "tools/tests/test_aviation_weather_proof_gfs.py", "tools/tests/test_aviation_weather_proof_satellite.py", "tools/tests/test_acceptance_platform_typing_policy.py", "-q", "-W", "error"]))'
```

GOES C13 normalization represents top-of-atmosphere brightness temperature in K,
with DQF=0, a maximum 75-degree view zenith, no cloud parallax correction, and
bilinear regridding requiring every nonzero source contributor to be valid. It
retains source scan start/end and each region's distinct interval, selecting scan
end for display. `reference.compare_satellite(capture, descriptor_path)` retains
ten independent analytic ellipsoid-navigation/source-value controls. Its local
bilinear-versus-nearest differences describe resampling; its separate half-step
0.005 K bound checks normalized quantization. It does not infer cloud height or
precipitation, or claim global resampling accuracy.

## Native Overview diagnostic

`run.sh <clean-40-hex-SHA> <capture-root> <provisioned-profile.toml>` owns the
private `starlink-290-aviation-proof` Compose project and loopback 15290/18290.
It archives the committed source, regenerates each product and its independent
source controls offline in separate 1 CPU/1 GiB/120 second containers, builds the
production Dockerfiles with a separate 15 minute bound, and drives the existing
Overview scene through the platform-owned native browser. The entire run has a
20 minute wall-clock limit and 10 second termination grace. The shared scientific
lock remains held through exact worker/container/process cleanup.

The test backend alone exposes normalized `/capture` assets in `aviation-proof`
mode. Original captures are mounted read-only in scientific workers and are not
served. The existing frontend dependency tree supplies esbuild and Playwright;
the runner does not invoke npm, npx, or install a browser. An unprovisioned profile
fails and retains platform diagnostics. Use the configured actor Docker daemon.

Browser support is test-only. RGBA8 nearest textures hold signed little-endian
Int16 components and mask bytes; the scalar shader manually interpolates and
requires all four stencil masks valid, including zero-weight neighbors. A
one-pixel RGBA8/depth target crops an independently rounded native viewport pixel,
with a ray intersection against the actual tessellated mesh. Quantity/mask and
palette measurements use that same shader. Independent Python geographic
bracketing checks the retained GPU hit coordinates. Palette checks use a known
linear framebuffer background, no tone mapping or output conversion in the
custom shader, no multisampling, and interior pixels; tolerance is 3/255 RGB.

Wind remains m/s in artifacts; glyphs point FROM and convert by 1.94384449 knots
per m/s, rounded to the nearest five knots. Advisory holes are triangulated before
interior subdivision and Earth projection. Explicit capture replay labels derive
from descriptor epochs; cancellation and half-open expiry controls remain
separate from real-source captures. Satellite brightness temperature is not
cloud height and each regional scan interval remains visible.

Allocations reserve encoded buffers, decoded/geometry and GPU bytes before
candidate creation, including both generations during replacement, packed
textures, geometry and diagnostic color/depth attachments. Conservative geometry
reservations exceed actual typed-buffer sizes; shader/material driver bookkeeping
is not measurable by WebGL. The diagnostic envelope is additional 32 MiB decoded
and 16 MiB GPU to preserve radar's 96/48 MiB budgets and its 0.40/0.17 opacity/hatch.

Success and failure attempts are retained privately beneath
`/srv/starlink-acceptance/evidence/issue-290/diagnostic/<unique-attempt>/<SHA>`.
The runner inventories caller bytes with O_EXCL, seals a fingerprint, and verifies
both after runtime cleanup. It rejects missing provenance, native GPU values or
metrics, failed masks, browser provider requests, missing cleanup or forced
child termination. These are diagnostics; no final product acceptance, WIFS
access, flight-level interpolation, worldwide feed completeness or global
satellite seam coverage is claimed.
