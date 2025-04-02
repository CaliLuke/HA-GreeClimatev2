import asyncio
from typing import Any, AsyncGenerator, Awaitable, Callable, Generator, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant

# Assuming climate.py is in custom_components/gree relative to the root
# Adjust the import path if your structure is different
from custom_components.greev2.climate import GreeClimate # Keep entity import
from custom_components.greev2.const import ( # Import constants from const.py
    DEFAULT_PORT,
    DEFAULT_TARGET_TEMP_STEP,
    DEFAULT_TIMEOUT,
    FAN_MODES,
    HVAC_MODES,
    PRESET_MODES,
    SWING_MODES,
    # Add any other constants needed by tests if missing
)

# --- Global Mocks ---
# Mock socket communication to prevent actual network calls
# Apply these globally for all tests collected by pytest in this directory/subdirectories
# Use pytest fixtures for patching where possible for better control, but global patch is okay for now
patch("socket.socket", MagicMock()).start()
patch("Crypto.Cipher.AES", MagicMock()).start()

# --- Constants for Tests ---
MOCK_IP: str = "192.168.1.100"
MOCK_PORT: int = DEFAULT_PORT
MOCK_MAC: str = "a1:b2:c3:d4:e5:f6"
MOCK_NAME: str = "Test Gree AC"

# Type alias for the factory function returned by the fixture
GreeClimateFactory = Callable[..., GreeClimate]

# --- Fixtures ---


@pytest.fixture
async def mock_hass() -> AsyncGenerator[HomeAssistant, None]:
    """Fixture for a basic mock Home Assistant Core object."""
    hass = MagicMock(spec=HomeAssistant)

    # Define a side effect function that executes the passed target function
    async def executor_job_side_effect(target: Callable[..., Any], *args: Any) -> Any:
        # Since update() is synchronous, we just call it.
        # If the target were async, we might need 'await target(*args)'
        # Important: Need to handle potential exceptions within the target
        # If the target raises an error, let it propagate
        # Check if it's a coroutine function or regular function
        if asyncio.iscoroutinefunction(target):
            return await target(*args)
        else:
            return target(*args)

    # Configure the mock to use the side effect
    hass.async_add_executor_job = AsyncMock(side_effect=executor_job_side_effect)

    # --- Mock call_soon_threadsafe to execute the callback ---
    def call_soon_threadsafe_side_effect(
        callback: Callable[..., Any], *args: Any
    ) -> None:
        # Directly call the callback function with its arguments
        # Note: This simplification assumes the callback is thread-safe
        # or that thread-safety isn't critical for these specific tests.
        callback(*args)

    # Mock the loop and call_soon_threadsafe needed by command methods
    hass.loop = MagicMock(spec=asyncio.AbstractEventLoop)  # Spec the loop
    hass.loop.call_soon_threadsafe = MagicMock(
        side_effect=call_soon_threadsafe_side_effect
    )

    # Mock hass.config.units.temperature_unit needed by state update
    hass.config = MagicMock()
    hass.config.units = MagicMock()
    hass.config.units.temperature = (
        UnitOfTemperature.CELSIUS
    )  # Use correct attribute name if changed in HA Core
    hass.config.units.temperature_unit = (
        UnitOfTemperature.CELSIUS
    )  # Keep this if still used

    # Mock hass.data needed by state update - simplify to empty dict
    hass.data = {}

    # Mock hass.states needed by state update
    hass.states = MagicMock()
    # Mock async_set instead of async_set_internal if that's the current HA method
    hass.states.async_set = AsyncMock()
    hass.states.async_set_internal = AsyncMock()  # Keep both if unsure which is used

    # Mock hass.bus for async_track_state_change_event
    hass.bus = MagicMock()
    # async_listen usually returns a callable (the unsubscribe function)
    hass.bus.async_listen = MagicMock(return_value=MagicMock())

    # Mock hass.states.get used in __init__
    hass.states.get = MagicMock(return_value=None)  # Default to returning None

    # Some helpers might check if hass is running
    hass.is_running = True

    # Add other hass methods/attributes if the component uses them
    yield hass  # Use yield for async generator fixture


@pytest.fixture
async def gree_climate_device(mock_hass: HomeAssistant) -> GreeClimateFactory:
    """Fixture factory to create a GreeClimate instance with mock config."""

    def _factory(
        encryption_version: int = 1,
        encryption_key: Optional[str] = None,
        uid: Optional[int] = None,
        horizontal_swing: bool = False,
        # Add other config params here if needed for testing variations
        temp_sensor_entity_id: Optional[str] = None,
        lights_entity_id: Optional[str] = None,
        xfan_entity_id: Optional[str] = None,
        health_entity_id: Optional[str] = None,
        powersave_entity_id: Optional[str] = None,
        sleep_entity_id: Optional[str] = None,
        eightdegheat_entity_id: Optional[str] = None,
        air_entity_id: Optional[str] = None,
        target_temp_entity_id: Optional[str] = None,
        anti_direct_blow_entity_id: Optional[str] = None,
        auto_xfan_entity_id: Optional[str] = None,
        auto_light_entity_id: Optional[str] = None,
        light_sensor_entity_id: Optional[str] = None,
        disable_available_check: bool = False,
        max_online_attempts: int = 3,
    ) -> GreeClimate:
        """Instantiates GreeClimate with specified settings."""
        device = GreeClimate(
            hass=mock_hass,
            name=MOCK_NAME,
            ip_addr=MOCK_IP,
            port=MOCK_PORT,
            mac_addr=MOCK_MAC.encode().replace(b":", b""),
            timeout=DEFAULT_TIMEOUT,
            target_temp_step=DEFAULT_TARGET_TEMP_STEP,
            # Pass through optional entity IDs
            temp_sensor_entity_id=temp_sensor_entity_id,
            lights_entity_id=lights_entity_id,
            xfan_entity_id=xfan_entity_id,
            health_entity_id=health_entity_id,
            powersave_entity_id=powersave_entity_id,
            sleep_entity_id=sleep_entity_id,
            eightdegheat_entity_id=eightdegheat_entity_id,
            air_entity_id=air_entity_id,
            target_temp_entity_id=target_temp_entity_id,
            anti_direct_blow_entity_id=anti_direct_blow_entity_id,
            hvac_modes=HVAC_MODES,
            fan_modes=FAN_MODES,
            swing_modes=SWING_MODES,
            preset_modes=PRESET_MODES,
            auto_xfan_entity_id=auto_xfan_entity_id,
            auto_light_entity_id=auto_light_entity_id,
            horizontal_swing=horizontal_swing,
            light_sensor_entity_id=light_sensor_entity_id,
            encryption_version=encryption_version,
            disable_available_check=disable_available_check,
            max_online_attempts=max_online_attempts,
            encryption_key=encryption_key,
            uid=uid,
        )
        # Assign hass after init if needed, common pattern in HA tests
        # device.hass = mock_hass # Already assigned in __init__

        # Set a unique ID if your tests rely on it
        # device.entity_id = f"climate.test_gree_ac_{encryption_version}" # entity_id is usually set by HA core

        # Initialize potentially checked attributes to avoid errors in tests
        # Set default values that would normally be set after first update/check
        # These are already initialized in GreeClimate.__init__ now
        # device._has_temp_sensor = None
        # device._has_anti_direct_blow = None
        # device._has_light_sensor = None
        return device

    return _factory
