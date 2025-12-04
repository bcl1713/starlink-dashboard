# Troubleshooting Data & Storage Issues

**Last Updated:** 2025-10-31 **Version:** 0.2.0

## Data & Storage Issues

### Symptom: POI list empty or missing

**Check POI file:**

```bash
# File exists?
ls -la backend/starlink-location/data/pois.json

# Content valid?
cat backend/starlink-location/data/pois.json | jq .

# If corrupted, reset
echo '[]' > backend/starlink-location/data/pois.json
docker compose restart starlink-location
```

### Issue: Can't create/edit POIs

**Check API:**

```bash
# Test POI creation
curl -X POST http://localhost:8000/api/pois \
  -H "Content-Type: application/json" \
  -d '{"name": "Test", "latitude": 40.7, "longitude": -74.0}'

# Check response for errors
# If 500 error, check backend logs:
docker compose logs starlink-location | tail -20
```

**Check file permissions:**

```bash
# POI file writable?
docker compose exec starlink-location ls -la /app/data/pois.json

# Fix if needed
docker compose exec starlink-location chmod 666 /app/data/pois.json
```

### Symptom: Data not persisting after restart

**Verify volumes mounted:**

```bash
# Check volume mounts in docker-compose.yml
rg -A 5 "volumes:" docker-compose.yml

# Verify volume exists
docker volume ls | rg poi
docker volume ls | rg prometheus
docker volume ls | rg grafana

# Check volume content
docker run -v poi_data:/data alpine ls -la /data
```

## Route Management Issues

### Issue: Routes not loading

**Check route files:**

```bash
# List route files
ls -la data/routes/

# Verify KML format
cat data/routes/your-route.kml | head -50

# Check backend logs for import errors
docker compose logs starlink-location | rg -i "route|kml"
```

### Issue: Route API errors

**Test route endpoints:**

```bash
# List all routes
curl http://localhost:8000/api/routes | jq .

# Get specific route
curl http://localhost:8000/api/routes/{route_id} | jq .

# Check for errors
docker compose logs starlink-location | tail -30
```

### Issue: Route not displaying in Grafana

**Verify route data:**

```bash
# Check active route
curl http://localhost:8000/api/routes/active | jq .

# Verify route metrics
curl http://localhost:8000/metrics | rg route_progress

# Check Grafana panel query
# In Grafana > Edit panel > Query inspector
```

## Mission Planning Issues

### Issue: Mission data not saving

**Check mission storage:**

```bash
# Check if missions directory exists
ls -la backend/starlink-location/data/missions/

# Verify file permissions
docker compose exec starlink-location ls -la /app/data/missions/

# Test mission creation
curl -X POST http://localhost:8000/api/missions \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Mission", "route_id": "test"}'
```

### Issue: Timeline calculations slow

**Monitor performance:**

```bash
# Check backend logs for timing
docker compose logs starlink-location | rg -i "timeline|computation"

# Monitor CPU usage
docker stats starlink-location

# Reduce timeline resolution if needed
# Edit mission configuration to use fewer waypoints
```

### Issue: Export generation failing

**Check export endpoints:**

```bash
# Test PDF export
curl -X GET http://localhost:8000/api/missions/{id}/export/pdf \
  -o test-export.pdf

# Test CSV export
curl -X GET http://localhost:8000/api/missions/{id}/export/csv \
  -o test-export.csv

# Check logs for errors
docker compose logs starlink-location | rg -i "export|pdf|csv"
```

## Database Issues

### Issue: Database corruption

**Reset database:**

```bash
# Backup current data
cp backend/starlink-location/data/pois.json pois.backup.json

# Reset to empty state
echo '[]' > backend/starlink-location/data/pois.json

# Restart service
docker compose restart starlink-location

# Verify service starts
curl http://localhost:8000/health
```

### Issue: Volume mount problems

**Check volume mounts:**

```bash
# Inspect container mounts
docker inspect starlink-location | rg -A 10 "Mounts"

# Verify host path exists
ls -la backend/starlink-location/data/

# Check permissions
docker compose exec starlink-location ls -la /app/data/
```

## Storage Space Issues

### Issue: Running out of disk space

**Check storage usage:**

```bash
# Overall disk usage
df -h

# Docker-specific usage
docker system df

# Volume sizes
docker volume ls
docker volume inspect prometheus_data | rg Mountpoint
du -sh /var/lib/docker/volumes/*/
```

**Clean up space:**

```bash
# Remove unused containers/images
docker system prune -a

# Remove unused volumes (WARNING: data loss)
docker volume prune

# Reduce Prometheus retention
echo "PROMETHEUS_RETENTION=15d" >> .env
docker compose down
docker compose up -d
```

## Backup and Recovery

### Backup important data

```bash
# Backup POI data
cp backend/starlink-location/data/pois.json backup/pois-$(date +%Y%m%d).json

# Backup routes
tar -czf backup/routes-$(date +%Y%m%d).tar.gz data/routes/

# Backup Prometheus data (requires downtime)
docker compose down
tar -czf backup/prometheus-$(date +%Y%m%d).tar.gz \
  /var/lib/docker/volumes/starlink-dashboard-dev_prometheus_data/
docker compose up -d

# Backup Grafana dashboards
docker compose exec grafana \
  tar -czf - /var/lib/grafana > backup/grafana-$(date +%Y%m%d).tar.gz
```

### Restore from backup

```bash
# Restore POI data
docker compose down
cp backup/pois-20251031.json backend/starlink-location/data/pois.json
docker compose up -d

# Restore routes
tar -xzf backup/routes-20251031.tar.gz -C data/

# Restore Prometheus (requires downtime)
docker compose down
rm -rf /var/lib/docker/volumes/starlink-dashboard-dev_prometheus_data/*
tar -xzf backup/prometheus-20251031.tar.gz \
  -C /var/lib/docker/volumes/starlink-dashboard-dev_prometheus_data/
docker compose up -d
```

## Related Documentation

- [Quick Diagnostics](./quick-diagnostics.md)
- [Backend Issues](./backend-issues.md)
- [Service Issues](./service-issues.md)
- [API Reference](../API-REFERENCE.md)
- [Setup Guide](../SETUP-GUIDE.md)
