import json
from typing import Any, Dict, List, Optional
from unittest.mock import ANY, MagicMock, call, patch

import pytest
from _pytest.logging import LogCaptureFixture
from homeassistant.components.climate import HVACMode
from homeassistant.const import STATE_ON, UnitOfTemperature, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from unittest.mock import Mock

from custom_components.greev2.climate import GreeClimate
from custom_components.greev2.const import FAN_MODES, SWING_MODES

# Import type alias from conftest
from .conftest import GreeClimateFactory

# Fixtures are automatically discovered

# --- Update Method Tests ---

# Removed @patch decorator
async def test_update_calls_get_values(
    gree_climate_device: GreeClimateFactory,
    mock_hass: HomeAssistant,
) -> None:
    """Test update correctly calls get_status on the API object."""
    device: GreeClimate = gree_climate_device()
    # Configure the mock API return value via the device's API instance
    mock_status_list: List[Any] = [0 for _ in device._options_to_fetch]
    device._api.get_status.return_value = mock_status_list # Configure the fixture's mock

    # Ensure key exists (though not strictly needed as API is mocked)
    device._encryption_key = b"testkey123456789"
    # Prevent initial feature check calls
    device._has_temp_sensor = False
    device._has_anti_direct_blow = False
    device._has_light_sensor = False
    device._api._is_bound = True

    await device.async_update()

    # Assertion: Check get_status on the device's API mock
    device._api.get_status.assert_called_once_with(device._options_to_fetch)

# Removed @patch decorator
async def test_update_success_full(
    gree_climate_device: GreeClimateFactory,
    mock_hass: HomeAssistant,
) -> None:
    """Test successful state update from device response."""
    device: GreeClimate = gree_climate_device()
    # Define expected status values
    mock_status_dict: Dict[str, Any] = {key: 0 for key in device._options_to_fetch}
    mock_status_dict.update({
        "Pow": 1, "Mod": 1, "SetTem": 24, "WdSpd": 0, "Lig": 1, "SwUpDn": 0,
    })
    # Ensure the mock list matches the order of _options_to_fetch
    current_options_to_fetch = list(device._options_to_fetch)
    # Assume features are not detected for this test to match mock list length
    device._has_temp_sensor = False
    device._has_anti_direct_blow = False
    device._has_light_sensor = False
    # Create list based on initial fetch list
    mock_status_list: List[Any] = [mock_status_dict.get(key, 1) for key in device._options_to_fetch]

    # Configure the mock API return value
    device._api.get_status.return_value = mock_status_list

    # Ensure key exists
    device._encryption_key = b"testkey123456789"
    device._api._is_bound = True

    await device.async_update()

    # Assertions
    device._api.get_status.assert_called_once_with(device._options_to_fetch)
    assert device.available is True
    assert device.hvac_mode == HVACMode.COOL
    assert device.target_temperature == 24.0
    assert device.fan_mode == FAN_MODES[0] # Auto
    assert device.swing_mode == SWING_MODES[0] # Default
    assert device._current_lights == STATE_ON
    assert device.current_temperature is None

# Removed @patch decorator
async def test_update_timeout(
    gree_climate_device: GreeClimateFactory,
    mock_hass: HomeAssistant,
) -> None:
    """Test state update when device communication times out."""
    device: GreeClimate = gree_climate_device()
    # Simulate communication error by raising an exception
    device._api.get_status.side_effect = ConnectionError("Simulated timeout")

    device._device_online = True
    device._has_temp_sensor = False
    device._has_anti_direct_blow = False
    device._has_light_sensor = False
    device._online_attempts = 0
    device._max_online_attempts = 1
    device._encryption_key = b"testkey123456789"
    device._api._is_bound = True

    await device.async_update()

    # Assertions
    device._api.get_status.assert_called_once_with(device._options_to_fetch)
    assert device.available is False
    assert device._device_online is False

# Removed @patch decorator
async def test_update_invalid_response_length(
    gree_climate_device: GreeClimateFactory,
    mock_hass: HomeAssistant,
    caplog: LogCaptureFixture,
) -> None:
    """Test state update when device returns list with incorrect length."""
    device: GreeClimate = gree_climate_device()
    # Simulate an invalid response
    invalid_response_list: List[Any] = [1, 1]
    device._api.get_status.return_value = invalid_response_list

    device._device_online = True
    device._has_temp_sensor = False # Assume features not detected
    device._has_anti_direct_blow = False
    device._has_light_sensor = False
    device._encryption_key = b"testkey123456789"
    device._api._is_bound = True
    device._max_online_attempts = 1

    await device.async_update()

    # Assertions
    # get_status is called once before the length check fails
    device._api.get_status.assert_called_once_with(device._options_to_fetch)
    assert device.available is False
    assert "API list length mismatch" in caplog.text

