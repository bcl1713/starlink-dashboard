# Performance tuning

Start by measuring `docker stats --no-stream`, backend logs, Prometheus query
latency, and the browser's network requests. Avoid changing several clocks at
once: backend updates, Prometheus scraping, and frontend history polling are
separate settings.

- Backend updates default to 1 second. Set
  `STARLINK_UPDATE_INTERVAL_SECONDS=2.0` in `.env` and recreate the backend to
  reduce update frequency when appropriate for your use case.
- Prometheus has global and job-specific 1-second scrape intervals and a
  1-second job timeout in `monitoring/prometheus/prometheus.yml`. If changing
  scrape frequency, update the job-specific setting as well, keep the timeout
  valid, and restart Prometheus. Coarser samples reduce history detail and can
  change alert behavior.
- `VITE_OVERVIEW_HISTORY_POLL_SECONDS=5` is the supported frontend history
  rollback cadence; rebuild Mission Planner after changing it. Narrow the
  selected Overview history window to reduce query work.
- Size storage using actual measurements; see
  [retention](storage-configuration.md).

The GFS worker already has a one-CPU, 1 GiB limit. Do not impose tiny backend
memory limits copied from old examples: exports, scientific libraries, and
mission size affect requirements. Preserve runtime data while diagnosing usage;
Docker prune and volume removal are not performance fixes.
