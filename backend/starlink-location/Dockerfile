# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Install curl for health checks and runtime essentials
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security before copying dependencies into its home.
# COPY --chown avoids a slow recursive chown over the installed Python package tree.
RUN useradd -m -u 1000 appuser

# Copy Python dependencies from builder with final ownership already set
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# Copy application code and configuration with final ownership already set
COPY --chown=appuser:appuser main.py .
COPY --chown=appuser:appuser config.yaml .
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser tests/ ./tests/

# Create data/cache directories with proper permissions without walking the dependency tree
RUN mkdir -p /data/routes /data/sim_routes /home/appuser/.local/share/cartopy /home/appuser/.config/matplotlib /home/appuser/.cache/matplotlib && \
    chown appuser:appuser /data /data/routes /data/sim_routes /home/appuser/.local/share/cartopy /home/appuser/.config /home/appuser/.config/matplotlib /home/appuser/.cache /home/appuser/.cache/matplotlib && \
    chmod 755 /data /data/routes /data/sim_routes /home/appuser/.local /home/appuser/.local/share /home/appuser/.local/share/cartopy /home/appuser/.config /home/appuser/.config/matplotlib /home/appuser/.cache /home/appuser/.cache/matplotlib

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
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
