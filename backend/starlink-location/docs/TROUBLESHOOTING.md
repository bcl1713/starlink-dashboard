# Troubleshooting Guide

[Back to Backend README](../README.md)

---

## Port Already in Use

```bash
lsof -i :8000
kill -9 <PID>
```

---

## Configuration Not Loading

```bash
# Check config file path
ls -la config.yaml

# Test with environment variable
STARLINK_MODE=live uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## Metrics Not Updating

```bash
# Check logs for background update errors
docker compose logs starlink-location | rg -i error

# Verify health endpoint
curl http://localhost:8000/health
```

---

[Back to Backend README](../README.md)
