# Network Configuration

[Back to Configuration Guide](./README.md)

---

## Port Configuration

### Default Ports

- Backend: `8000`
- Prometheus: `9090`
- Grafana: `3000`

### Changing Ports

Edit `.env`:

```bash
STARLINK_LOCATION_PORT=8001
PROMETHEUS_PORT=9091
GRAFANA_PORT=3001
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
sudo ufw allow 3000/tcp  # Grafana
sudo ufw allow 8000/tcp  # Backend
sudo ufw allow 9090/tcp  # Prometheus

# Verify
sudo ufw status
```

### Linux (firewalld)

```bash
# Open ports
sudo firewall-cmd --permanent --add-port=3000/tcp
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --permanent --add-port=9090/tcp

# Reload
sudo firewall-cmd --reload
```

### Windows Firewall

```powershell
# Open ports in Windows Firewall
New-NetFirewallRule -DisplayName "Grafana" -Direction Inbound -LocalPort 3000 -Protocol TCP -Action Allow
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
lsof -i :3000
lsof -i :8000
lsof -i :9090

# Windows
netstat -ano | findstr :3000
```

### Test Container Connectivity

```bash
# Test if containers can reach each other
docker compose exec starlink-location curl http://prometheus:9090
docker compose exec prometheus curl http://starlink-location:8000/health
docker compose exec grafana curl http://prometheus:9090
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
