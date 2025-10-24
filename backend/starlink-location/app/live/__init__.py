"""Live Starlink terminal integration module.

This module provides real-time data collection from Starlink dishes via gRPC.
"""

from app.live.client import StarlinkClient

__all__ = ["StarlinkClient"]
