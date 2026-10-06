# Overview map labels

Overview map labels protect the full rendered own-aircraft chevron and glow,
plus an eight CSS-pixel visibility margin. Protection is checked after every
rendered camera frame and again when a label-placement worker responds. It also
covers crowded-label summaries and their open name lists. A label whose old
position becomes unsafe is hidden until a safe placement is available; the
aircraft and underlying markers and paths remain present.

Placement first seeks clear space around the aircraft, route/link/history paths,
POI/GEP symbols, other labels and fixed panels. When those softer constraints
conflict, traffic identities use the least occupied safe callout and nearby POIs
can share a compact disclosure. The own-aircraft exclusion is never relaxed. If
no safe rectangle fits, the visual label is suppressed. POI and satellite names
remain in their accessible map lists; ADS-B identities and details remain
available through marker selection and keyboard contact buttons. An open
disclosure moves clear of the aircraft while preserving its open state and
focus; a list that cannot fit safely is hidden until space opens.

The tracked browser scenario uses a deterministic KADW/GEP/traffic cluster and
monitors every animation frame during camera gestures, telemetry movement,
stale/fresh refresh, fullscreen and enlarged-text transitions. Run the isolated
production-image control on a clean committed worktree with:

```sh
timeout --kill-after=30s 25m tools/acceptance/overview-labels/run.sh
```

It archives the exact tracked HEAD, builds the production Dockerfiles, checks
the real Nginx API path, and runs the label and ADS-B browser suites on Forge.
Browser-intercepted API fixtures establish deterministic geometry; they do not
prove a live ADS-B provider. The runner owns the `starlink-295` Compose project,
private volumes and loopback ports 15295/18295, and removes them after the
checks. Evidence stays under
`.superpowers/sdd/issue-295-label-occlusion/evidence/`.
