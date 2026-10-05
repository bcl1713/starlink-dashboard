# Overview history evidence provenance

Supporting details for the
[qualification report](2026-10-04-overview-history-efficiency-follow-up.md).

The application tree is `ad4f088db9c89dd0748ffbb1f598edfa5241585b`; the complete
frontend tree is `519f9cc02e183e05c3df28d56773546330941302`. Repeat builds have
different OCI attestation-index IDs, retained verbatim in `images.txt` and the
phase metadata. Runtime config digests in the build logs remain identical:
backend `06fda224dc75753f35d3cfbe9d264dc41bd76249c12c27a5d95432e6a0658e5d`,
frontend poll-5
`d594be85518ec53a960f764667670781d16e3d05ad695c6f87e886e0c0235486`, and frontend
poll-1 `da114077e74595b910cc79336d94dd1a35aefac22d4fc67c311656f0311997d6`.

First cold HTTP-reader observations are single backend-reader timings and
exclude JSON, Nginx and browser: 152.646 ms for incremental-5s, 172.813 ms for
one-viewer incremental-1s, 132.764 ms for the two-viewer full baseline and
149.604 ms for two-viewer incremental-1s. Cold replay distributions, profiles
and full-window points are recorded separately; these are not cold browser
latency quantiles. Actual one-second starts include response and timer delay, so
neither source acquisition freshness nor strict one-Hz starts are promised.

Raw evidence is retained at
`/tmp/starlink-224-followup/.superpowers/sdd/2026-10-04-overview-history-efficiency-follow-up/evidence/`.
Qualified directories are:

- `ae8397bf692a6ad0aad839ce3eb0d0745079f26f/full-5-1`
- `ae8397bf692a6ad0aad839ce3eb0d0745079f26f/incremental-5-1`
- `ae8397bf692a6ad0aad839ce3eb0d0745079f26f/incremental-1-1`
- `a3ac77357bfd599eeb413b9ecb6d7a4e73d48346/full-5-2-retry`
- `a3ac77357bfd599eeb413b9ecb6d7a4e73d48346/incremental-1-2`

The
[machine-readable evidence index](2026-10-04-overview-history-efficiency-evidence.json)
contains exact phase image IDs, summaries, gates and manifest digests. Each raw
directory contains candidate SHA, build/Compose/runtime receipts, images, seed,
append-only backend queries/reads, browser request/resource JSONL, screenshots,
recording/profile, observed metadata, derived summary/budgets and SHA-256
manifest. The one-viewer later cleanup audit SHA-256 is
`96fa9131cc62e0000dac39f481f3e5c3dcedb8bc5248e6b701bf3081bb74ce75`.
Failed/interrupted runs and their original logs remain available. Measurement
and summary helper scripts are retained with the evidence archive. To reproduce,
freeze a clean tracked candidate and run the task-owned runner with
`--phase full --cadence 5 --viewers N --warmup 300 --duration 600`, then
`--phase incremental --cadence 1 --viewers N --warmup 300 --duration 3600` for
N=1 and N=2, using the same pinned native profile. The incremental-5s comparison
uses one viewer and 600 measured seconds. Full commands/environment appear in
the retained executor scripts. No production stack was deployed and issues
211/213 remain open.
