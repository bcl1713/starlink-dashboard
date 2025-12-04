# Storage Configuration

[Back to Configuration Guide](./README.md)

---

## Data Retention

### Storage Calculation

```text
Number of metrics: 45
Scrape interval: 1 second
Retention period: 1 year (31,536,000 seconds)
Size per sample: ~1.5 bytes (compressed)
Compression overhead: ~1.2x

Storage = (45 × 31,536,000 × 1.5 × 1.2) / 1,073,741,824 ≈ 2.4 GB
```

### Common Retention Periods

| Retention | Storage | Use Case            |
| --------- | ------- | ------------------- |
| `1y`      | ~2.4 GB | Long-term analysis  |
| `90d`     | ~600 MB | Quarterly reviews   |
| `30d`     | ~200 MB | Monthly monitoring  |
| `15d`     | ~100 MB | Development/testing |
| `7d`      | ~50 MB  | Minimal storage     |

### Configure Retention

Edit `.env`:

```bash
PROMETHEUS_RETENTION=30d  # Or your preferred retention
```

Apply:

```bash
docker compose down
docker compose up -d
```

---

## Volume Management

### View Volumes

```bash
docker volume ls | rg starlink
```

### Check Volume Size

```bash
docker volume inspect prometheus_data
```

### Clean Up Old Data

```bash
# Stop services
docker compose down

# Remove volumes (WARNING: deletes all data)
docker volume rm starlink-dashboard-dev_prometheus_data

# Restart
docker compose up -d
```

### Backup Volumes

```bash
# Backup Prometheus data
docker run --rm \
  -v starlink-dashboard-dev_prometheus_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/prometheus-backup.tar.gz -C /data .

# Backup Grafana data
docker run --rm \
  -v starlink-dashboard-dev_grafana_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/grafana-backup.tar.gz -C /data .
```

### Restore Volumes

```bash
# Restore Prometheus data
docker run --rm \
  -v starlink-dashboard-dev_prometheus_data:/data \
  -v $(pwd):/backup \
  alpine tar xzf /backup/prometheus-backup.tar.gz -C /data

# Restore Grafana data
docker run --rm \
  -v starlink-dashboard-dev_grafana_data:/data \
  -v $(pwd):/backup \
  alpine tar xzf /backup/grafana-backup.tar.gz -C /data
```

---

[Back to Configuration Guide](./README.md)
