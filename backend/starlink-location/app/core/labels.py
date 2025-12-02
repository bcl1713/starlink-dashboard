"""Label helper functions for Prometheus metrics."""


def get_mode_label(config) -> str:
    """
    Get the operation mode label.

    Args:
        config: ConfigManager instance with mode attribute

    Returns:
        str: "simulation" or "live"
    """
    return config.mode


def get_status_label(latency_ms: float, packet_loss_percent: float) -> str:
    """
    Get the connection status label based on network performance.

    Status levels are determined by latency and packet loss thresholds:
    - excellent: latency < 50ms AND packet_loss < 1%
    - good: latency < 100ms AND packet_loss < 5%
    - degraded: latency < 150ms OR packet_loss < 10%
    - poor: anything else (high latency or high packet loss)

    Args:
        latency_ms: Network latency in milliseconds
        packet_loss_percent: Packet loss percentage (0-100)

    Returns:
        str: One of "excellent", "good", "degraded", "poor"
    """
    if latency_ms < 50 and packet_loss_percent < 1:
        return "excellent"
    elif latency_ms < 100 and packet_loss_percent < 5:
        return "good"
    elif latency_ms < 150 and packet_loss_percent < 10:
        return "degraded"
    else:
        return "poor"


def get_geographic_labels(latitude: float, longitude: float) -> dict:
    """
    Get geographic region and zone labels based on coordinates.

    This is a stub implementation for future enhancement. Currently returns
    generic labels. Can be extended to support:
    - Regional classifications (Americas, Europe, Asia, etc.)
    - Zone classifications based on latitude/longitude ranges
    - Integration with actual geographic data service

    Args:
        latitude: Dish latitude in decimal degrees (-90 to 90)
        longitude: Dish longitude in decimal degrees (-180 to 180)

    Returns:
        dict: Contains 'region' and 'zone' label values
    """
    # Stub implementation - can be enhanced with actual geographic data
    region = "unknown"
    zone = "unknown"

    # Simple hemisphere-based classification for now
    if latitude >= 0:
        hemisphere = "north"
    else:
        hemisphere = "south"

    if longitude >= 0:
        meridian = "east"
    else:
        meridian = "west"

    region = f"{hemisphere}-{meridian}"
    zone = f"lat:{latitude:.1f},lon:{longitude:.1f}"

    return {"region": region, "zone": zone}


def apply_common_labels(telemetry, config) -> dict:
    """
    Apply all applicable labels for a metric based on telemetry and config.

    This helper computes all relevant labels in one place for consistency.

    Args:
        telemetry: TelemetryData instance with position, network data
        config: ConfigManager instance with mode information

    Returns:
        dict: Dictionary of label names and values, e.g.:
              {
                  "mode": "simulation",
                  "status": "good",
                  "region": "north-west",
                  "zone": "lat:40.5,lon:-120.3"
              }
    """
    mode = get_mode_label(config)
    status = get_status_label(
        telemetry.network.latency_ms, telemetry.network.packet_loss_percent
    )
    geo_labels = get_geographic_labels(
        telemetry.position.latitude, telemetry.position.longitude
    )

    return {
        "mode": mode,
        "status": status,
        "region": geo_labels["region"],
        "zone": geo_labels["zone"],
    }
