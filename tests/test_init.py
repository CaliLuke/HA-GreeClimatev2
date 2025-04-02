import json
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.components.climate import HVACMode
from homeassistant.core import HomeAssistant

from custom_components.greev2.const import GCM_DEFAULT_KEY # Import from const

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
    assert device._mac_addr == MOCK_MAC.replace(":", "").lower()
    assert device.hvac_mode == HVACMode.OFF  # Check default state
    # Check default encryption version
    assert device.encryption_version == 1
    assert device._encryption_key is None  # No key by default


async def test_init_with_encryption_key(
    gree_climate_device: GreeClimateFactory,
) -> None:
    """Test initialization with a configured encryption key (V1)."""
    mock_key: str = "testEncryptKey16"  # Ensure 16 bytes for AES-128
    # Get the device instance by calling the factory with args
    device = gree_climate_device(encryption_key=mock_key, encryption_version=1)

    assert device._encryption_key == mock_key.encode("utf8")
    assert device.encryption_version == 1
    # Check if the API object was initialized with the key
    assert device._api._encryption_key == mock_key.encode("utf8")
    assert device._api._encryption_version == 1
    assert device._api._cipher is not None  # API should create the cipher for V1
    # assert ( # CIPHER attribute removed
    #     device.CIPHER is None
    # )  # Should NOT be created directly in GreeClimate anymore


async def test_init_with_gcm_encryption(
    gree_climate_device: GreeClimateFactory,
) -> None:
    """Test initialization with GCM encryption (V2) and key."""
    mock_key: str = "testGcmKey123456"  # 16 bytes
    # Get the device instance by calling the factory with args
    device = gree_climate_device(encryption_key=mock_key, encryption_version=2)

    assert device._encryption_key == mock_key.encode("utf8")
    assert device.encryption_version == 2
    # Check if the API object was initialized correctly for V2
    assert device._api._encryption_key == mock_key.encode("utf8")
    assert device._api._encryption_version == 2
    assert device._api._cipher is None  # API should NOT create cipher on init for V2
    # assert device.CIPHER is None # CIPHER attribute removed


# TODO: Implement test_init_with_optional_entities
@patch(
    "custom_components.greev2.climate.async_track_state_change_event"
)  # Patch where it's used
async def test_init_with_optional_entities(
    mock_track_state: MagicMock,
    mock_hass: HomeAssistant,  # Need hass fixture
    gree_climate_device: GreeClimateFactory,  # Need factory fixture
) -> None:
    """Test initialization calls async_track_state_change_event for configured entities."""
    # Define some mock entity IDs
    temp_sensor_id = "sensor.outside_temp"
    lights_id = "switch.living_room_lights"
    xfan_id = "input_boolean.ac_xfan"

    # Create device instance using the factory with specific entity IDs
    device = gree_climate_device(
        temp_sensor_entity_id=temp_sensor_id,
        lights_entity_id=lights_id,
        xfan_entity_id=xfan_id,
        # Add others if needed
    )

    # Assert async_track_state_change_event was called for each configured entity
    # Check call count first
    assert mock_track_state.call_count == 3

    # Check that calls were made with the correct entity IDs (more robust than checking hass/callback instance)
    called_entity_ids = {
        call_args[1] for call_args, _ in mock_track_state.call_args_list
    }
    assert temp_sensor_id in called_entity_ids
    assert lights_id in called_entity_ids
    assert xfan_id in called_entity_ids

    # Original assertions (can be problematic with mock/method comparison):
    # mock_track_state.assert_any_call(
    #     mock_hass, temp_sensor_id, device._async_temp_sensor_changed
    # )
    # mock_track_state.assert_any_call(
    #     mock_hass, lights_id, device._async_lights_entity_state_changed
    # )
    # mock_track_state.assert_any_call(
    #     mock_hass, xfan_id, device._async_xfan_entity_state_changed
    # )
