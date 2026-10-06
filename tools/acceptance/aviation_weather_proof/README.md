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
