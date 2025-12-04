"""ETA calculation service with speed smoothing and dual-mode support."""

from app.services.eta.calculator import ETACalculator
from app.services.eta.projection import ETAProjection

# Export the main calculator class
__all__ = ["ETACalculator", "ETAProjection"]
