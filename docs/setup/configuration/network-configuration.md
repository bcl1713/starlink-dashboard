# Network Configuration

[Back to Configuration Guide](./README.md)

---

## Port Configuration

### Default Ports

- Backend: `8000`
- Prometheus: `9090`
- Mission Planner: `5173`

### Changing Ports

Edit `.env`:

```bash
STARLINK_LOCATION_PORT=8001
PROMETHEUS_PORT=9091
```

**Apply:**

```bash
docker compose down
docker compose up -d
```

### Access

- **Frontend**: `http://localhost:3001`
- **Backend API**: `http://localhost:8001`
- **Prometheus**: `http://localhost:9091`

---

## Firewall Configuration

### Linux (ufw)

```bash
# Open ports
sudo ufw allow 5173/tcp  # Mission Planner
sudo ufw allow 8000/tcp  # Backend
sudo ufw allow 9090/tcp  # Prometheus

# Verify
sudo ufw status
```

### Linux (firewalld)

```bash
# Open ports
sudo firewall-cmd --permanent --add-port=5173/tcp
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --permanent --add-port=9090/tcp

# Reload
sudo firewall-cmd --reload
```

### Windows Firewall

```powershell
# Open ports in Windows Firewall
New-NetFirewallRule -DisplayName "Mission Planner" -Direction Inbound -LocalPort 5173 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Backend" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Prometheus" -Direction Inbound -LocalPort 9090 -Protocol TCP -Action Allow
```

### macOS Firewall

macOS firewall typically allows localhost connections by default. If needed:

1. System Preferences > Security & Privacy > Firewall
2. Click "Firewall Options"
3. Add Docker to allowed applications

---

## Network Troubleshooting

### Check Port Conflicts

```bash
# Linux/macOS
lsof -i :5173
lsof -i :8000
lsof -i :9090

# Windows
netstat -ano | findstr :5173
```

### Test Container Connectivity

```bash
# Test if containers can reach each other
docker compose exec starlink-location curl http://prometheus:9090
docker compose exec prometheus curl http://starlink-location:8000/health
curl --fail http://localhost:9090/-/ready
```

### Verify Network

```bash
# View network
docker network inspect starlink-dashboard-dev_starlink-net

# Verify all containers connected
docker network inspect starlink-dashboard-dev_starlink-net | rg -A 10 "Containers"
```

---

[Back to Configuration Guide](./README.md)
