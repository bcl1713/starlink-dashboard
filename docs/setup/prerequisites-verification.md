# Prerequisites Verification and Troubleshooting

Verification steps and troubleshooting for prerequisites.

[Back to Setup Guide](./README.md) | [Back to main docs](../index.md)

---

## Table of Contents

1. [Verification Steps](#verification-steps)
2. [Troubleshooting](#troubleshooting)

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

## Troubleshooting

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

### Docker Desktop resource issues

**Symptoms:**

- Slow performance
- Services failing to start
- Out of memory errors

**Solutions:**

1. **Increase allocated resources:**
   - Docker Desktop → Settings → Resources
   - Memory: Allocate at least 4 GB (8 GB recommended)
   - CPU: Allocate at least 2 cores (4 cores recommended)
   - Disk: Allocate at least 10 GB

2. **Restart Docker Desktop** after changes

3. **Clean up unused resources:**

   ```bash
   docker system prune -a
   ```

---

### Network connectivity issues

**Symptoms:**

- Cannot pull Docker images
- Timeout errors during build

**Solutions:**

1. **Check internet connection**

2. **Configure Docker proxy** (if behind corporate firewall):

   ```bash
   # Create or edit ~/.docker/config.json
   {
     "proxies": {
       "default": {
         "httpProxy": "http://proxy.example.com:8080",
         "httpsProxy": "http://proxy.example.com:8080"
       }
     }
   }
   ```

3. **Test DNS resolution:**

   ```bash
   docker run busybox nslookup google.com
   ```

---

### Linux-specific issues

#### Docker daemon not starting

```bash
# Check status
sudo systemctl status docker

# View logs
sudo journalctl -xeu docker

# Restart service
sudo systemctl restart docker
```

#### Permission issues with volumes

```bash
# Check volume permissions
ls -la /var/lib/docker/volumes

# Fix permissions if needed
sudo chown -R $USER:$USER /path/to/project
```

---

### macOS-specific issues

#### Docker Desktop stuck at "Starting"

1. Quit Docker Desktop completely
2. Run: `rm -rf ~/Library/Group\ Containers/group.com.docker`
3. Restart Docker Desktop

#### Apple Silicon compatibility

Most images work on Apple Silicon (M1/M2). If you encounter issues:

```bash
# Force platform for compatibility
docker pull --platform linux/amd64 image:tag
```

---

### Windows-specific issues

#### WSL 2 not installed

```powershell
# Enable WSL
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart

# Enable Virtual Machine Platform
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

# Restart computer, then:
wsl --set-default-version 2
```

#### Docker Desktop integration issues

1. Docker Desktop → Settings → Resources → WSL Integration
2. Enable integration with your WSL distribution
3. Restart Docker Desktop

#### File permission issues

Windows file permissions can cause issues. Run from WSL filesystem:

```bash
# Clone in WSL home directory, not /mnt/c/
cd ~
git clone <repository>
```

---

## Next Steps

Once all verification checks pass, proceed to installation:

**[Installation →](./installation.md)**

---

[Back to Setup Guide](./README.md) | [Back to main docs](../index.md)
