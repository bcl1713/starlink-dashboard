# Visualization implementation

The native Overview renders operational position, POIs and route context.
Mission leg preview renders the editable configuration before save; export
preparation captures a stable input snapshot for customer artifacts. These
surfaces have different purposes and should not share mutable render inputs.

See [Overview](../../features/overview.md),
[mission planning](../../features/mission-planning.md), and
[export preparation](../planning/outputs.md). Export implementation lives in
[`app/mission/exporter`](../../../backend/starlink-location/app/mission/exporter).
