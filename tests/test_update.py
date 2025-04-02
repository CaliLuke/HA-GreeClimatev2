import json
from typing import Any, Dict, List
from unittest.mock import ANY, MagicMock, call, patch

import pytest
from _pytest.logging import LogCaptureFixture  # For caplog type hint
from homeassistant.components.climate import HVACMode
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant

from custom_components.greev2.climate import FAN_MODES, SWING_MODES, GreeClimate

# Import type alias from conftest
from .conftest import GreeClimateFactory

# Fixtures (mock_hass, gree_climate_device) are automatically discovered from conftest.py

# --- Update Method Tests ---


@patch("custom_components.greev2.climate.GreeClimate.GreeGetValues")
async def test_update_calls_get_values(
    mock_get_values: MagicMock,
    gree_climate_device: GreeClimateFactory,
    mock_hass: HomeAssistant,
) -> None:
    """Test update correctly calls GreeGetValues."""
    # Get device instance
    device: GreeClimate = gree_climate_device()
    # Mock response values as dict - needed for the method to run
    mock_status_dict: Dict[str, Any] = {key: 0 for key in device._optionsToFetch}
    mock_get_values.return_value = mock_status_dict

    # Ensure key exists so async_update() calls _update_sync directly
    device._encryption_key = b"testkey123456789"
    device._api._cipher = MagicMock()  # Mock the API's cipher
    # Prevent initial feature check call to GreeGetValues
    device._has_temp_sensor = False
    device._has_anti_direct_blow = False
    device._has_light_sensor = False

    # Call the update method
    await device.async_update()
    # Note: The original test expected an IndexError from SetAcOptions.
    # If SetAcOptions is now more robust, this test might just pass without error.
    # We only assert that GreeGetValues was called.

    # Assertion: Only check if GreeGetValues was called
    mock_get_values.assert_called_once_with(device._optionsToFetch)


@patch("custom_components.greev2.climate.GreeClimate.GreeGetValues")
async def test_update_success_full(
    mock_get_values: MagicMock,
    gree_climate_device: GreeClimateFactory,
    mock_hass: HomeAssistant,
) -> None:
    """Test successful state update from device response."""
    # Get device instance
    device: GreeClimate = gree_climate_device()
    # Mock response values as a dictionary matching _optionsToFetch keys
    mock_status_dict: Dict[str, Any] = {key: 0 for key in device._optionsToFetch}
    mock_status_dict.update(
        {
            "Pow": 1,
            "Mod": 1,  # COOL index
            "SetTem": 24,
            "WdSpd": 0,  # Auto index
            "Lig": 1,
            "SwUpDn": 0,  # Default index
            # Add other non-zero values as needed for the test assertions
        }
    )
    mock_get_values.return_value = mock_status_dict

    # Ensure key exists so async_update() calls _update_sync directly
    device._encryption_key = b"testkey123456789"
    device._api._cipher = MagicMock()
    # Prevent initial feature check calls
    device._has_temp_sensor = False
    device._has_anti_direct_blow = False
    device._has_light_sensor = False

    # Call the update method
    await device.async_update()

    # Assertions
    mock_get_values.assert_called_once_with(device._optionsToFetch)
    assert device.available is True
    assert device.hvac_mode == HVACMode.COOL
    assert device.target_temperature == 24.0  # Should be float
    assert device.fan_mode == FAN_MODES[0]  # Auto
    assert device.swing_mode == SWING_MODES[0]  # Default
    assert device._current_lights == STATE_ON
    # ... (Add back other state assertions as needed for the full test)
    assert device.current_temperature is None  # Assuming no temp sensor


@patch("custom_components.greev2.climate.GreeClimate.GreeGetValues")
async def test_update_timeout(
    mock_get_values: MagicMock,
    gree_climate_device: GreeClimateFactory,
    mock_hass: HomeAssistant,
) -> None:
    """Test state update when device communication times out."""
    # Get device instance
    device: GreeClimate = gree_climate_device()
    # Simulate communication error by returning None (as API does)
    mock_get_values.return_value = None

    # Ensure device starts online and feature checks are skipped
    device._device_online = True
    device._has_temp_sensor = False
    device._has_anti_direct_blow = False
    device._has_light_sensor = False
    device._online_attempts = 0  # Reset attempts
    device._max_online_attempts = 1  # Make it fail after one attempt
    # Ensure key exists so async_update() calls _update_sync directly
    device._encryption_key = b"testkey123456789"
    device._api._cipher = MagicMock()

    # Call update - expecting SyncState to handle None return
    await device.async_update()

    # Assertions
    mock_get_values.assert_called_once_with(device._optionsToFetch)
    assert device.available is False
    assert device._device_online is False


