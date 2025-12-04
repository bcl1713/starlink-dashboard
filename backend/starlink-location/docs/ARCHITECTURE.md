# Backend Architecture

[Back to Backend README](../README.md)

---

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

---

## Key Metrics

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

---

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

---

## Performance

- Response times: < 50ms for most endpoints
- Memory usage: ~100-150 MB
- CPU usage: < 5% at rest
- Background update loop: 10 Hz (0.1s per cycle)
- Prometheus scrape interval: 1s

---

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

---

[Back to Backend README](../README.md)
