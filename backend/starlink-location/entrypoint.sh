#!/bin/sh

# Ensure mounted data directories exist and have writable top-level permissions.
# Do not recursively chown/chmod the volumes on every container start: route/POI
# caches can grow large, and walking them makes startup look hung.
for dir in \
  /app/data/missions \
  /app/data/satellites \
  /app/data/sat_coverage \
  /app/data/settings \
  /app/data/orbital \
  /data/routes \
  /data/sim_routes \
  /data
 do
  mkdir -p "$dir" 2>/dev/null || true
  chown appuser:appuser "$dir" 2>/dev/null || true
  chmod 775 "$dir" 2>/dev/null || true
 done

# Operator history is private and independent of the shared 775 directories.
# Touch only the mount root; retained database/backup ownership stays intact.
operator_dir="${OPERATOR_ROOT:-/app/data/operator}"
mkdir -p "$operator_dir"
chown appuser:appuser "$operator_dir"
chmod 700 "$operator_dir"

# Execute the main command as appuser
exec runuser -u appuser -- "$@"