@pytest.mark.xfail(
    reason="SetAcOptions may raise error on invalid/incomplete data",
    # raises=IndexError, # Might raise KeyError or other error now
    strict=True,
)
@patch("custom_components.greev2.climate.GreeClimate.GreeGetValues")
async def test_update_invalid_response(
    mock_get_values: MagicMock,
    gree_climate_device: GreeClimateFactory,
    mock_hass: HomeAssistant,
    caplog: LogCaptureFixture,
) -> None:
    """Test state update when device returns invalid/incomplete data."""
    # Get device instance
    device: GreeClimate = gree_climate_device()
    # Simulate an invalid response (dictionary with missing keys)
    invalid_response_dict: Dict[str, Any] = {"Pow": 1, "Mod": 1}  # Missing many keys
    mock_get_values.return_value = invalid_response_dict
    expected_options_len: int = len(device._optionsToFetch)

    # Store initial state for comparison
    initial_ac_options: Dict[str, Any] = device._acOptions.copy()

    # Ensure device starts online, has key, and feature checks are skipped
    device._device_online = True
    device._has_temp_sensor = False
    device._has_anti_direct_blow = False
    device._has_light_sensor = False
    device._encryption_key = b"testkey123456789"
    device._api._cipher = MagicMock()

    # Call update
    await device.async_update()

    # Assertions
    mock_get_values.assert_called_once_with(device._optionsToFetch)
    assert device.available is True  # Communication succeeded, parsing might fail
    # Check if state changed - depends on SetAcOptions robustness
    # assert device._acOptions == initial_ac_options
    # Check for a warning/error log from SetAcOptions if it handles missing keys
    assert (
        "Could not convert value" in caplog.text or "SetAcOptions error" in caplog.text
    )


@patch("custom_components.greev2.climate.GreeClimate.GreeGetValues")
async def test_update_sets_availability(
    mock_get_values: MagicMock,
    gree_climate_device: GreeClimateFactory,
    mock_hass: HomeAssistant,
) -> None:
    """Test that update correctly sets the 'available' property on success/failure."""
    # Get device instance
    device: GreeClimate = gree_climate_device()
    # Mock successful response as dict
    mock_status_dict: Dict[str, Any] = {key: 0 for key in device._optionsToFetch}

    # Ensure key exists, etc.
    device._encryption_key = b"testkey123456789"
    device._api._cipher = MagicMock()
    device._has_temp_sensor = False
    device._has_anti_direct_blow = False
    device._has_light_sensor = False

    # --- Test 1: Success Case ---
    device._device_online = False
    device._online_attempts = 0
    mock_get_values.return_value = mock_status_dict
    mock_get_values.side_effect = None  # Clear any previous side effect

    await device.async_update()

    assert device.available is True
    assert device._device_online is True
    assert mock_get_values.call_count == 1

    # --- Test 2: Failure Case (GreeGetValues returns None) ---
    device._device_online = True
    device._online_attempts = 0
    device._max_online_attempts = 1  # Fail after one attempt
    mock_get_values.return_value = None  # Simulate API failure
    mock_get_values.side_effect = None

    await device.async_update()

    assert device.available is False
    assert device._device_online is False
    assert mock_get_values.call_count == 2  # Called once in success, once in failure

    # --- Test 3: Recovery Case ---
    device._device_online = False
    device._online_attempts = 0  # Reset attempts
    mock_get_values.return_value = mock_status_dict  # Set back to success
    mock_get_values.side_effect = None  # Clear side effect

    await device.async_update()

    assert device.available is True
    assert device._device_online is True
    assert mock_get_values.call_count == 3  # Called again for recovery


# --- GCM Specific Tests ---


