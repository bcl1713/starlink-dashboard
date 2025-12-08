"""Configuration management and loading system."""

# FR-004: File exceeds 300 lines (305 lines) because config management handles
# environment variable loading, YAML parsing, validation, and cached config state.
# Splitting would fragment configuration lifecycle. Deferred to v0.4.0.

import os
from pathlib import Path
from typing import Optional, Any

import yaml
from pydantic import ValidationError

from app.models.config import SimulationConfig


def _override_from_env(config_dict: dict) -> dict:
    """
    Apply environment variable overrides to configuration.

    Environment variables follow the pattern: STARLINK_<SECTION>_<KEY>=value
    Examples:
        STARLINK_MODE=live
        STARLINK_UPDATE_INTERVAL_SECONDS=2.0
        STARLINK_ROUTE_LATITUDE_START=51.5074
        STARLINK_NETWORK_LATENCY_MIN_MS=15.0

    Backward Compatibility:
        SIMULATION_MODE=false is equivalent to STARLINK_MODE=live
        SIMULATION_MODE=true is equivalent to STARLINK_MODE=simulation
    """
    env_prefix = "STARLINK_"

    # Handle SIMULATION_MODE for backward compatibility
    # This takes precedence if STARLINK_MODE is not explicitly set
    simulation_mode = os.getenv("SIMULATION_MODE", "").lower()
    if simulation_mode and "STARLINK_MODE" not in os.environ:
        if simulation_mode in ("false", "0", "no", "off"):
            config_dict["mode"] = "live"
        elif simulation_mode in ("true", "1", "yes", "on"):
            config_dict["mode"] = "simulation"

    for env_key, env_value in os.environ.items():
        if not env_key.startswith(env_prefix):
            continue

        # Remove prefix and convert to lowercase
        config_key = env_key[len(env_prefix) :].lower()

        # Handle nested keys (e.g., ROUTE_LATITUDE_START -> route.latitude_start)
        if "_" in config_key:
            # Try to find which section this belongs to
            parts = config_key.split("_", 1)
            section = parts[0]
            key = None

            # Check for multi-word sections (e.g. heading_tracker) using longest prefix matching
            # This ensures that STARLINK_HEADING_TRACKER_ENABLED maps to heading_tracker.enabled
            # rather than heading.tracker_enabled (if "heading" happened to be a section).
            # Sort by length descending to match longest prefix first
            candidate_sections = [
                k for k, v in config_dict.items() if isinstance(v, dict)
            ]
            candidate_sections.sort(key=len, reverse=True)

            for known_section in candidate_sections:
                if config_key.startswith(f"{known_section}_"):
                    section = known_section
                    key = config_key[len(known_section) + 1 :]
                    break
            else:
                # Fallback to simple split if no section matched
                if len(parts) > 1:
                    key = parts[1]

            if section and key is not None and section in config_dict:
                # Convert value to appropriate type
                value = _convert_env_value(env_value)
                config_dict[section][key] = value
            else:
                # Top-level key
                value = _convert_env_value(env_value)
                config_dict[config_key] = value
        else:
            # Top-level key
            value = _convert_env_value(env_value)
            config_dict[config_key] = value

    return config_dict


def _convert_env_value(value: str) -> Any:
    """
    Convert environment variable string to appropriate Python type.

    Supports: bool, float, int, string
    """
    # Boolean
    if value.lower() in ("true", "yes", "1", "on"):
        return True
    if value.lower() in ("false", "no", "0", "off"):
        return False

    # Try float
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        # Return as string
        return value


