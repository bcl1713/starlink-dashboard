# Live connectivity troubleshooting

First confirm the effective `mode` and `dish_connected` in
`curl --fail --max-time 10 http://localhost:8000/health`. `dish_connected`
appears only in live mode. A healthy API with false dish connectivity means the
HTTP server is running but telemetry acquisition has not succeeded; it is not a
simulation fallback.

Check the configured dish address and port without publishing your full rendered
environment. Test the dish TCP endpoint from the backend container, then inspect
acquisition logs. Instructions and a bounded socket probe are in
[live setup](../../setup/configuration/live-mode/setup.md).

Verify host routing, VPN policy and firewall access to the dish subnet. A host
mapping or successful ping does not establish gRPC access. Container bridge
routing can differ from host routing. Do not open arbitrary inbound public ports
to solve an outbound dish connection failure.

Failed dish reads yield no new valid telemetry. Treat old values as stale and
use `/health` and dashboard freshness indicators before relying on position,
ETA, or network metrics. Reconnect behavior should be evaluated against actual
successful samples, not merely a running container.
