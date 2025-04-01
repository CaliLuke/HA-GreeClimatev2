from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant

# Assuming climate.py is in custom_components/gree relative to the root
# Adjust the import path if your structure is different
from custom_components.greev2.climate import (DEFAULT_PORT,
                                            DEFAULT_TARGET_TEMP_STEP,
                                            DEFAULT_TIMEOUT, FAN_MODES,
                                            HVAC_MODES, PRESET_MODES,
                                            SWING_MODES, GreeClimate)

# --- Global Mocks ---
# Mock socket communication to prevent actual network calls
# Apply these globally for all tests collected by pytest in this directory/subdirectories
patch("socket.socket", MagicMock()).start()
patch("Crypto.Cipher.AES", MagicMock()).start()

# --- Constants for Tests ---
MOCK_IP = "192.168.1.100"
MOCK_PORT = DEFAULT_PORT
MOCK_MAC = "a1:b2:c3:d4:e5:f6"
MOCK_NAME = "Test Gree AC"

# --- Fixtures ---


@pytest.fixture
async def mock_hass() -> HomeAssistant:
    """Fixture for a basic mock Home Assistant Core object."""
    hass = MagicMock(spec=HomeAssistant)

    # Define a side effect function that executes the passed target function
    async def executor_job_side_effect(target, *args):
        # Since update() is synchronous, we just call it.
        # If the target were async, we might need 'await target(*args)'
        # Important: Need to handle potential exceptions within the target
        # If the target raises an error, let it propagate
        return target(*args)

    # Configure the mock to use the side effect
    hass.async_add_executor_job = AsyncMock(side_effect=executor_job_side_effect)

    # --- Mock call_soon_threadsafe to execute the callback ---
    def call_soon_threadsafe_side_effect(callback, *args):
        # Directly call the callback function with its arguments
        # Note: This simplification assumes the callback is thread-safe
        # or that thread-safety isn't critical for these specific tests.
        callback(*args)

    # Mock the loop and call_soon_threadsafe needed by command methods
    hass.loop = MagicMock()
    hass.loop.call_soon_threadsafe = MagicMock(
        side_effect=call_soon_threadsafe_side_effect
    )

    # Mock hass.config.units.temperature_unit needed by state update
    hass.config = MagicMock()
    hass.config.units = MagicMock()
    hass.config.units.temperature_unit = UnitOfTemperature.CELSIUS

    # Mock hass.data needed by state update - simplify to empty dict
    hass.data = {}

    # Mock hass.states needed by state update
    hass.states = MagicMock()
    hass.states.async_set_internal = AsyncMock()

    # Add other hass methods/attributes if the component uses them
    return hass


@pytest.fixture
async def gree_climate_device(mock_hass: HomeAssistant):
    """Fixture factory to create a GreeClimate instance with mock config."""

    def _factory(
        encryption_version: int = 1,
        encryption_key: str | None = None,
        uid: int | None = None,
        horizontal_swing: bool = False,
        # Add other config params here if needed for testing variations
    ) -> GreeClimate:
        """Instantiates GreeClimate with specified encryption settings."""
        device = GreeClimate(
            hass=mock_hass,
            name=MOCK_NAME,
            ip_addr=MOCK_IP,
            port=MOCK_PORT,
            mac_addr=MOCK_MAC.encode().replace(b":", b""),
            timeout=DEFAULT_TIMEOUT,
            target_temp_step=DEFAULT_TARGET_TEMP_STEP,
            # Provide None or mock values for all the optional entity IDs
            temp_sensor_entity_id=None,
            lights_entity_id=None,
            xfan_entity_id=None,
            health_entity_id=None,
            powersave_entity_id=None,
            sleep_entity_id=None,
            eightdegheat_entity_id=None,
            air_entity_id=None,
            target_temp_entity_id=None,
            anti_direct_blow_entity_id=None,
            hvac_modes=HVAC_MODES,
            fan_modes=FAN_MODES,
            swing_modes=SWING_MODES,
            preset_modes=PRESET_MODES,
            auto_xfan_entity_id=None,
            auto_light_entity_id=None,
            horizontal_swing=horizontal_swing,
            light_sensor_entity_id=None,
            encryption_version=encryption_version,
            disable_available_check=False,
            max_online_attempts=3,
            encryption_key=encryption_key,
            uid=uid,
        )
        # Assign hass after init if needed, common pattern in HA tests
        device.hass = mock_hass
        # Set a unique ID if your tests rely on it
        device.entity_id = (
            f"climate.test_gree_ac_{encryption_version}"  # Make unique ID dependent?
        )
        # Initialize potentially checked attributes to avoid errors in tests
        # Set default values that would normally be set after first update/check
        device._has_temp_sensor = None  # Let tests control this if needed
        device._has_anti_direct_blow = None
        device._has_light_sensor = None
        return device

    return _factory
