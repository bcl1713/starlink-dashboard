"""Tests for configuration loading and validation."""

import os
import pytest
import tempfile
import yaml
from pathlib import Path

from app.core.config import ConfigManager, _override_from_env, _convert_env_value
from app.models.config import SimulationConfig, HeadingTrackerConfig


class TestEnvValueConversion:
    """Test environment variable value conversion."""

    def test_convert_bool_true(self):
        """Test converting 'true' to boolean."""
        assert _convert_env_value("true") is True
        assert _convert_env_value("yes") is True
        assert _convert_env_value("1") is True
        assert _convert_env_value("on") is True

    def test_convert_bool_false(self):
        """Test converting 'false' to boolean."""
        assert _convert_env_value("false") is False
        assert _convert_env_value("no") is False
        assert _convert_env_value("0") is False
        assert _convert_env_value("off") is False

    def test_convert_integer(self):
        """Test converting string to integer."""
        assert _convert_env_value("42") == 42
        assert _convert_env_value("-10") == -10

    def test_convert_float(self):
        """Test converting string to float."""
        assert _convert_env_value("3.14") == 3.14
        assert _convert_env_value("-2.5") == -2.5

    def test_convert_string(self):
        """Test keeping string as string."""
        assert _convert_env_value("hello") == "hello"
        assert _convert_env_value("simulation") == "simulation"


class TestConfigLoading:
    """Test configuration loading from file."""

    def test_load_from_file(self, default_config):
        """Test loading configuration from YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(default_config.model_dump(), f)
            temp_path = Path(f.name)

        try:
            config = ConfigManager.load_from_file(temp_path)
            assert config.mode == "simulation"
            assert config.route.pattern == "circular"
            assert config.network.latency_typical_ms == 50.0
        finally:
            temp_path.unlink()

    def test_load_from_nonexistent_file(self):
        """Test loading from nonexistent file raises error."""
        with pytest.raises(FileNotFoundError):
            ConfigManager.load_from_file(Path("/nonexistent/path.yaml"))

    def test_load_from_dict(self, default_config):
        """Test loading configuration from dictionary."""
        config_dict = default_config.model_dump()
        config = ConfigManager.load_from_dict(config_dict)
        assert config.mode == "simulation"
        assert config.route.latitude_start == 40.7128

    def test_load_from_dict_with_env_override(self, default_config):
        """Test loading with environment variable overrides."""
        # Set environment variables
        os.environ["STARLINK_MODE"] = "live"
        os.environ["STARLINK_NETWORK_LATENCY_MIN_MS"] = "15.0"

        try:
            config_dict = default_config.model_dump()
            config = ConfigManager.load_from_dict(config_dict)
            assert config.mode == "live"
            assert config.network.latency_min_ms == 15.0
        finally:
            del os.environ["STARLINK_MODE"]
            del os.environ["STARLINK_NETWORK_LATENCY_MIN_MS"]


class TestConfigValidation:
    """Test configuration validation."""

    def test_invalid_radius_negative(self):
        """Test that negative radius raises validation error."""
        with pytest.raises(Exception):  # ValidationError
            SimulationConfig(
                route={"radius_km": -50.0}
            )

    def test_invalid_latency_spike_probability(self):
        """Test that invalid spike probability raises error."""
        with pytest.raises(Exception):  # ValidationError
            SimulationConfig(
                network={"spike_probability": 1.5}
            )

    def test_invalid_packet_loss_percent(self):
        """Test that invalid packet loss percentage raises error."""
        with pytest.raises(Exception):  # ValidationError
            SimulationConfig(
                network={"packet_loss_max_percent": 150.0}
            )

    def test_invalid_update_interval(self):
        """Test that invalid update interval raises error."""
        with pytest.raises(Exception):  # ValidationError
            SimulationConfig(
                update_interval_seconds=-1.0
            )


class TestConfigManager:
    """Test ConfigManager singleton."""

    def test_singleton_pattern(self):
        """Test that ConfigManager is a singleton."""
        manager1 = ConfigManager()
        manager2 = ConfigManager()
        assert manager1 is manager2

    def test_load_creates_default_on_missing(self):
        """Test that loading with missing file creates default config."""
        manager = ConfigManager()
        # This should not raise, should create default
        config = manager.load(Path("/nonexistent/config.yaml"))
        assert config is not None
        assert config.mode == "simulation"

    def test_reload_resets_config(self, default_config):
        """Test that reload resets cached config."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(default_config.model_dump(), f)
            temp_path = Path(f.name)

        try:
            manager = ConfigManager()
            config1 = manager.load(temp_path)
            config1_id = id(config1)

            config2 = manager.reload(temp_path)
            config2_id = id(config2)

            # Should be different object instances
            assert config1_id != config2_id
        finally:
            temp_path.unlink()

    def test_update_config(self, default_config):
        """Test updating configuration."""
        manager = ConfigManager()
        manager.load()

        new_config = SimulationConfig(
            mode="live",
            route=default_config.route
        )
        updated = manager.update_config({"mode": "live"})
        assert updated.mode == "live"

    def test_reset(self):
        """Test resetting ConfigManager singleton."""
        ConfigManager.reset()
        manager1 = ConfigManager()
        config1 = manager1.load()

        ConfigManager.reset()
        manager2 = ConfigManager()
        config2 = manager2.load()

        # Different instances
        assert manager1 is not manager2


