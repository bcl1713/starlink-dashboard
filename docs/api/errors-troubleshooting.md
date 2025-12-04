# Error Troubleshooting Guide

[Back to API Reference](./README.md) | [Back to errors](./errors.md)

---

## Overview

Diagnostic steps and solutions for persistent or unexplained API errors.

---

## Check Service Health

Always start by checking service health:

```bash
curl http://localhost:8000/health
```

If this fails, the backend may be down or unreachable.

---

## Enable Debug Logging

For detailed error information:

```bash
# Edit .env
LOG_LEVEL=DEBUG

# Restart services
docker compose down
docker compose up -d

# View logs
docker compose logs -f starlink-location
```

---

## Common Solutions

### "Service is healthy" but endpoints fail

**Cause:** Initialization issue with specific components.

**Solution:**

```bash
# Check logs for errors
docker compose logs starlink-location | rg -i error

# Restart service
docker compose restart starlink-location
```

---

### Persistent 500 errors

**Cause:** Backend configuration or data file issues.

**Solution:**

```bash
# Check POI file
cat backend/starlink-location/data/pois.json | jq .

# Reset if corrupted
echo '[]' > backend/starlink-location/data/pois.json

# Restart
docker compose restart starlink-location
```

---

### Validation errors on valid data

**Cause:** Type mismatch or encoding issues.

**Solution:**

```bash
# Ensure JSON is properly formatted
curl -X POST http://localhost:8000/api/pois \
  -H "Content-Type: application/json" \
  -d @poi_data.json  # Use file input for complex data

# Check request headers
curl -v http://localhost:8000/api/pois  # Verbose output
```

---

### 404 errors on existing resources

**Cause:** Incorrect ID or resource was deleted.

**Solution:**

```bash
# List all POIs to get correct IDs
curl http://localhost:8000/api/pois | jq '.[] | {id, name}'

# Check active routes
curl http://localhost:8000/api/routes
```

---

## Getting Help

If errors persist:

1. **Collect error information:**
   - Full error response (JSON)
   - Request that triggered error
   - Service logs

2. **Check documentation:**
   - [Troubleshooting Guide](../troubleshooting/README.md)
   - [Setup Guide](../setup/README.md)
   - Interactive API docs at `/docs`

3. **Common issues:**
   - Docker container not running
   - Port conflicts
   - File permission issues
   - Missing environment variables

---

[Back to API Reference](./README.md) | [Back to errors](./errors.md)
