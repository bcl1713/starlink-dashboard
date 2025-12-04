# Starlink Location Backend

A FastAPI-based Prometheus metrics exporter and telemetry API for simulating
Starlink dish positioning, network performance, and environmental conditions.
Includes realistic physics-based simulators for position tracking, network
metrics, and obstruction detection.

## Features

- **Simulation Mode**: Generates realistic Starlink telemetry data
- **Prometheus Metrics**: Exports metrics in Prometheus format (1-second scrape
  interval)
- **REST API**: JSON telemetry endpoints and configuration management
- **Structured Logging**: JSON-formatted logs for monitoring and debugging
- **Health Checks**: Built-in health monitoring and uptime tracking
- **Configuration Management**: Runtime configuration updates via API or
  environment variables
- **Graceful Degradation**: Returns last known good values on errors
- **Background Updates**: Continuous telemetry generation at 10 Hz

## Quick Start

### Using Docker Compose

```bash
# Build and start all services
docker compose up -d

# Verify services are running
docker compose ps

# Check backend health
curl <http://localhost:8000/health>

# View metrics
curl <http://localhost:8000/metrics> | head -20

# Get status
curl <http://localhost:8000/api/status> | jq .

# Access Prometheus
open <http://localhost:9090>

# Access Grafana
open <http://localhost:3000>  # admin/admin
```

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run with uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000

# Or with auto-reload
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Environment Variables

### Application Configuration

```bash
# Logging
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR, CRITICAL
JSON_LOGS=true                    # Use JSON format for logs
LOG_FILE=/var/log/starlink.log   # Optional log file path

# Simulation configuration (via STARLINK_* prefix)
STARLINK_MODE=simulation          # simulation or live
STARLINK_UPDATE_INTERVAL_SECONDS=1.0

# Route configuration
STARLINK_ROUTE_PATTERN=circular   # circular or straight
STARLINK_ROUTE_LATITUDE_START=40.7128
STARLINK_ROUTE_LONGITUDE_START=-74.0060
STARLINK_ROUTE_RADIUS_KM=100.0

# Network configuration
STARLINK_NETWORK_LATENCY_MIN_MS=20.0
STARLINK_NETWORK_LATENCY_TYPICAL_MS=50.0
STARLINK_NETWORK_LATENCY_MAX_MS=80.0

# Obstruction configuration
STARLINK_OBSTRUCTION_MIN_PERCENT=0.0
STARLINK_OBSTRUCTION_MAX_PERCENT=30.0
STARLINK_OBSTRUCTION_VARIATION_RATE=0.5

# Position configuration
STARLINK_POSITION_SPEED_MIN_KNOTS=0.0
STARLINK_POSITION_SPEED_MAX_KNOTS=100.0
STARLINK_POSITION_ALTITUDE_MIN_METERS=100.0
STARLINK_POSITION_ALTITUDE_MAX_METERS=10000.0
```

### Configuration File

Default configuration is loaded from `config.yaml`:

```yaml
mode: simulation
update_interval_seconds: 1.0

route:
  pattern: circular
  latitude_start: 40.7128
  longitude_start: -74.0060
  radius_km: 100.0
  distance_km: 500.0

network:
  latency_min_ms: 20.0
  latency_typical_ms: 50.0
  latency_max_ms: 80.0
  latency_spike_max_ms: 200.0
  spike_probability: 0.05
  throughput_down_min_mbps: 50.0
  throughput_down_max_mbps: 200.0
  throughput_up_min_mbps: 10.0
  throughput_up_max_mbps: 40.0
  packet_loss_min_percent: 0.0
  packet_loss_max_percent: 5.0

obstruction:
  min_percent: 0.0
  max_percent: 30.0
  variation_rate: 0.5

position:
  speed_min_knots: 0.0
  speed_max_knots: 100.0
  altitude_min_meters: 100.0
  altitude_max_meters: 10000.0
  heading_variation_rate: 5.0
```

## API Endpoints

### `/` - Root