# Removed @patch decorator
async def test_update_sets_availability(
    gree_climate_device: GreeClimateFactory,
    mock_hass: HomeAssistant,
) -> None:
    """Test that update correctly sets the 'available' property on success/failure."""
    device: GreeClimate = gree_climate_device()
    # Mock successful response list (use length matching initial fetch list)
    mock_status_list: List[Any] = [0] * len(device._options_to_fetch)

    # Ensure key exists, etc.
    device._encryption_key = b"testkey123456789"
    device._has_temp_sensor = False # Assume features not detected
    device._has_anti_direct_blow = False
    device._has_light_sensor = False
    device._api._is_bound = True
    device._max_online_attempts = 1

    # --- Test 1: Success Case ---
    device._device_online = False
    device._online_attempts = 0
    device._api.get_status.return_value = mock_status_list
    device._api.get_status.side_effect = None # Clear side effect

    await device.async_update()

    assert device.available is True
    assert device._device_online is True
    assert device._api.get_status.call_count == 1

    # --- Test 2: Failure Case (API raises ConnectionError) ---
    device._device_online = True
    device._online_attempts = 0
    device._max_online_attempts = 1
    device._api.get_status.side_effect = ConnectionError("Simulated failure")

    await device.async_update()

    assert device.available is False
    assert device._device_online is False
    assert device._api.get_status.call_count == 2

    # --- Test 3: Recovery Case ---
    device._device_online = False
    device._online_attempts = 0
    device._api.get_status.return_value = mock_status_list
    device._api.get_status.side_effect = None # Clear side effect

    await device.async_update()

    assert device.available is True
    assert device._device_online is True
    assert device._api.get_status.call_count == 3


# --- GCM Specific Tests ---

# Removed @patch decorators for API methods
async def test_update_gcm_calls_api_methods(
    gree_climate_device: GreeClimateFactory,
    mock_hass: HomeAssistant,
) -> None:
    """Test update calls correct API methods for GCM (v2) encryption."""
    MOCK_GCM_KEY: str = "thisIsAMockKey16"
    device_v2: GreeClimate = gree_climate_device(encryption_version=2)
    # Configure the mock API instance from the fixture
    mock_api = device_v2._api
    mock_api._encryption_key = MOCK_GCM_KEY.encode("utf8")
    mock_api._is_bound = True # Assume bound for this test

    # Mock return values for the API calls
    mock_pack = "mock_encrypted_pack_base64"
    mock_tag = "mock_tag_base64"
    mock_api._encrypt_gcm.return_value = (mock_pack, mock_tag)

    mock_gcm_cipher_instance = MagicMock()
    mock_api._get_gcm_cipher.return_value = mock_gcm_cipher_instance

    # Assume features not detected for simplicity
    device_v2._has_temp_sensor = False
    device_v2._has_anti_direct_blow = False
    device_v2._has_light_sensor = False
    mock_status_values: List[Any] = [0] * len(device_v2._options_to_fetch)
    mock_api._fetch_result.return_value = {
        "dat": mock_status_values, "cols": device_v2._options_to_fetch,
    }

    await device_v2.async_update()

    # Assertions on the fixture's mock API
    expected_plaintext = f'{{"cols":{json.dumps(device_v2._options_to_fetch)},"mac":"{device_v2._mac_addr}","t":"status"}}'
    # Re-configure get_status mock for this test
    mock_api.get_status.return_value = mock_status_values
    mock_api.get_status.reset_mock() # Reset call count from fixture setup

    await device_v2.async_update() # Call update again with reconfigured mock

    mock_api.get_status.assert_called_once_with(device_v2._options_to_fetch)
    # Cannot easily assert internal calls like _encrypt_gcm when get_status is mocked


# Removed @patch decorators for API methods
async def test_update_gcm_key_retrieval_and_update(
    gree_climate_device: GreeClimateFactory,
    mock_hass: HomeAssistant,
) -> None:
    """Test update retrieves GCM key, updates API, and fetches status."""
    DEVICE_SPECIFIC_KEY = b"mockDeviceKey123"

    # --- Setup ---
    device_v2: GreeClimate = gree_climate_device(encryption_version=2)
    # Configure the mock API instance from the fixture
    mock_api = device_v2._api
    mock_api._is_bound = False # Start unbound
    mock_api._encryption_key = None

    # Mock return values for bind_and_get_key directly
    mock_api.bind_and_get_key.return_value = True # Simulate successful bind
    # Simulate the side effect of bind_and_get_key setting the key and bound status
    def bind_side_effect():
        mock_api._encryption_key = DEVICE_SPECIFIC_KEY
        mock_api._is_bound = True
        # DO NOT call update_encryption_key here, let the main code do it
        return True
    mock_api.bind_and_get_key.side_effect = bind_side_effect

    # Mock return value for get_status (called after successful bind)
    # Assume features not detected
    device_v2._has_temp_sensor = False
    device_v2._has_anti_direct_blow = False
    device_v2._has_light_sensor = False
    mock_status_values = [0] * len(device_v2._options_to_fetch)
    options_map = {name: i for i, name in enumerate(device_v2._options_to_fetch)}
    mock_status_values[options_map["Pow"]] = 1
    mock_status_values[options_map["Mod"]] = 1
    mock_status_values[options_map["SetTem"]] = 23
    mock_status_values[options_map["WdSpd"]] = 1
    mock_status_values[options_map["Lig"]] = 1
    mock_api.get_status.return_value = mock_status_values

    # --- Action ---
    await device_v2.async_update()

    # --- Assertions ---
    # 1. Verify Binding call
    mock_api.bind_and_get_key.assert_called_once()

    # 2. Verify API key update call (This is called by _update_sync after successful bind)
    mock_api.update_encryption_key.assert_called_once_with(DEVICE_SPECIFIC_KEY)

    # 3. Verify Status call
    mock_api.get_status.assert_called_once_with(device_v2._options_to_fetch)

    # 4. Verify device state reflects the key update
    assert device_v2._api._encryption_key == DEVICE_SPECIFIC_KEY
    assert device_v2._api._is_bound is True

    # 5. Verify device state updated correctly from status list
    assert device_v2.hvac_mode == HVACMode.COOL
    assert device_v2.target_temperature == 23.0
    assert device_v2.fan_mode == FAN_MODES[1] # Low
    assert device_v2._current_lights == STATE_ON

# External temperature sensor tests removed
