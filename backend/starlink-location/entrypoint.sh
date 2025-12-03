#!/bin/sh

# Ensure mounted data directories have correct permissions for appuser
# This runs as root.
# Try to change ownership, but don't fail if it's not permitted (e.g. specific bind mounts)
chown -R appuser:appuser /app/data/missions 2>/dev/null || true
chown -R appuser:appuser /app/data/satellites 2>/dev/null || true
chown -R appuser:appuser /app/data/sat_coverage 2>/dev/null || true
chown -R appuser:appuser /data/routes 2>/dev/null || true
chown -R appuser:appuser /data/sim_routes 2>/dev/null || true
chown -R appuser:appuser /data 2>/dev/null || true

# Ensure they are writable by everyone (simplest fix for bind mount permission issues in dev)
chmod -R 777 /app/data/sat_coverage
chmod -R 777 /data

# Execute the main command as appuser
exec runuser -u appuser -- "$@"