Returns welcome message and API documentation links.

```bash
curl <http://localhost:8000/>
```

### `/health` - Health Check

Returns service status, uptime, and mode information.

```bash
curl <http://localhost:8000/health>
```

Response:

```json
{
  "status": "ok",
  "uptime_seconds": 123.45,
  "mode": "simulation",
  "version": "0.2.0",
  "timestamp": "2024-10-23T16:30:00.000000"
}
```

### `/metrics` - Prometheus Metrics

Returns metrics in Prometheus format. Compatible with Prometheus scraping.

```bash
curl <http://localhost:8000/metrics>
```

Available metrics:

- Position: `starlink_dish_latitude_degrees`, `starlink_dish_longitude_degrees`,
  `starlink_dish_altitude_meters`, `starlink_dish_speed_knots`,
  `starlink_dish_heading_degrees`
- Network: `starlink_network_latency_ms`,
  `starlink_network_throughput_down_mbps`,
  `starlink_network_throughput_up_mbps`, `starlink_network_packet_loss_percent`
- Status: `starlink_dish_obstruction_percent`,
  `starlink_signal_quality_percent`, `starlink_uptime_seconds`,
  `starlink_service_info`
- Counters: `simulation_updates_total`, `simulation_errors_total`

### `/api/status` - Current Status (JSON)

Returns current telemetry with human-readable fields and ISO 8601 timestamp.

```bash
curl <http://localhost:8000/api/status>
```

Response:

```json
{
  "timestamp": "2024-10-23T16:30:00.000000",
  "position": {
    "latitude": 40.7128,
    "longitude": -74.006,
    "altitude": 5000.0,
    "speed": 25.5,
    "heading": 45.0
  },
  "network": {
    "latency_ms": 45.2,
    "throughput_down_mbps": 125.3,
    "throughput_up_mbps": 25.1,
    "packet_loss_percent": 0.5
  },
  "obstruction": {
    "obstruction_percent": 15.0
  },
  "environmental": {
    "signal_quality_percent": 85.0,
    "uptime_seconds": 3600.5,
    "temperature_celsius": null
  }
}
```

### `/api/config` - Configuration Management

#### GET - Retrieve Configuration

```bash
curl <http://localhost:8000/api/config>
```

#### POST/PUT - Update Configuration

```bash
curl -X POST <http://localhost:8000/api/config> \
  -H "Content-Type: application/json" \
  -d @config.json
```

## Metrics

### Position Metrics

- `starlink_dish_latitude_degrees` - Current dish latitude
- `starlink_dish_longitude_degrees` - Current dish longitude
- `starlink_dish_altitude_meters` - Current dish altitude
- `starlink_dish_speed_knots` - Current movement speed
- `starlink_dish_heading_degrees` - Current heading (0=North, 90=East)

### Network Metrics

- `starlink_network_latency_ms` - Round-trip latency with occasional spikes
- `starlink_network_throughput_down_mbps` - Download throughput (50-200 Mbps)
- `starlink_network_throughput_up_mbps` - Upload throughput (10-40 Mbps)
- `starlink_network_packet_loss_percent` - Packet loss percentage (0-5%)

### Obstruction & Signal Metrics

- `starlink_dish_obstruction_percent` - Obstruction percentage (0-100%)
- `starlink_signal_quality_percent` - Signal quality (0-100%, inverse of
  obstruction)

### Status Metrics

- `starlink_service_info{version="0.2.0", mode="simulation"}` - Service
  information
- `starlink_uptime_seconds` - Service uptime

### Counters

- `simulation_updates_total` - Total simulation updates executed
- `simulation_errors_total` - Total simulation errors encountered

## Simulation Behavior

### Position Simulation

- Follows a circular or straight route
- Speed varies realistically (0-100 knots)
- Heading changes smoothly
- Altitude varies between configured min/max

### Network Simulation

- Latency: 20-80ms typical, occasional spikes to 200ms (5% probability)
- Download: 50-200 Mbps with random variation
- Upload: 10-40 Mbps with slower variation
- Packet loss: 0-5% with smooth changes

