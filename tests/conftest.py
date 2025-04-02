import asyncio
from typing import Any, AsyncGenerator, Awaitable, Callable, Generator, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant

# Need format_mac for mock entry unique_id
from homeassistant.helpers.device_registry import format_mac

# Need ClimateEntityFeature for fixture modification
from homeassistant.components.climate import ClimateEntityFeature

# Assuming climate.py is in custom_components/gree relative to the root
from custom_components.greev2.climate import GreeClimate
from custom_components.greev2.const import (
    DEFAULT_PORT,
    DEFAULT_TARGET_TEMP_STEP,  # Keep if needed elsewhere, but not for fixture
    DEFAULT_TIMEOUT,  # Keep if needed elsewhere, but not for fixture
    FAN_MODES,  # Keep if needed elsewhere, but not for fixture
    HVAC_MODES,  # Keep if needed elsewhere, but not for fixture
    PRESET_MODES,  # Keep if needed elsewhere, but not for fixture
    SWING_MODES,  # Keep if needed elsewhere, but not for fixture
    # Import constants needed for mock config entry data
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_ENCRYPTION_VERSION,
    DEFAULT_HORIZONTAL_SWING,  # Import default
)

# --- Global Mocks ---
patch("Crypto.Cipher.AES", MagicMock()).start()

# --- Constants for Tests ---
MOCK_IP: str = "192.168.1.100"
MOCK_PORT: int = DEFAULT_PORT  # Keep for potential direct API tests
MOCK_MAC: str = "a1:b2:c3:d4:e5:f6"
MOCK_NAME: str = "Test Gree AC"

# Type alias for the factory function returned by the fixture
GreeClimateFactory = Callable[..., GreeClimate]

# --- Fixtures ---


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations defined in the test environment."""
    yield


@pytest.fixture
async def mock_hass() -> AsyncGenerator[HomeAssistant, None]:
    """Fixture for a basic mock Home Assistant Core object."""
    hass = MagicMock(spec=HomeAssistant)

    async def executor_job_side_effect(target: Callable[..., Any], *args: Any) -> Any:
        if asyncio.iscoroutinefunction(target):
            return await target(*args)
        else:
            return target(*args)

    hass.async_add_executor_job = AsyncMock(side_effect=executor_job_side_effect)

    def call_soon_threadsafe_side_effect(
        callback: Callable[..., Any], *args: Any
    ) -> None:
        callback(*args)

    hass.loop = MagicMock(spec=asyncio.AbstractEventLoop)
    hass.loop.call_soon_threadsafe = MagicMock(
        side_effect=call_soon_threadsafe_side_effect
    )

    hass.config = MagicMock()
    hass.config.units = MagicMock()
    hass.config.units.temperature = UnitOfTemperature.CELSIUS
    hass.config.units.temperature_unit = UnitOfTemperature.CELSIUS

    hass.data = {}
    hass.states = MagicMock()
    hass.states.async_set = AsyncMock()
    hass.states.async_set_internal = AsyncMock()
    hass.bus = MagicMock()
    hass.bus.async_listen = MagicMock(return_value=MagicMock())
    hass.states.get = MagicMock(return_value=None)
    hass.is_running = True

    yield hass


@pytest.fixture
async def gree_climate_device(mock_hass: HomeAssistant) -> GreeClimateFactory:
    """Fixture factory to create a GreeClimate instance using a mock ConfigEntry."""

    def _factory(
        host: str = MOCK_IP,
        mac: str = MOCK_MAC,
        name: str = MOCK_NAME,
        encryption_version: int = 2,
        horizontal_swing: Optional[bool] = None,  # Added parameter, default None
        # Add other config entry data fields here if needed for tests
    ) -> GreeClimate:
        """Instantiates GreeClimate using a mock ConfigEntry."""
        # Create mock ConfigEntry
        mock_entry = MagicMock(spec=config_entries.ConfigEntry)
        mock_entry.entry_id = "mock_entry_123"
        formatted_mac = format_mac(mac)
        mock_entry.unique_id = f"climate.gree_{formatted_mac}"
        mock_entry.data = {
            CONF_HOST: host,
            CONF_MAC: mac,
            CONF_NAME: name,
            CONF_ENCRYPTION_VERSION: str(encryption_version),
            # NOTE: horizontal_swing is NOT part of config entry data currently
        }
        mock_entry.options = {}

        # Patch the API during instantiation
        with patch("custom_components.greev2.climate.GreeDeviceApi") as mock_api_class:
            mock_api_instance = mock_api_class.return_value
            mock_api_instance._is_bound = True
            mock_api_instance.bind_and_get_key = AsyncMock(return_value=True)
            # Default mock status - adjust in specific tests if needed
            # Use a realistic length based on initial fetch list in climate.py __init__
            initial_fetch_list_len = 20
            mock_api_instance.get_status = AsyncMock(
                return_value=[0] * initial_fetch_list_len
            )
            mock_api_instance._encryption_version = encryption_version
            mock_api_instance._encryption_key = None
            mock_api_instance.configure_mock(_cipher=None)

            # Instantiate the device (uses DEFAULT_HORIZONTAL_SWING internally first)
            device = GreeClimate(hass=mock_hass, entry=mock_entry)
            device._api = mock_api_instance  # Assign mock API

            # Override horizontal_swing if specified by the test AFTER init
            if horizontal_swing is not None:
                device._horizontal_swing = horizontal_swing
                # Update state helper instance as well
                if hasattr(device, "_state"):  # Ensure _state exists
                    device._state._horizontal_swing = horizontal_swing
                # Re-evaluate preset modes based on the override
                if horizontal_swing:
                    device._attr_preset_modes = device._preset_modes_list
                    device._attr_supported_features |= ClimateEntityFeature.PRESET_MODE
                else:
                    device._attr_preset_modes = None
                    # Use bitwise AND NOT to remove the flag safely
                    device._attr_supported_features &= ~ClimateEntityFeature.PRESET_MODE

        return device

    return _factory
