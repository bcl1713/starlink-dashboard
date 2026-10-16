# Live mode configuration

Use [live setup](live-mode/setup.md) for environment settings, container-to-dish
routing, and bounded connectivity checks. See
[live troubleshooting](../../troubleshooting/connectivity/live-mode.md) when the
HTTP API is healthy but acquisition fails.

Live mode remains live during dish outages; it does not generate simulation
fallback telemetry. Check `dish_connected` and freshness separately from HTTP
health. The local bridge profile and Portainer deployment are distinct; use the
[deployment runbook](../../deployment/portainer-ghcr.md) for managed stacks.
