#!/bin/sh

# Ensure mounted data directories exist and have writable top-level permissions.
# Do not recursively chown/chmod the volumes on every container start: route/POI
# caches can grow large, and walking them makes startup look hung.
for dir in \
  /app/data/missions \
  /app/data/satellites \
  /app/data/sat_coverage \
  /data/routes \
  /data/sim_routes \
  /data
 do
  mkdir -p "$dir" 2>/dev/null || true
  chown appuser:appuser "$dir" 2>/dev/null || true
  chmod 775 "$dir" 2>/dev/null || true
 done

# Execute the main command as appuser
exec runuser -u appuser -- "$@"