# Troubleshooting & Best Practices

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
