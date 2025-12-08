# Data Storage Troubleshooting

Troubleshooting guide for data persistence and storage issues.

---

## Data Not Persisting After Restart

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
