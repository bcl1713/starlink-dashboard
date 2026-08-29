"""KML file validation."""

from pathlib import Path


class KMLParseError(Exception):
    """Raised when KML parsing fails."""


def validate_kml_file(file_path: str | Path) -> tuple[bool, str | None]:
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
    except (
        RuntimeError,
        ValueError,
        OSError,
        KeyError,
        TypeError,
        AttributeError,
        LookupError,
        ConnectionError,
        TimeoutError,
        ImportError,
        EOFError,
    ) as e:
        return False, f"Unexpected error: {e}"
