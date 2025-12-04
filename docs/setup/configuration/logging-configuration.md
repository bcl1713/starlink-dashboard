# Logging Configuration

[Back to Configuration Guide](./README.md)

---

## Log Levels

Available levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

### In `.env`

```bash
# Development: detailed logs
LOG_LEVEL=DEBUG

# Production: standard logs
LOG_LEVEL=INFO

# Quiet: errors only
LOG_LEVEL=ERROR
```

**Apply:**

```bash
docker compose restart starlink-location
```

---

## Log Format

### JSON Logs (default)

Machine-readable format for log aggregation:

```bash
JSON_LOGS=true
```

**Example output:**

```json
{
  "timestamp": "2025-12-04T10:30:00Z",
  "level": "INFO",
  "message": "Backend started",
  "service": "starlink-location"
}
```

### Human-Readable Logs

Plain text format for development:

```bash
JSON_LOGS=false
```

**Example output:**

```text
2025-12-04 10:30:00 INFO Backend started
```

---

## View Logs

### All Services

```bash
docker compose logs -f
```

### Specific Service

```bash
docker compose logs -f starlink-location
docker compose logs -f prometheus
docker compose logs -f grafana
```

### Filter by Level

```bash
docker compose logs starlink-location | rg -i error
docker compose logs starlink-location | rg -i warning
```

### Save Logs to File

```bash
docker compose logs > logs.txt
docker compose logs starlink-location > backend.log
```

---

## Log Rotation

Docker automatically rotates logs. Configure in `docker-compose.yml`:

```yaml
services:
  starlink-location:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

This keeps the last 3 files of 10MB each (30MB total per container).

---

[Back to Configuration Guide](./README.md)
