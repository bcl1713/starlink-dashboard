# Prior production-image diagnostic evidence

This review bundle preserves the production-image/Nginx diagnostic and nominal
one-hour soak recorded for
[PR #432](https://github.com/bcl1713/starlink-dashboard/pull/432) on 2026-10-28.
Candidate and harness were both `bba55c5209eafc5f4f56a2dd2a99fe7f539de2ef`.
These are historical measurements of that revision, not evidence for later
source changes or final acceptance.

The [original report](report.txt) is copied byte for byte, including its
then-current contract and approval status. Its reference to `evidence/health/`
describes separately retained platform evidence; that directory is deliberately
absent here. Health alone does not establish product acceptance. Sealed platform
authority remains outside tracked repository content as required by the
[acceptance platform procedure](../../../operations/acceptance-platform.md#evidence-and-publication).

## Recorded result and limits

The soak runner returned `measured`, with 721 measured resource samples after a
120-second warmup. Its raw first-to-last span is **3599.9999547059997 seconds**
(rounded to `3599.999954706000` in the original report), and
**`sustained_60_minutes` is `false`**. The planned duration was 3,600 seconds;
the strict duration gate was not passed.

The fixture used the production backend/frontend Dockerfiles from the exact
source archive, production Nginx, actual Prometheus with 1 Hz scraping, one
1920×1080 Overview viewer plus Operator, and a 30-minute history window. The
backend ran `performance.fixture:app` with synthetic simulation data and
read-only acceptance fixture mounts, as shown in the copied Compose records.
Each service had a 2 CPU/2 GiB limit. This is a synthetic workload, not a live
deployment measurement.

Both diagnostic browsers were headless Chrome 153.0.8010.12 using SwiftShader,
DPR 1 and DOM fullscreen, with `physical_fullscreen: false`. The frame p95 of
116.6 ms is a software-rendering observation. This bundle does not establish
hardware-rendering performance, physical fullscreen or final platform
acceptance.

The soak recorded zero unexpected request failures, zero client cancellations,
and an empty browser failure list. All three lifecycle operations and journal
writes returned successful receipts. The cardinality file contains 46 scrape
observations plus one terminal status row: observed current identities followed
1 → 0 → 1, with no mission gauge children during observed inactivity and POI ETA
count 2. These point observations do not prove every intervening scrape.

There is no matched baseline for these production-image measurements. Memory
growth remains visible: backend anonymous memory was 315.63 → 329.28 MB, peaking
at 899.49 MB around reactivation; browser PSS was 1168.77 → 1479.21 MB, peaking
at 1542.16 MB with a fitted slope of 3.828 MB/min. The evidence does not
establish flat browser memory or a leak diagnosis. See the full
[resource and endpoint summary](production-soak/summary.json).

## Review entry points

| Evidence                                                                                                                                                                       | Contents                                                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| [Soak run](production-soak/run.json)                                                                                                                                           | Candidate/harness SHA, image IDs and revision labels, source/config/fixture hashes, hardware, workload, browser identity and runner cleanup |
| [Soak summary](production-soak/summary.json)                                                                                                                                   | Exact span, strict duration flag, resource slopes and request/frame latency distributions                                                   |
| [Soak operations](production-soak/operations.jsonl)                                                                                                                            | Synthetic leg switch, deactivation, reactivation and three journal receipts                                                                 |
| [Request outcomes](production-soak/request-outcomes.json), [failures](production-soak/failures.json), [polling](production-soak/polling.json)                                  | Recorded request outcomes, empty browser failure list and Overview polling observations                                                     |
| [Soak Compose](production-soak/compose.json), [package inventory](production-soak/backend-packages.json)                                                                       | Service images, limits, fixture entry point/mounts and installed backend dependencies                                                       |
| [Short probe run](production-probe-r2/run.json), [summary](production-probe-r2/summary.json), [Compose](production-probe-r2/compose.json)                                      | Successful short diagnostic before the soak; distinct image IDs with the same revision/config fingerprints                                  |
| [Raw samples archive](raw-samples.tar.gz)                                                                                                                                      | Unmodified soak/probe resource and browser-process JSONL, plus all mission-cardinality JSONL rows                                           |
| [Final cleanup](final-cleanup.json), [soak browser cleanup](production-soak/browser-host-cleanup.json), [probe browser cleanup](production-probe-r2/browser-host-cleanup.json) | Historical empty project resource/process listings, closed listeners and browser process-group cleanup receipts                             |
| [Manifest](manifest.json), [bundle checksums](SHA256SUMS), [raw member checksums](RAW-SHA256SUMS)                                                                              | Artifact byte sizes/hashes, original source hashes, archive format and documented redactions                                                |

Source archive SHA-256:
`a6424604de63ad3896d6c28e60e42430aa805656cee6bc3dc5f124a08c16b562`. The archived
source itself and container image layers are not included. Soak image IDs are:

- Backend:
  `sha256:f4cbf42fed80373c2ec39762ad2a427347794dcf818dff0370886700482e3687`
- Frontend:
  `sha256:4fe7bf67cc4be2183b32bab70a0c5b7710b583c239003d4556961d0a12573a98`
- Prometheus:
  `sha256:63805ebb8d2b3920190daf1cb14a60871b16fd38bed42b857a3182bc621f4996`

## Integrity, privacy and reading raw records

The retained source directory is `2026-10-28-issue393-acceptance`; its originals
were not changed. Allowlisted text artifacts were inspected before copying.
Synthetic fixture identities, task project names/PIDs and meaningful machine
descriptions are retained. The only transformed artifacts are the final cleanup
receipt and the two Compose files: host path prefixes become
`<candidate-worktree>` or `<diagnostic-evidence>`, with all other bytes
unchanged. The manifest records both original and copied hashes. The
[original checksum list](source-SHA256SUMS) is unchanged and refers to original
bytes, so it is not the verification list for these redacted copies.

The raw archive contains five byte-exact JSONL files, 4,626,838 bytes before
compression and 673,633 bytes compressed. It uses sorted USTAR members with zero
UID/GID/mtime and mode 0644, then gzip level 9 with an empty filename and zero
mtime. Its SHA-256 is
`bb5db43b4cccdc0aeaeab060868963f6921a01791beb90fcf26e17d4c358a118`. Large
service logs, screenshots, seeded history, ownership dumps and sealed platform
health artifacts are omitted; this is an allowlisted diagnostic bundle.

From this directory, verify the bundle and inspect its file list:

```sh
timeout --kill-after=10s 1m sha256sum --check SHA256SUMS
timeout --kill-after=10s 1m tar --list --gzip --file raw-samples.tar.gz
```

To inspect the raw JSONL with local tools, extract to a disposable directory and
verify every member against the raw checksum list. This command removes its
temporary extraction on exit:

```sh
(
  set -eu
  diagnostic_raw=$(mktemp -d)
  trap 'rm -rf -- "$diagnostic_raw"' EXIT HUP INT TERM
  timeout --kill-after=10s 1m tar --extract --gzip \
    --file raw-samples.tar.gz --directory "$diagnostic_raw"
  cp RAW-SHA256SUMS "$diagnostic_raw/RAW-SHA256SUMS"
  (cd "$diagnostic_raw" && timeout --kill-after=10s 1m \
    sha256sum --check RAW-SHA256SUMS)
  # Inspect $diagnostic_raw/production-soak/samples.jsonl, etc. here.
)
```

Packaging launched no services or browser processes. The cleanup receipts
describe the original diagnostic resources at their recorded check time; they
are not a new acceptance run.
