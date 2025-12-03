"""KML file validation."""

from pathlib import Path
from typing import Optional


class KMLParseError(Exception):
    """Raised when KML parsing fails."""

    pass


def validate_kml_file(file_path: str | Path) -> tuple[bool, Optional[str]]:
    """
    Validate a KML file without fully parsing it.

    Args:
        file_path: Path to KML file

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Import here to avoid circular dependency
    from app.services.kml.parser import parse_kml_file

    try:
        parse_kml_file(file_path)
        return True, None
    except KMLParseError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Unexpected error: {e}"
