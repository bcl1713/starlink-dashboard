# Connection Testing & Verification

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
