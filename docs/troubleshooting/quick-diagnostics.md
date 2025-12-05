# Troubleshooting Quick Diagnostics

**Last Updated:** 2025-10-31 **Version:** 0.2.0

## Quick Diagnostics

Before diving into specific issues, run these checks:

```bash
# 1. Check all services running
docker compose ps

# 2. Check backend health
curl http://localhost:8000/health

# 3. Check logs for errors
docker compose logs --tail=50

# 4. Check resource usage
docker stats --no-stream
```

## Service Won't Start

### Symptom: Container exits immediately

**Check logs:**

```bash
docker compose logs starlink-location
docker compose logs prometheus
docker compose logs grafana
```

**Common Causes & Solutions:**

#### 1. Configuration Error

```bash
# Check syntax of .env
cat .env | rg "^[A-Z_]+=.*"

# Rebuild without cache
docker compose down
docker compose build --no-cache
docker compose up -d
```

#### 2. Port Binding Failed

```bash
# Find what's using the port
lsof -i :8000  # Backend
lsof -i :9090  # Prometheus
lsof -i :3000  # Grafana

# Kill process or change port in .env
kill -9 <PID>
```

#### 3. Insufficient Disk Space

```bash
# Check available space
df -h

# If < 5 GB free:
docker system prune -a  # Remove unused images
docker volume prune      # Remove unused volumes
```

#### 4. Memory Issues

```bash
# Check system memory
free -h
docker stats --no-stream

# Stop other services or increase swap
docker compose down
# Stop unnecessary apps
docker compose up -d
```

### Symptom: "Failed to connect to Docker daemon"

```bash
# Ensure Docker is running
sudo systemctl status docker  # Linux
# or check Docker Desktop (macOS/Windows)

# Start Docker
sudo systemctl start docker
```

## Port Conflicts

### Symptom: "Address already in use"

**Find process using port:**

```bash
# Linux/macOS
lsof -i :3000
lsof -i :8000
lsof -i :9090

# Windows
netstat -ano | findstr :3000
```

#### Solution 1: Kill process

```bash
# Linux/macOS
kill -9 <PID>

# Windows
taskkill /PID <PID> /F
```

#### Solution 2: Change port in .env

```bash
# Edit .env
nano .env

# Change port
GRAFANA_PORT=3001
STARLINK_LOCATION_PORT=8001
PROMETHEUS_PORT=9091

# Restart
docker compose down
docker compose up -d
```

#### Solution 3: Check if service is running

```bash
# See what's actually bound to the port
netstat -tlnp | rg 3000  # Linux
lsof -i :3000            # macOS
netstat -ano | findstr 3000 # Windows

# If it's Docker, just restart it
docker compose restart
```

## Debug Logging

### Enable debug mode

```bash
# Edit .env
LOG_LEVEL=DEBUG
JSON_LOGS=true

# Restart
docker compose down
docker compose up -d

# View detailed logs
docker compose logs -f starlink-location
```

### View all component logs

```bash
# All services
docker compose logs -f

# Specific service with timestamps
docker compose logs -f --timestamps starlink-location

# Last N lines
docker compose logs --tail=100 starlink-location

# Search for errors
docker compose logs | rg -i "error"
```

### Save logs to file

```bash
# Save all logs
docker compose logs > logs.txt

# Save specific service logs
docker compose logs starlink-location > backend.log
docker compose logs prometheus > prometheus.log
docker compose logs grafana > grafana.log
```

## Getting Help

### Before asking for help, gather

1. **Log output:**

   ```bash
   docker compose logs > debug-logs.txt
   ```

2. **System info:**

   ```bash
   docker --version
   docker compose version
   uname -a
   ```

3. **Configuration:**

   ```bash
   cat .env | rg -v "PASSWORD"
   docker compose config | head -50
   ```

4. **Current state:**

   ```bash
   docker compose ps
   docker stats --no-stream
   curl http://localhost:8000/health
   curl http://localhost:9090/api/v1/targets
   ```

### Resources

- [Backend Issues](./services/backend.md)
- [Service Issues](./service-issues.md)
- [Data Issues](./data-issues.md)
- [API Reference](../API-REFERENCE.md)
- [Setup Guide](../SETUP-GUIDE.md)
- [Design Document](../design-document.md)
- [Backend README](../../backend/starlink-location/README.md)
- [Grafana Documentation](https://grafana.com/docs/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
