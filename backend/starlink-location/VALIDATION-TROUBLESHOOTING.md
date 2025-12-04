# Validation Troubleshooting Guide

This document provides troubleshooting steps for common issues encountered
during validation of the Starlink Location Backend.

## Troubleshooting

### Service won't start

1. Check logs: `docker compose logs starlink-location`
2. Verify port 8000 is available
3. Rebuild image: `docker compose build --no-cache starlink-location`

### Metrics endpoint returns empty

1. Wait 5-10 seconds for simulator to initialize
2. Check background task:
   `docker compose logs -f starlink-location | rg "Background"`

### Prometheus shows "DOWN" status

1. Check if starlink-location is healthy: `docker compose ps`
2. Verify health endpoint works: `curl <http://localhost:8000/health>`
3. Check Prometheus config: `cat monitoring/prometheus/prometheus.yml`

### Configuration changes not applied

1. POST request must have valid SimulationConfig JSON
2. Check response for validation errors
3. GET config to verify update applied