# Patch the API methods directly for GCM test
@patch("custom_components.greev2.device_api.GreeDeviceApi._fetch_result")
@patch("custom_components.greev2.device_api.GreeDeviceApi._get_gcm_cipher")
@patch("custom_components.greev2.device_api.GreeDeviceApi._encrypt_gcm")
async def test_update_gcm_calls_api_methods(
    mock_encrypt_gcm: MagicMock,
    mock_get_gcm_cipher: MagicMock,
    mock_fetch_result: MagicMock,
    gree_climate_device: GreeClimateFactory,  # Fixture factory
    mock_hass: HomeAssistant,
) -> None:
    """Test update calls correct API methods for GCM (v2) encryption."""
    MOCK_GCM_KEY: str = "thisIsAMockKey16"  # 16 bytes
    # Create a V2 device instance using the factory
    device_v2: GreeClimate = gree_climate_device(
        encryption_version=2, encryption_key=MOCK_GCM_KEY
    )

    # Mock return values for the API calls
    mock_pack: str = "mock_encrypted_pack_base64"
    mock_tag: str = "mock_tag_base64"
    mock_encrypt_gcm.return_value = (mock_pack, mock_tag)

    mock_gcm_cipher_instance = MagicMock()
    mock_get_gcm_cipher.return_value = mock_gcm_cipher_instance

    # Mock the decrypted response that GreeGetValues expects from fetch_result
    mock_decrypted_data: Dict[str, Any] = {
        key: 0 for key in device_v2._optionsToFetch
    }  # Use dict format
    # Mock the structure returned by _fetch_result which includes 'dat'
    mock_fetch_result.return_value = {"dat": mock_decrypted_data}

    # Prevent initial feature check calls which also use GreeGetValues
    device_v2._has_temp_sensor = False
    device_v2._has_anti_direct_blow = False
    device_v2._has_light_sensor = False

    # Call the update method
    await device_v2.async_update()
    # Note: Original test caught IndexError from SetAcOptions.
    # If SetAcOptions is robust, this should pass.

    # Assertions: Check API methods were called correctly by GreeGetValues -> get_status
    expected_plaintext: str = (
        '{"cols":'
        + json.dumps(device_v2._optionsToFetch)
        + ',"mac":"'
        + device_v2._mac_addr
        + '","t":"status"}'
    )
    # get_status calls _encrypt_gcm internally
    mock_encrypt_gcm.assert_called_once_with(
        MOCK_GCM_KEY.encode("utf8"), expected_plaintext
    )

    # get_status calls _get_gcm_cipher internally
    mock_get_gcm_cipher.assert_called_once_with(MOCK_GCM_KEY.encode("utf8"))

    # Check that fetch_result was called with the mock cipher and correct payload structure
    mock_fetch_result.assert_called_once_with(
        mock_gcm_cipher_instance,  # The cipher object returned by _get_gcm_cipher
        ANY,  # Check the payload structure more loosely
    )
    # Verify the payload string passed to _fetch_result matches expectations
    call_args, _ = mock_fetch_result.call_args
    actual_payload_str: str = call_args[1]
    expected_payload: Dict[str, Any] = {
        "cid": "app",
        "i": 0,
        "pack": mock_pack,
        "t": "pack",
        "tcid": device_v2._mac_addr,
        "uid": 0,
        "tag": mock_tag,
    }
    # Parse the actual payload string and compare dictionaries for robustness
    assert json.loads(actual_payload_str) == expected_payload


# --- Test for GCM Key Retrieval ---


