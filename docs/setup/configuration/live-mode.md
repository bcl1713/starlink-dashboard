# Live Mode Configuration

[Back to Configuration Guide](./README.md)

---

## Overview

**Purpose:** Connect to a real Starlink terminal for actual telemetry.

Live mode connects directly to your Starlink terminal to collect real metrics
and position data.

---

## Prerequisites

1. Starlink terminal on local network
2. Terminal accessible at `192.168.100.1` (default) or known IP
3. Port `9200` accessible for gRPC communication

---

## Basic Configuration

Edit `.env`:

```bash
# Set mode to live
STARLINK_MODE=live

# Configure dish connection
STARLINK_DISH_HOST=192.168.100.1  # Your terminal's IP
STARLINK_DISH_PORT=9200            # Standard gRPC port
```

---

## Network Mode Selection

Choose network mode based on your OS:

### Option A: Bridge Mode (Recommended - Cross-Platform)

Already configured by default. Works on Windows, macOS, and Linux.

**In `docker-compose.yml`:**

```yaml
extra_hosts:
  - "dish.starlink:${STARLINK_DISH_HOST:-192.168.100.1}"
```

No changes needed - this is the default configuration.

### Option B: Host Mode (Linux Only - Best Performance)

For Linux systems, host mode provides direct network access.

**In `docker-compose.yml`:**

Uncomment:

```yaml
network_mode: host
```

And comment out:

```yaml
# extra_hosts:
#   - "dish.starlink:${STARLINK_DISH_HOST:-192.168.100.1}"
```

**Apply changes:**

```bash
docker compose down
docker compose up -d
```

---

## Connection Behavior

The system gracefully handles connection issues:

### On Startup

- If dish unreachable, service starts anyway
- Status shows `dish_connected: false`
- No metrics exported until connection established

### During Operation

- Attempts reconnect on each update cycle
- Returns last known values while reconnecting
- Automatic reconnection when dish becomes available

### Health Check

```bash
curl http://localhost:8000/health | jq .
```

**Connected response:**

```json
{
  "status": "ok",
  "mode": "live",
  "message": "Live mode: connected to dish",
  "dish_connected": true
}
```

**Disconnected response:**

```json
{
  "status": "ok",
  "mode": "live",
  "message": "Live mode: waiting for dish connection",
  "dish_connected": false
}
```

---

## Testing Connection

### 1. Verify dish is reachable

```bash
ping 192.168.100.1
```

**Expected:** Reply from 192.168.100.1

### 2. Test port accessibility

```bash
timeout 5 bash -c 'cat < /dev/null > /dev/tcp/192.168.100.1/9200' && \
  echo "Connection OK" || echo "Connection failed"
```

**Expected:** "Connection OK"

### 3. Check backend logs

```bash
docker compose logs -f starlink-location | rg -i "dish|connect"
```

**Expected:** "Connected to dish" or similar success message

### 4. Verify metrics

```bash
curl http://localhost:8000/metrics | rg starlink_dish
```

**Expected:** Real metrics from your terminal

---

## Custom IP Configuration

If your dish uses a different IP:

```bash
# Edit .env
nano .env

# Update IP
STARLINK_DISH_HOST=192.168.1.100  # Your actual IP

# Restart
docker compose down
docker compose up -d

# Verify
curl http://localhost:8000/health | jq '.dish_connected'
```

---

## Troubleshooting

### Can't Connect to Dish

**Symptoms:**

- `dish_connected: false` in health check
- Logs show connection errors

**Solutions:**

1. **Verify IP address:**

   ```bash
   ping 192.168.100.1
   # If fails, find correct IP and update .env
   ```

2. **Check port accessibility:**

   ```bash
   nc -zv 192.168.100.1 9200
   # Should show "succeeded" or "open"
   ```

3. **Check firewall:**

   ```bash
   # Linux: check firewall rules
   sudo ufw status

   # Allow if needed
   sudo ufw allow 9200
   ```

4. **Verify network mode:**

   ```bash
   # Check if using correct network mode
   docker inspect starlink-location | rg -i networkmode
   ```

5. **Test from container:**

   ```bash
   docker compose exec starlink-location ping 192.168.100.1
   ```

### Metrics Appear Stale

**Symptoms:**

- Metrics not updating
- Timestamps don't change

**Solutions:**

```bash
# Check update frequency
for i in {1..5}; do
  curl -s http://localhost:8000/api/status | jq '.timestamp'
  sleep 2
done

# Timestamps should change

# If stuck, restart backend
docker compose restart starlink-location
```

### Connection Drops Intermittently

**Symptoms:**

- Connected then disconnected repeatedly
- Unstable metrics

**Solutions:**

1. **Check network stability:**

   ```bash
   ping -c 100 192.168.100.1
   # Check for packet loss
   ```

2. **Check terminal status:**
   - Ensure terminal has clear sky view
   - Verify terminal is online (check Starlink app)

3. **Increase reconnection timeout** (if needed):
   - Edit backend config to increase retry intervals

---

## Network Requirements

### Bandwidth

Live mode requires minimal bandwidth:

- Upstream: ~10 KB/s (metrics polling)
- Downstream: ~50 KB/s (metrics + telemetry)

### Latency

- Typical latency: <5ms (local network)
- Acceptable latency: <100ms
- High latency may cause delayed updates

### Firewall Rules

**Required:**

- Allow outbound to `192.168.100.1:9200` (gRPC)
- Allow inbound on configured service ports (8000, 9090, 3000)

---

## Best Practices

### Production Deployment

```bash
# .env for production
STARLINK_MODE=live
STARLINK_DISH_HOST=192.168.100.1
PROMETHEUS_RETENTION=1y
GRAFANA_ADMIN_PASSWORD=<strong-password>
LOG_LEVEL=INFO
JSON_LOGS=true
```

### Testing Live Connection

```bash
# .env for testing
STARLINK_MODE=live
STARLINK_DISH_HOST=192.168.100.1
PROMETHEUS_RETENTION=7d
LOG_LEVEL=DEBUG
JSON_LOGS=false
```

---

## Next Steps

- **[Performance Tuning](./performance-tuning.md)** - Optimize resource usage
- **[Network Configuration](./network-configuration.md)** - Advanced network
  settings
- **[Troubleshooting](../../troubleshooting/README.md)** - Common issues

---

[Back to Configuration Guide](./README.md)
