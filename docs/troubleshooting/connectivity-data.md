# Connectivity, Data & Performance Troubleshooting

This guide covers network connectivity, live mode issues, data storage, POI
management, and performance optimization.

## Network & Connectivity

### Services Can't Communicate

**Verify network connectivity:**

```bash
# Check if containers can reach each other
docker compose exec starlink-location curl http://prometheus:9090
docker compose exec prometheus curl http://starlink-location:8000/health
docker compose exec grafana curl http://prometheus:9090
```

**Check network configuration:**

```bash
# View network
docker network inspect starlink-dashboard-dev_starlink-net

# Verify all containers connected
docker network inspect starlink-dashboard-dev_starlink-net | rg -A 10 "Containers"
```

### Live Mode Won't Connect to Dish

**Test network connectivity:**

```bash
# From host
ping 192.168.100.1
timeout 5 bash -c \
  'cat < /dev/null > /dev/tcp/192.168.100.1/9200' && \
  echo "Connection OK" || echo "Connection failed"

# From container
docker compose exec starlink-location ping -c 3 192.168.100.1
docker compose exec starlink-location \
  timeout 5 bash -c \
  'cat < /dev/null > /dev/tcp/192.168.100.1/9200' && \
  echo "OK" || echo "Failed"
```

**Check network mode:**

```bash
# Verify bridge vs host mode
docker inspect starlink-location | rg -A 2 NetworkMode

# For bridge mode, check extra_hosts
docker inspect starlink-location | rg -A 5 extra_hosts
```

**Update IP if needed:**

```bash
# Edit .env
nano .env
STARLINK_DISH_HOST=<your-actual-ip>

# Restart
docker compose down
docker compose up -d
```

---

## Additional Documentation

For more troubleshooting topics, see:

- [Live Mode Issues](connectivity-live-mode.md)
- [Data Storage Issues](connectivity-data-storage.md)
- [POI Management Issues](connectivity-poi-management.md)
- [Performance Issues](connectivity-performance.md)