class TestHeadingTrackerConfig:
    """Test HeadingTrackerConfig model."""

    def test_default_values(self):
        """Test default values for HeadingTrackerConfig."""
        config = HeadingTrackerConfig()
        assert config.min_distance_meters == 10.0
        assert config.max_age_seconds == 30.0

    def test_custom_values(self):
        """Test creating HeadingTrackerConfig with custom values."""
        config = HeadingTrackerConfig(
            min_distance_meters=25.0,
            max_age_seconds=60.0
        )
        assert config.min_distance_meters == 25.0
        assert config.max_age_seconds == 60.0

    def test_invalid_negative_distance(self):
        """Test that negative distance raises validation error."""
        with pytest.raises(Exception):  # ValidationError
            HeadingTrackerConfig(min_distance_meters=-10.0)

    def test_invalid_zero_distance(self):
        """Test that zero distance raises validation error."""
        with pytest.raises(Exception):  # ValidationError
            HeadingTrackerConfig(min_distance_meters=0.0)

    def test_invalid_negative_age(self):
        """Test that negative max age raises validation error."""
        with pytest.raises(Exception):  # ValidationError
            HeadingTrackerConfig(max_age_seconds=-5.0)

    def test_invalid_zero_age(self):
        """Test that zero max age raises validation error."""
        with pytest.raises(Exception):  # ValidationError
            HeadingTrackerConfig(max_age_seconds=0.0)

    def test_heading_tracker_in_simulation_config(self):
        """Test that SimulationConfig includes heading_tracker."""
        config = SimulationConfig()
        assert hasattr(config, 'heading_tracker')
        assert isinstance(config.heading_tracker, HeadingTrackerConfig)
        assert config.heading_tracker.min_distance_meters == 10.0
        assert config.heading_tracker.max_age_seconds == 30.0

    def test_heading_tracker_custom_in_simulation_config(self):
        """Test SimulationConfig with custom heading tracker."""
        config = SimulationConfig(
            heading_tracker={
                "min_distance_meters": 50.0,
                "max_age_seconds": 120.0
            }
        )
        assert config.heading_tracker.min_distance_meters == 50.0
        assert config.heading_tracker.max_age_seconds == 120.0

    def test_heading_tracker_from_env_override(self):
        """Test loading heading tracker config from environment variables."""
        os.environ["STARLINK_HEADING_TRACKER_MIN_DISTANCE_METERS"] = "15.5"
        os.environ["STARLINK_HEADING_TRACKER_MAX_AGE_SECONDS"] = "45.0"

        try:
            config = ConfigManager.load_from_dict({})
            assert config.heading_tracker.min_distance_meters == 15.5
            assert config.heading_tracker.max_age_seconds == 45.0
        finally:
            del os.environ["STARLINK_HEADING_TRACKER_MIN_DISTANCE_METERS"]
            del os.environ["STARLINK_HEADING_TRACKER_MAX_AGE_SECONDS"]

    def test_heading_tracker_from_yaml(self):
        """Test loading heading tracker config from YAML file."""
        config_data = {
            "mode": "simulation",
            "heading_tracker": {
                "min_distance_meters": 20.0,
                "max_age_seconds": 90.0
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = Path(f.name)

        try:
            config = ConfigManager.load_from_file(temp_path)
            assert config.heading_tracker.min_distance_meters == 20.0
            assert config.heading_tracker.max_age_seconds == 90.0
        finally:
            temp_path.unlink()

    def test_heading_tracker_yaml_with_env_override(self):
        """Test YAML config with environment variable override."""
        config_data = {
            "heading_tracker": {
                "min_distance_meters": 10.0,
                "max_age_seconds": 30.0
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = Path(f.name)

        os.environ["STARLINK_HEADING_TRACKER_MIN_DISTANCE_METERS"] = "25.0"

        try:
            config = ConfigManager.load_from_file(temp_path)
            # Environment override should take precedence
            assert config.heading_tracker.min_distance_meters == 25.0
            # YAML value should be used for max_age_seconds
            assert config.heading_tracker.max_age_seconds == 30.0
        finally:
            temp_path.unlink()
            del os.environ["STARLINK_HEADING_TRACKER_MIN_DISTANCE_METERS"]