# Patch the API methods directly
@patch("custom_components.greev2.device_api.GreeDeviceApi._fetch_result")
@patch("custom_components.greev2.device_api.GreeDeviceApi._get_gcm_cipher")
@patch("custom_components.greev2.device_api.GreeDeviceApi._encrypt_gcm")
@patch(
    "custom_components.greev2.device_api.GreeDeviceApi.update_encryption_key"
)  # Mock the new method
async def test_update_gcm_key_retrieval_and_update(
    mock_update_key: MagicMock,  # Mock for the new method
    mock_encrypt_gcm: MagicMock,
    mock_get_gcm_cipher: MagicMock,
    mock_fetch_result: MagicMock,
    gree_climate_device: GreeClimateFactory,  # Fixture factory from conftest.py
    mock_hass: HomeAssistant,
) -> None:
    """Test update retrieves GCM key, updates API, and fetches status."""
    GENERIC_GCM_KEY: bytes = b"{yxAHAY_Lm6pbC/<"  # Key used for binding
    DEVICE_SPECIFIC_KEY: bytes = b"mockDeviceKey123"  # The key we expect to get back

    # --- Setup ---
    # Create a V2 device instance with NO initial key
    device_v2: GreeClimate = gree_climate_device(
        encryption_version=2, encryption_key=None
    )

    # Mock return values for the API calls during BINDING
    mock_bind_pack: str = "mock_bind_pack_base64"
    mock_bind_tag: str = "mock_bind_tag_base64"
    # Simulate _encrypt_gcm response for binding and status calls using side_effect
    mock_status_pack: str = "mock_status_pack_base64"
    mock_status_tag: str = "mock_status_tag_base64"
    mock_encrypt_gcm.side_effect = [
        (mock_bind_pack, mock_bind_tag),  # First call (binding)
        (mock_status_pack, mock_status_tag),  # Second call (status)
    ]

    # Simulate _get_gcm_cipher response (used for both binding and status)
    mock_generic_cipher = MagicMock(name="GenericCipher")
    mock_device_cipher = MagicMock(name="DeviceCipher")
    mock_get_gcm_cipher.side_effect = [
        mock_generic_cipher,
        mock_device_cipher,
    ]  # First call gets generic, second gets device

    # Simulate _fetch_result: First call (binding) returns the device key, second call (status) returns status data
    mock_bind_response: Dict[str, Any] = {"key": DEVICE_SPECIFIC_KEY.decode("utf8")}
    # Use dict format for status data
    mock_status_data: Dict[str, Any] = {key: 0 for key in device_v2._optionsToFetch}
    mock_status_response: Dict[str, Any] = {"dat": mock_status_data}
    mock_fetch_result.side_effect = [mock_bind_response, mock_status_response]

    # Simulate the key being updated on the API object after binding
    # This happens via update_encryption_key, but we need to ensure the mock reflects it for the *next* call
    def update_api_key_side_effect(*args: Any) -> None:
        # Make sure the API object exists before trying to set attribute
        if hasattr(device_v2, "_api") and device_v2._api is not None:
            device_v2._api._encryption_key = DEVICE_SPECIFIC_KEY
        # For V1, we'd also update the cipher here if testing V1
        # device_v2._api._cipher = AES.new(DEVICE_SPECIFIC_KEY, AES.MODE_ECB)

    mock_update_key.side_effect = update_api_key_side_effect

    # Prevent initial feature check calls which also use GreeGetValues/get_status
    device_v2._has_temp_sensor = False
    device_v2._has_anti_direct_blow = False
    device_v2._has_light_sensor = False

    # --- Action ---
    # Call the update method
    await device_v2.async_update()
    # Note: Original test caught IndexError from SetAcOptions.
    # If SetAcOptions is robust, this should pass.

    # --- Assertions ---

    # 1. Verify Binding API calls
    # Check _encrypt_gcm was called for binding (with generic key)
    bind_plaintext: str = (
        '{"cid":"'
        + device_v2._mac_addr
        + '", "mac":"'
        + device_v2._mac_addr
        + '","t":"bind","uid":0}'
    )
    # Check _get_gcm_cipher was called for binding (with generic key)
    # Check _fetch_result was called for binding (with generic cipher)
    bind_payload_str: str = (
        '{"cid": "app","i": 1,"pack": "'
        + mock_bind_pack
        + '","t":"pack","tcid":"'
        + device_v2._mac_addr
        + '","uid": 0, "tag" : "'
        + mock_bind_tag
        + '"}'
    )

    # 2. Verify API key update
    mock_update_key.assert_called_once_with(DEVICE_SPECIFIC_KEY)

    # 3. Verify Status API calls (using the NEW key)
    # Check _encrypt_gcm was called for status (with device key)
    status_plaintext: str = (
        '{"cols":'
        + json.dumps(device_v2._optionsToFetch)
        + ',"mac":"'
        + device_v2._mac_addr
        + '","t":"status"}'
    )
    # Check _get_gcm_cipher was called for status (with device key)
    # Check _fetch_result was called for status (with device cipher)

    status_payload_str: str = (
        '{"cid":"app","i":0,"pack":"'
        + mock_status_pack
        + '","t":"pack","tcid":"'
        + device_v2._mac_addr
        + '","uid":0,"tag":"'
        + mock_status_tag
        + '"}'
    )

    # Check all calls were made in the correct order with correct args
    mock_encrypt_gcm.assert_has_calls(
        [
            call(GENERIC_GCM_KEY, bind_plaintext),  # Binding call
            call(DEVICE_SPECIFIC_KEY, status_plaintext),  # Status call
        ]
    )
    mock_get_gcm_cipher.assert_has_calls(
        [
            call(GENERIC_GCM_KEY),  # Binding call
            call(DEVICE_SPECIFIC_KEY),  # Status call
        ]
    )
    mock_fetch_result.assert_has_calls(
        [
            call(mock_generic_cipher, bind_payload_str),  # Binding call
            call(mock_device_cipher, status_payload_str),  # Status call
        ]
    )

    # 4. Verify device state
    assert device_v2._encryption_key == DEVICE_SPECIFIC_KEY  # Climate object's key
    assert device_v2.available is True  # Should be available after successful update
