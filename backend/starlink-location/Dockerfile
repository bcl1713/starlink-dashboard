# syntax=docker/dockerfile:1
FROM node:22.22.2-trixie-slim AS renderer-build
WORKDIR /renderer
COPY frontend/mission-planner/package.json frontend/mission-planner/package-lock.json ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; \
    npm ci --strict-ssl=true --no-audit --no-fund
COPY frontend/mission-planner/src ./src
COPY frontend/mission-planner/public ./public
COPY frontend/mission-planner/mission-export.html frontend/mission-planner/vite.mission-export.config.ts ./
RUN npm run build:mission-export

# Python dependency build stage
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
COPY --from=renderer-build /renderer/node_modules/playwright /opt/customer-briefing/node_modules/playwright
COPY --from=renderer-build /renderer/node_modules/playwright-core /opt/customer-briefing/node_modules/playwright-core
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/customer-briefing/browsers \
    BRIEFING_APO_PATH="/opt/customer-briefing/APO Patch.jpg"
# The renderer remains available when development mounts replace /app.
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; \
    node /opt/customer-briefing/node_modules/playwright/cli.js install --with-deps chromium --only-shell && \
    apt-get update && apt-get install -y --no-install-recommends \
    curl fonts-dejavu-core poppler-utils \
    && rm -rf /var/lib/apt/lists/*
COPY --from=renderer-build /renderer/dist-mission-export /opt/customer-briefing/assets
COPY frontend/mission-planner/src/mission-export/briefing-render.mjs \
     frontend/mission-planner/src/mission-export/mission-briefing-render.mjs \
     frontend/mission-planner/src/mission-export/briefing-mission-layout.mjs \
     frontend/mission-planner/src/mission-export/briefing-pdf-stage.mjs \
     frontend/mission-planner/src/mission-export/map-stage.mjs \
     frontend/mission-planner/src/mission-export/render-budget.mjs \
     frontend/mission-planner/src/mission-export/render-owner.mjs /opt/customer-briefing/renderer/
COPY frontend/mission-planner/src/mission-export/briefing/document.mjs \
     frontend/mission-planner/src/mission-export/briefing/timeline.mjs \
     frontend/mission-planner/src/mission-export/briefing/pagination.mjs \
     frontend/mission-planner/src/mission-export/briefing/pdf-expectations.mjs \
     frontend/mission-planner/src/mission-export/briefing/briefing.css /opt/customer-briefing/renderer/briefing/
COPY ["backend/starlink-location/app/mission/assets/APO Patch.jpg", "/opt/customer-briefing/APO Patch.jpg"]

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
