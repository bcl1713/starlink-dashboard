# syntax=docker/dockerfile:1
# The renderer and Python runtime share Debian 13's ABI.
FROM node:22.22.2-trixie-slim AS renderer-build
WORKDIR /opt/mission-map/frontend/mission-planner
COPY frontend/mission-planner/package.json frontend/mission-planner/package-lock.json ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; \
    npm ci --strict-ssl=true --no-audit --no-fund
COPY frontend/mission-planner/ ./
RUN npm run build:mission-export
RUN node --input-type=module -e 'import { readFileSync, readdirSync, writeFileSync } from "node:fs"; import { createHash } from "node:crypto"; const files = ["package-lock.json", ...readdirSync("src/mission-export").map(f => "src/mission-export/" + f), ...readdirSync("dist-mission-export/assets").map(f => "dist-mission-export/assets/" + f), "dist-mission-export/earth-day-hi.jpg", "dist-mission-export/city-lights-mask.png"]; writeFileSync("runtime-manifest.json", JSON.stringify(Object.fromEntries(files.sort().map(f => [f, createHash("sha256").update(readFileSync(f)).digest("hex")]))));'

FROM python:3.11-slim-trixie AS builder

WORKDIR /app

# Install dependencies
COPY backend/starlink-location/requirements.txt .
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim-trixie

WORKDIR /app

COPY --from=renderer-build /usr/local/bin/node /usr/local/bin/node
COPY --from=renderer-build /opt/mission-map/frontend/mission-planner/node_modules/playwright-core /opt/mission-map/frontend/mission-planner/node_modules/playwright-core
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/mission-map-browsers
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; \
    node /opt/mission-map/frontend/mission-planner/node_modules/playwright-core/cli.js install --with-deps chromium --only-shell && \
    dpkg-query -W > /opt/mission-map-os-packages.txt && \
    rm -rf /var/lib/apt/lists/*
COPY --from=renderer-build /opt/mission-map/frontend/mission-planner/dist-mission-export /opt/mission-map/frontend/mission-planner/dist-mission-export
COPY --from=renderer-build /opt/mission-map/frontend/mission-planner/src/mission-export /opt/mission-map/frontend/mission-planner/src/mission-export
COPY --from=renderer-build /opt/mission-map/frontend/mission-planner/package-lock.json /opt/mission-map/frontend/mission-planner/runtime-manifest.json /opt/mission-map/frontend/mission-planner/

# Install curl for health checks and runtime essentials
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security before copying dependencies into its home.
# COPY --chown avoids a slow recursive chown over the installed Python package tree.
RUN useradd -m -u 1000 appuser
RUN mkdir -p /app/data/gfs/products /app/data/gfs/staging /app/data/gfs-mailbox/leases && \
    chown -R appuser:appuser /app/data/gfs /app/data/gfs-mailbox

# Copy Python dependencies from builder with final ownership already set
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

ARG ACCEPTANCE_CANDIDATE_SHA
RUN test -n "$ACCEPTANCE_CANDIDATE_SHA"
LABEL org.opencontainers.image.revision=$ACCEPTANCE_CANDIDATE_SHA

# Copy application code and configuration with final ownership already set
COPY --chown=appuser:appuser backend/starlink-location/main.py .
COPY --chown=appuser:appuser backend/starlink-location/config.yaml .
COPY --chown=appuser:appuser backend/starlink-location/app/ ./app/
COPY --chown=appuser:appuser backend/starlink-location/tests/ ./tests/

# Create data/cache directories with proper permissions without walking the dependency tree
RUN mkdir -p /data/routes /data/sim_routes /home/appuser/.local/share/cartopy /home/appuser/.config/matplotlib /home/appuser/.cache/matplotlib && \
    chown appuser:appuser /data /data/routes /data/sim_routes /home/appuser/.local/share/cartopy /home/appuser/.config /home/appuser/.config/matplotlib /home/appuser/.cache /home/appuser/.cache/matplotlib && \
    chmod 755 /data /data/routes /data/sim_routes /home/appuser/.local /home/appuser/.local/share /home/appuser/.local/share/cartopy /home/appuser/.config /home/appuser/.config/matplotlib /home/appuser/.cache /home/appuser/.cache/matplotlib

COPY backend/starlink-location/entrypoint.sh /usr/local/bin/entrypoint.sh
ENTRYPOINT ["entrypoint.sh"]

# Set PATH to include user's local bin
ENV PATH=/home/appuser/.local/bin:$PATH

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
