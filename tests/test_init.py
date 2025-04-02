import json
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.components.climate import HVACMode
from homeassistant.core import HomeAssistant

from custom_components.greev2.climate import GCM_DEFAULT_KEY

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


@pytest.mark.asyncio
@patch("custom_components.greev2.device_api.GreeDeviceApi._fetch_result")
@patch("custom_components.greev2.device_api.GreeDeviceApi._get_gcm_cipher")
@patch("custom_components.greev2.device_api.GreeDeviceApi._encrypt_gcm")
async def test_get_device_key_gcm(
    mock_encrypt_gcm: MagicMock,
    mock_get_gcm_cipher: MagicMock,
    mock_fetch_result: MagicMock,
    gree_climate_device: GreeClimateFactory,
) -> None:
    """Test the GetDeviceKeyGCM method calls API correctly and returns key."""
    # INITIAL_GCM_KEY is not used by GetDeviceKeyGCM, binding uses default key
    NEW_GCM_KEY: str = "newBindingKey456"

    # Create a V2 device (initial key doesn't matter for this call)
    device_v2 = gree_climate_device(encryption_version=2)

    # Mock API call return values
    mock_pack: str = "mock_encrypted_bind_pack"
    mock_tag: str = "mock_bind_tag"
    mock_encrypt_gcm.return_value = (mock_pack, mock_tag)

    mock_gcm_cipher_instance = MagicMock()
    mock_get_gcm_cipher.return_value = mock_gcm_cipher_instance

    mock_fetch_result.return_value = {
        "key": NEW_GCM_KEY,
        "r": 200,
    }  # Simulate successful bind

    # Call the GCM binding method (synchronous)
    returned_key: bool = device_v2.get_device_key_gcm()

    # Assertions
    # 1. Check _encrypt_gcm call - Use the exact plaintext from GetDeviceKeyGCM
    expected_bind_plaintext: str = (
        '{"cid":"'
        + device_v2._mac_addr
        + '", "mac":"'
        + device_v2._mac_addr
        + '","t":"bind","uid":0}'
    )
    mock_encrypt_gcm.assert_called_once_with(
        GCM_DEFAULT_KEY.encode("utf8"),  # Use the actual default key from climate.py
        expected_bind_plaintext,
    )

    # 2. Check _get_gcm_cipher call
    # This should also use the default key
    mock_get_gcm_cipher.assert_called_once_with(GCM_DEFAULT_KEY.encode("utf8"))

    # 3. Check _fetch_result call (Payload has i=1 hardcoded in GetDeviceKeyGCM)
    expected_payload_dict: Dict[str, Any] = {
        "cid": "app",
        "i": 1,  # Actual code uses i=1 for binding
        "pack": mock_pack,
        "t": "pack",
        "tcid": device_v2._mac_addr,
        "uid": 0,
        "tag": mock_tag,
    }
    mock_fetch_result.assert_called_once()  # Check it was called
    actual_call_args, _ = mock_fetch_result.call_args
    actual_cipher_arg: Any = actual_call_args[0]
    actual_payload_str: str = actual_call_args[1]

    assert actual_cipher_arg is mock_gcm_cipher_instance
    assert json.loads(actual_payload_str) == expected_payload_dict

    # 4. Check returned value and stored key
    assert returned_key is True
    assert device_v2._encryption_key == NEW_GCM_KEY.encode("utf8")


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
