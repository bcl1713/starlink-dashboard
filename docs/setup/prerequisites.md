# Prerequisites

[Back to Setup Guide](./README.md) | [Back to main docs](../INDEX.md)

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Required Software](#required-software)
3. [OS-Specific Notes](#os-specific-notes)
4. [Network Requirements](#network-requirements)
5. [Verification Steps](#verification-steps)

---

## System Requirements

### Minimum Hardware

- **CPU:** 2 cores
- **RAM:** 4 GB
- **Disk Space:** 5 GB free
  - Docker images: ~1 GB
  - Prometheus data (1 year): ~2.4 GB
  - Development/caching: ~1 GB

### Recommended Hardware

- **CPU:** 4+ cores
- **RAM:** 8 GB
- **Disk Space:** 10 GB free
- **SSD Storage:** Recommended for better performance

---

## Required Software

### Docker

**Version:** 20.10 or higher

Docker is required to run all services in containers.

**Check installed version:**

```bash
docker --version
```

**Expected output:**

```text
Docker version 20.10.x, build xxxxx
```

**Installation:**

- **Linux:** [Install Docker Engine](https://docs.docker.com/engine/install/)
- **macOS:**
  [Install Docker Desktop](https://docs.docker.com/desktop/install/mac-install/)
- **Windows:**
  [Install Docker Desktop](https://docs.docker.com/desktop/install/windows-install/)

---

### Docker Compose

**Version:** 2.0 or higher

Docker Compose orchestrates multiple containers.

**Check installed version:**

```bash
docker compose version
```

**Expected output:**

```text
Docker Compose version v2.x.x
```

**Note:** Docker Compose v2 is included with Docker Desktop. On Linux, you may
need to install it separately.

**Installation (Linux):**

```bash
sudo apt-get update
sudo apt-get install docker-compose-plugin
```

---

### Git

**Version:** Any recent version

Required to clone the repository.

**Check installed version:**

```bash
git --version
```

**Installation:**

- **Linux:** `sudo apt-get install git`
- **macOS:** Included with Xcode Command Line Tools
- **Windows:** [Git for Windows](https://git-scm.com/download/win)

---

### Optional: jq

**Purpose:** JSON parsing for testing

While not required, jq makes testing API endpoints much easier.

**Installation:**

- **Linux:** `sudo apt-get install jq`
- **macOS:** `brew install jq`
- **Windows:** [Download from GitHub](https://stedolan.github.io/jq/download/)

**Test:**

```bash
curl <http://localhost:8000/health> | jq .
```

---

## OS-Specific Notes

### Linux

**Advantages:**

- ✅ Full feature support
- ✅ Best performance
- ✅ Host network mode available

**Additional Setup:**

1. **Add user to docker group** (avoid sudo):

   ```bash
   sudo usermod -aG docker $USER
   newgrp docker
   ```

1. **Start Docker service:**

   ```bash
   sudo systemctl start docker
   sudo systemctl enable docker  # Start on boot
   ```

1. **Firewall configuration:**

   Open ports if using firewall:

   ```bash
   sudo ufw allow 3000  # Grafana
   sudo ufw allow 8000  # Backend
   sudo ufw allow 9090  # Prometheus
   ```

---

### macOS (Intel or Apple Silicon)

**Advantages:**

- ✅ Full feature support via Docker Desktop
- ✅ Uses bridge network mode (cross-platform compatible)

**Additional Setup:**

1. **Install Docker Desktop** from official website

2. **Configure Docker Desktop:**
   - Resources → Memory: Allocate at least 4 GB
   - Resources → Disk: Allocate at least 10 GB

3. **Ensure Docker Desktop is running** before starting services

---

### Windows

**Advantages:**

- ✅ Full feature support via Docker Desktop
- ✅ WSL 2 provides near-native Linux performance

**Additional Setup:**

1. **Install WSL 2:**

   ```powershell
   wsl --install
   ```

1. **Install Docker Desktop** with WSL 2 backend enabled

1. **Configure Docker Desktop:**
   - Settings → Resources → WSL Integration
   - Enable integration with your WSL distribution

1. **Run commands from WSL terminal** for best experience

---

## Network Requirements

### Internet Access

Required for:

- Pulling Docker images
- Initial setup
- Grafana plugin downloads (if applicable)

### Ports

The following ports must be available on localhost:

| Port | Service     | Protocol |
| ---- | ----------- | -------- |
| 3000 | Grafana     | HTTP     |
| 8000 | Backend API | HTTP     |
| 9090 | Prometheus  | HTTP     |

**Check port availability:**

```bash
# Linux/macOS
lsof -i :3000
lsof -i :8000
lsof -i :9090

# Windows
netstat -ano | findstr :3000
netstat -ano | findstr :8000
netstat -ano | findstr :9090
```

If ports are in use, either free them or configure different ports in `.env`.

---

### Live Mode Requirements

**Additional requirements for connecting to Starlink terminal:**

1. **Network Access:**
   - Terminal accessible at `192.168.100.1` (default)
   - Port `9200` open for gRPC communication

2. **Network Mode:**
   - **Bridge mode:** Cross-platform, configured by default
   - **Host mode:** Linux only, best performance

---

## Verification Steps

Run these checks before proceeding to installation:

### 1. Docker Check

```bash
docker run hello-world
```

**Expected:** Success message about Docker installation.

---

### 2. Docker Compose Check

```bash
docker compose version
```

**Expected:** Version 2.0 or higher displayed.

---

### 3. Disk Space Check

```bash
df -h
```

**Expected:** At least 5 GB free in the location where you'll clone the
repository.

---

### 4. Memory Check

```bash
# Linux
free -h

# macOS
vm_stat

# Windows (PowerShell)
systeminfo | findstr Memory
```

**Expected:** At least 4 GB RAM available.

---

### 5. Port Availability Check

```bash
# Check all required ports
for port in 3000 8000 9090; do
  if lsof -i :$port > /dev/null 2>&1; then
    echo "Port $port is in use"
  else
    echo "Port $port is available"
  fi
done
```

**Expected:** All ports available.

---

## Troubleshooting Prerequisites

### Docker won't start

**Linux:**

```bash
sudo systemctl status docker
sudo journalctl -u docker --no-pager
```

**macOS/Windows:**

- Check Docker Desktop is running
- Restart Docker Desktop
- Check system resources in Docker Desktop settings

---

### Permission denied errors

**Linux:**

```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Log out and back in, or run:
newgrp docker
```

---

### WSL 2 issues (Windows)

```bash
# Update WSL
wsl --update

# Set default version
wsl --set-default-version 2

# Check distribution version
wsl -l -v
```

---

### Port conflicts

**Find what's using a port:**

```bash
# Linux/macOS
lsof -i :3000

# Windows
netstat -ano | findstr :3000
```

**Options:**

1. Stop the conflicting service
2. Change ports in `.env` file
3. Use Docker's port mapping

---

## Next Steps

Once all prerequisites are met, proceed to:

**[Installation →](./installation.md)**

---

[Back to Setup Guide](./README.md) | [Back to main docs](../INDEX.md)
