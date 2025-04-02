import asyncio
from typing import Any, AsyncGenerator, Awaitable, Callable, Generator, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
# Need format_mac for mock entry unique_id
from homeassistant.helpers.device_registry import format_mac

# Assuming climate.py is in custom_components/gree relative to the root
from custom_components.greev2.climate import GreeClimate
from custom_components.greev2.const import (
    DEFAULT_PORT,
    DEFAULT_TARGET_TEMP_STEP, # Keep if needed elsewhere, but not for fixture
    DEFAULT_TIMEOUT, # Keep if needed elsewhere, but not for fixture
    FAN_MODES, # Keep if needed elsewhere, but not for fixture
    HVAC_MODES, # Keep if needed elsewhere, but not for fixture
    PRESET_MODES, # Keep if needed elsewhere, but not for fixture
    SWING_MODES, # Keep if needed elsewhere, but not for fixture
    # Import constants needed for mock config entry data
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_ENCRYPTION_VERSION,
)

# --- Global Mocks ---
patch("Crypto.Cipher.AES", MagicMock()).start()

# --- Constants for Tests ---
MOCK_IP: str = "192.168.1.100"
MOCK_PORT: int = DEFAULT_PORT # Keep for potential direct API tests
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

    def call_soon_threadsafe_side_effect(callback: Callable[..., Any], *args: Any) -> None:
        callback(*args)
    hass.loop = MagicMock(spec=asyncio.AbstractEventLoop)
    hass.loop.call_soon_threadsafe = MagicMock(side_effect=call_soon_threadsafe_side_effect)

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
        encryption_version: int = 2, # Default to V2 as per config flow
        # Add other config entry data fields here if needed for tests
    ) -> GreeClimate:
        """Instantiates GreeClimate using a mock ConfigEntry."""
        # Create mock ConfigEntry
        mock_entry = MagicMock(spec=config_entries.ConfigEntry)
        mock_entry.entry_id = "mock_entry_123" # Example entry ID
        # Format MAC address for unique ID consistency
        formatted_mac = format_mac(mac)
        mock_entry.unique_id = f"climate.gree_{formatted_mac}"
        mock_entry.data = {
            CONF_HOST: host,
            CONF_MAC: mac, # Store original MAC format in data
            CONF_NAME: name,
            CONF_ENCRYPTION_VERSION: str(encryption_version), # Store as string like in config flow
            # Add other data fields if the component expects them from the entry
        }
        # Mock options if needed for future tests
        mock_entry.options = {}

        # Instantiate the device using the new __init__ signature
        # Patch the API during instantiation for most tests
        # Removed autospec=True to avoid InvalidSpecError
        with patch("custom_components.greev2.climate.GreeDeviceApi") as mock_api_class:
            # Configure the mock instance returned by the API class constructor
            mock_api_instance = mock_api_class.return_value
            mock_api_instance._is_bound = True # Assume bound by default for most tests
            mock_api_instance.bind_and_get_key.return_value = True # Simulate successful bind
            # Configure the mock get_status *method* to return the default list
            # Length 21 = 18 base + 3 potential features (TemSen, AntiDirectBlow, LigSen)
            mock_api_instance.get_status.return_value = [1] * 21
            # Explicitly set the encryption version on the mock API instance
            mock_api_instance._encryption_version = encryption_version
            # Explicitly set the encryption key to None initially
            mock_api_instance._encryption_key = None
            # Explicitly configure the _cipher attribute to be None
            mock_api_instance.configure_mock(_cipher=None)

            device = GreeClimate(hass=mock_hass, entry=mock_entry)
            # Assign the mock API instance to the device for inspection if needed
            device._api = mock_api_instance

        return device

    return _factory
