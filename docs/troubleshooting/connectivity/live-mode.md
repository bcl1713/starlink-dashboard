# Live Mode Troubleshooting

Troubleshooting guide for live mode connectivity and data issues.

---

## Symptom: "Live mode: waiting for dish connection"

**This is normal!** The system is designed to wait for the dish.

**Verify dish status:**

```bash
# Check health endpoint
curl http://localhost:8000/health | jq '.dish_connected'

# Should be false initially, true when connected

# Monitor connection attempts
docker compose logs -f starlink-location | rg -i "dish|connect"
```

**Troubleshoot connection:**

1. **Verify dish IP:**

   ```bash
   ping 192.168.100.1
   # If not reachable, update .env with correct IP
   ```

2. **Check network mode:**

   ```bash
   # Bridge mode (cross-platform)
   docker inspect starlink-location | rg -A 5 extra_hosts

   # Host mode (Linux only)
   docker inspect starlink-location | rg NetworkMode
   ```

3. **Test from container:**

   ```bash
   docker compose exec starlink-location \
     timeout 5 bash -c \
     'cat < /dev/null > /dev/tcp/192.168.100.1/9200'
   # Should succeed if reachable
   ```

4. **Check firewall:**

   ```bash
   # Linux: check firewall rules
   sudo ufw status
   sudo ufw allow 9200

   # macOS: System Preferences > Security & Privacy > Firewall
   # Windows: Settings > Windows Defender Firewall
   ```

---

## Metrics from Live Mode Appear Stale

```bash
# Check update frequency
for i in {1..5}; do
  curl -s http://localhost:8000/api/status | jq '.timestamp'
  sleep 2
done

# Timestamps should change

# If stuck, check logs
docker compose logs starlink-location | rg -i "error|fail"

# May need to reconnect
docker compose restart starlink-location
```
