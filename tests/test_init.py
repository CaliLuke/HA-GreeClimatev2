# import json # Removed unused
# from typing import Any, Dict # Removed unused
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.components.climate import HVACMode
from homeassistant.core import HomeAssistant

# from custom_components.greev2.const import GCM_DEFAULT_KEY  # Removed unused import

# Import MOCK constants from conftest using absolute path relative to tests dir
# No longer needed if using fixtures properly
# from tests.conftest import MOCK_IP, MOCK_MAC, MOCK_NAME, MOCK_PORT
from .conftest import (  # Use relative import for type alias
    GreeClimateFactory,
    MOCK_IP,
    MOCK_MAC,
    MOCK_NAME,
    MOCK_PORT,
)

# Fixtures (mock_hass, gree_climate_device) are automatically discovered from conftest.py

# --- Initialization Tests ---


async def test_init_minimal_config(gree_climate_device: GreeClimateFactory) -> None:
    """Test initialization with minimal configuration."""
    # Get the device instance by calling the factory
    device = gree_climate_device()
    # Basic checks after fixture instantiation
    assert device is not None
    assert device.name == MOCK_NAME
    assert device._ip_addr == MOCK_IP
    assert device._port == MOCK_PORT
    # Check MAC address format (should have colons now due to format_mac)
    assert device._mac_addr == MOCK_MAC.lower()
    assert device.hvac_mode == HVACMode.OFF  # Check default state
    # Check default encryption version (fixture defaults to 2)
    assert device.encryption_version == 2
    assert device._encryption_key is None  # No key by default


async def test_init_with_encryption_key(
    gree_climate_device: GreeClimateFactory,
) -> None:
    """Test initialization with V1 encryption."""
    # Get the device instance by calling the factory with args
    # Encryption key is no longer passed during init, it's retrieved during bind
    device = gree_climate_device(encryption_version=1)

    # Assertions check the version and that the API was configured correctly
    assert device.encryption_version == 1
    assert device._api._encryption_version == 1
    # Key is None initially, API cipher should also be None until bind
    assert device._encryption_key is None
    assert device._api._encryption_key is None
    assert device._api._cipher is None


async def test_init_with_gcm_encryption(
    gree_climate_device: GreeClimateFactory,
) -> None:
    """Test initialization with GCM encryption (V2)."""
    # Get the device instance by calling the factory with args
    # Encryption key is no longer passed during init
    device = gree_climate_device(encryption_version=2)

    # Assertions check the version and that the API was configured correctly
    assert device.encryption_version == 2
    assert device._api._encryption_version == 2
    # Key is None initially
    assert device._encryption_key is None
    assert device._api._encryption_key is None
    assert device._api._cipher is None  # API should NOT create cipher on init for V2


@pytest.mark.skip(reason="Optional entities no longer configured in __init__")
@patch(
    "custom_components.greev2.climate.async_track_state_change_event"
)  # Patch where it's used
async def test_init_with_optional_entities(
    mock_track_state: MagicMock,
    mock_hass: HomeAssistant,  # Need hass fixture
    gree_climate_device: GreeClimateFactory,  # Need factory fixture
) -> None:
    """Test initialization calls async_track_state_change_event for configured entities."""
    # This test is skipped because optional entities are no longer passed in __init__
    # They would need to be configured via an Options Flow, and listeners set up there.
    pass
    # Define some mock entity IDs
    # temp_sensor_id = "sensor.outside_temp"
    # lights_id = "switch.living_room_lights"
    # xfan_id = "input_boolean.ac_xfan"

    # Create device instance using the factory with specific entity IDs
    # device = gree_climate_device(
    #     temp_sensor_entity_id=temp_sensor_id,
    #     lights_entity_id=lights_id,
    #     xfan_entity_id=xfan_id,
    #     # Add others if needed
    # )

    # Assert async_track_state_change_event was called for each configured entity
    # Check call count first
    # assert mock_track_state.call_count == 3

    # Check that calls were made with the correct entity IDs (more robust than checking hass/callback instance)
    # called_entity_ids = {
    #     call_args[1] for call_args, _ in mock_track_state.call_args_list
    # }
    # assert temp_sensor_id in called_entity_ids
    # assert lights_id in called_entity_ids
    # assert xfan_id in called_entity_ids