class ConfigManager:
    """Manager for loading and validating configuration."""

    _instance: Optional["ConfigManager"] = None
    _config: Optional[SimulationConfig] = None

    def __new__(cls) -> "ConfigManager":
        """Implement singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls) -> "ConfigManager":
        """Get singleton instance."""
        return cls()

    @staticmethod
    def get_config_path() -> Path:
        """
        Get the configuration file path.

        Checks environment variable STARLINK_CONFIG first,
        then looks for config.yaml in the current directory.
        """
        if config_env := os.getenv("STARLINK_CONFIG"):
            return Path(config_env)

        # Look for config.yaml in current working directory
        default_path = Path("config.yaml")
        if default_path.exists():
            return default_path

        # Look in backend/starlink-location directory
        backend_path = Path(__file__).parent.parent.parent / "config.yaml"
        if backend_path.exists():
            return backend_path

        # Fall back to default path even if it doesn't exist
        return default_path

    @staticmethod
    def load_from_file(file_path: Path) -> SimulationConfig:
        """
        Load configuration from YAML file with environment variable overrides.

        Args:
            file_path: Path to the YAML configuration file

        Returns:
            SimulationConfig instance

        Raises:
            FileNotFoundError: If file doesn't exist
            yaml.YAMLError: If YAML is invalid
            ValidationError: If configuration is invalid
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        try:
            with open(file_path, "r") as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Failed to parse YAML configuration: {e}")

        # Ensure nested dicts exist for section overrides
        for section in [
            "route",
            "network",
            "obstruction",
            "position",
            "heading_tracker",
        ]:
            if section not in data:
                data[section] = {}

        # Apply environment variable overrides
        data = _override_from_env(data)

        try:
            return SimulationConfig(**data)
        except ValidationError as e:
            raise ValidationError.from_exception_data(
                title="SimulationConfig",
                line_errors=[
                    {
                        "type": "value_error",
                        "loc": ("config",),
                        "msg": f"Configuration validation failed: {e}",
                    }
                ],
            )

    @staticmethod
    def load_from_dict(data: dict) -> SimulationConfig:
        """
        Load configuration from dictionary with environment variable overrides.

        Args:
            data: Configuration dictionary

        Returns:
            SimulationConfig instance

        Raises:
            ValidationError: If configuration is invalid
        """
        # Ensure nested dicts exist for section overrides
        for section in [
            "route",
            "network",
            "obstruction",
            "position",
            "heading_tracker",
        ]:
            if section not in data:
                data[section] = {}

        # Apply environment variable overrides
        data = _override_from_env(data)

        try:
            return SimulationConfig(**data)
        except ValidationError as e:
            raise ValidationError.from_exception_data(
                title="SimulationConfig",
                line_errors=[
                    {
                        "type": "value_error",
                        "loc": ("config",),
                        "msg": f"Configuration validation failed: {e}",
                    }
                ],
            )

    def load(self, file_path: Optional[Path] = None) -> SimulationConfig:
        """
        Load configuration from file or create default.

        Args:
            file_path: Path to YAML file. If None, uses get_config_path()

        Returns:
            SimulationConfig instance
        """
        if self._config is not None:
            return self._config

        file_path = file_path or self.get_config_path()

        try:
            self._config = self.load_from_file(file_path)
        except FileNotFoundError:
            # Use default configuration if file not found
            self._config = SimulationConfig()

        return self._config

    def get_config(self) -> SimulationConfig:
        """
        Get current configuration, loading if necessary.

        Returns:
            SimulationConfig instance
        """
        if self._config is None:
            self.load()
        return self._config

    def reload(self, file_path: Optional[Path] = None) -> SimulationConfig:
        """
        Reload configuration from file.

        Args:
            file_path: Path to YAML file. If None, uses get_config_path()

        Returns:
            SimulationConfig instance
        """
        self._config = None
        return self.load(file_path)

    def update_config(self, updates: dict) -> SimulationConfig:
        """
        Update current configuration with new values.

        Args:
            updates: Dictionary of configuration updates

        Returns:
            Updated SimulationConfig instance
        """
        current = self.get_config()
        config_dict = current.model_dump()
        config_dict.update(updates)
        self._config = SimulationConfig(**config_dict)
        return self._config

    @classmethod
    def reset(cls) -> None:
        """Reset singleton instance and cached configuration."""
        cls._instance = None
        cls._config = None