### Obstruction Simulation

- Varies 0-30% by default
- Correlates with network latency (higher latency → higher obstruction)
- Smooth time-based variation

## Testing

### Unit Tests

```bash
pytest tests/unit/ -v
```

Tests included for:

- Configuration loading and validation
- Route generation (circular and straight)
- Position simulator
- Network simulator
- Obstruction simulator
- Prometheus metrics

### Integration Tests

```bash
pytest tests/integration/ -v
```

Tests included for:

- Health endpoint
- Metrics endpoint
- Status endpoint
- Configuration API
- End-to-end simulation

### Run All Tests with Coverage

```bash
pytest tests/ --cov=app --cov-report=html
```

## Docker

### Build

```bash
docker build -t starlink-location:0.2.0 .
```

### Run

```bash
docker run -p 8000:8000 -e STARLINK_MODE=simulation starlink-location:0.2.0
```

### Health Check

Built-in health check pings `/health` endpoint every 30 seconds.

## Logging

Structured JSON logging with context fields:

```json
{
  "timestamp": "2024-10-23T16:30:00.000000",
  "level": "INFO",
  "logger": "app.simulation.coordinator",
  "message": "Simulation coordinator initialized",
  "uptime_seconds": 0.1
}
```

Configure via environment:

- `LOG_LEVEL`: DEBUG, INFO, WARNING, ERROR, CRITICAL
- `JSON_LOGS`: true/false (default: true)
- `LOG_FILE`: Optional file path

## Performance

- Response times: < 50ms for most endpoints
- Memory usage: ~100-150 MB
- CPU usage: < 5% at rest
- Background update loop: 10 Hz (0.1s per cycle)
- Prometheus scrape interval: 1s

## Project Structure

```text
backend/starlink-location/
├── main.py                 # FastAPI application entry point
├── config.yaml             # Default configuration
├── requirements.txt        # Python dependencies
├── Dockerfile              # Docker build configuration
├── pytest.ini              # Pytest configuration
├── app/
│   ├── api/
│   │   ├── health.py      # Health check endpoint
│   │   ├── metrics.py     # Prometheus metrics endpoint
│   │   ├── status.py      # JSON status endpoint
│   │   └── config.py      # Configuration API endpoint
│   ├── core/
│   │   ├── config.py      # Configuration management
│   │   ├── logging.py     # Structured logging
│   │   └── metrics.py     # Prometheus metrics definitions
│   ├── models/
│   │   ├── config.py      # Configuration Pydantic models
│   │   └── telemetry.py   # Telemetry Pydantic models
│   └── simulation/
│       ├── route.py       # Route generation
│       ├── position.py    # Position simulator
│       ├── network.py     # Network simulator
│       ├── obstructions.py # Obstruction simulator
│       └── coordinator.py # Simulation orchestrator
└── tests/
    ├── conftest.py        # Pytest fixtures
    ├── unit/              # Unit tests
    └── integration/       # Integration tests
```

## Documentation

- `VALIDATION.md` - Detailed validation guide and testing procedures
- `design-document.md` - Architecture and design details (parent project)
- `phased-development-plan.md` - Implementation phases (parent project)

## Troubleshooting

### Port Already in Use

```bash
lsof -i :8000
kill -9 <PID>
```

### Configuration Not Loading

```bash
# Check config file path
ls -la config.yaml

# Test with environment variable
STARLINK_MODE=live uvicorn main:app --host 0.0.0.0 --port 8000
```

### Metrics Not Updating

```bash
# Check logs for background update errors
docker compose logs starlink-location | grep -i error

# Verify health endpoint
curl <http://localhost:8000/health>
```

## Contributing

When making changes:

1. Update tests in `tests/`
2. Ensure all tests pass: `pytest tests/`
3. Run with coverage: `pytest tests/ --cov=app`
4. Update this README if adding features

## License

Part of the Starlink Dashboard project.
