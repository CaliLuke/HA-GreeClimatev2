# import json # Removed unused
# import socket  # Removed unused
from typing import Any, Dict, List # Removed Optional
from unittest.mock import ANY, MagicMock, patch, AsyncMock  # Removed call

# import pytest # Removed unused
from _pytest.logging import LogCaptureFixture
from homeassistant.components.climate import HVACMode
# Removed unused UnitOfTemperature, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
# from homeassistant.helpers.entity import Entity # Removed unused
# from unittest.mock import Mock # Removed unused

from custom_components.greev2.climate import GreeClimate

# Import detect_features for patching
# from custom_components.greev2.climate_helpers import detect_features # Removed unused
from custom_components.greev2.const import FAN_MODES, SWING_MODES

# Import type alias from conftest
from .conftest import GreeClimateFactory

# Fixtures are automatically discovered

# --- Update Method Tests ---


@patch(
    "custom_components.greev2.climate.detect_features",
    return_value=(False, False, False, []),
)  # Mock feature detection
async def test_update_calls_get_values(
    mock_detect_features: AsyncMock,  # Add mock arg
    gree_climate_device: GreeClimateFactory,
    mock_hass: HomeAssistant, # Keep mock_hass even if unused by test logic, fixture might need it
) -> None:
    """Test update correctly calls get_status on the API object."""
    device: GreeClimate = gree_climate_device()
    initial_options = list(device._options_to_fetch)  # Store initial options
    mock_detect_features.return_value = (
        False,
        False,
        False,
        initial_options,
    )  # Ensure mock returns initial list

    # Configure the mock API return value via the device's API instance
    mock_status_list: List[Any] = [0 for _ in initial_options]
    device._api.get_status = AsyncMock(return_value=mock_status_list)  # type: ignore[method-assign]
    device._api._is_bound = True
    device._api.bind_and_get_key = AsyncMock(return_value=True)  # type: ignore[method-assign]

    await device.async_update()

    # Assertion: Check get_status on the device's API mock
    mock_detect_features.assert_called_once_with(
        device._api, initial_options
    )  # Verify detect_features called
    device._api.get_status.assert_called_once_with(
        initial_options
    )  # Verify get_status called with correct options


@patch(
    "custom_components.greev2.climate.detect_features",
    return_value=(False, False, False, []),
)  # Mock feature detection
async def test_update_success_full(
    mock_detect_features: AsyncMock,  # Add mock arg
    gree_climate_device: GreeClimateFactory,
    mock_hass: HomeAssistant, # Keep mock_hass
) -> None:
    """Test successful state update from device response."""
    device: GreeClimate = gree_climate_device()
    initial_options = list(device._options_to_fetch)  # Store initial options
    mock_detect_features.return_value = (
        False,
        False,
        False,
        initial_options,
    )  # Ensure mock returns initial list

    # Define expected status values based on initial_options
    mock_status_dict: Dict[str, Any] = {key: 0 for key in initial_options}
    mock_status_dict.update(
        {
            "Pow": 1,
            "Mod": 1,
            "SetTem": 24,
            "WdSpd": 0,
            "Lig": 1,
            "SwUpDn": 0,
        }
    )
    mock_status_list: List[Any] = [
        mock_status_dict.get(key, 1) for key in initial_options
    ]

    # Configure the mock API return value
    device._api.get_status = AsyncMock(return_value=mock_status_list)  # type: ignore[method-assign]
    device._api._is_bound = True
    device._api.bind_and_get_key = AsyncMock(return_value=True)  # type: ignore[method-assign]

    await device.async_update()

    # Assertions
    mock_detect_features.assert_called_once_with(
        device._api, ANY
    )  # ANY because initial list is created inside fixture
    device._api.get_status.assert_called_once_with(initial_options)
    assert device.available is True
    assert device.hvac_mode == HVACMode.COOL
    assert device.target_temperature == 24.0
    assert device.fan_mode == FAN_MODES[0]  # Auto
    assert device.swing_mode == SWING_MODES[0]  # Default
    assert device._state.lights_state == STATE_ON  # Check state helper property
    assert device.current_temperature is None  # Internal sensor assumed false by mock


@patch(
    "custom_components.greev2.climate.detect_features",
    return_value=(False, False, False, []),
)  # Mock feature detection
async def test_update_timeout(
    mock_detect_features: AsyncMock,  # Add mock arg
    gree_climate_device: GreeClimateFactory,
    mock_hass: HomeAssistant, # Keep mock_hass
) -> None:
    """Test state update when device communication times out."""
    device: GreeClimate = gree_climate_device()
    initial_options = list(device._options_to_fetch)  # Store initial options
    mock_detect_features.return_value = (
        False,
        False,
        False,
        initial_options,
    )  # Ensure mock returns initial list

    # Simulate communication error by raising an exception
    device._api.get_status = AsyncMock(side_effect=ConnectionError("Simulated timeout"))  # type: ignore[method-assign]

    device._device_online = True
    device._online_attempts = 0
    device._max_online_attempts = 1
    device._api._is_bound = True
    device._api.bind_and_get_key = AsyncMock(return_value=True)  # type: ignore[method-assign]

    await device.async_update()

    # Assertions
    mock_detect_features.assert_called_once_with(device._api, ANY)
    device._api.get_status.assert_called_once_with(initial_options)
    assert device.available is False
    assert device._device_online is False


@patch(
    "custom_components.greev2.climate.detect_features",
    return_value=(False, False, False, []),
)  # Mock feature detection
async def test_update_invalid_response_length(
    mock_detect_features: AsyncMock,  # Add mock arg
    gree_climate_device: GreeClimateFactory,
    mock_hass: HomeAssistant, # Keep mock_hass
    caplog: LogCaptureFixture,
) -> None:
    """Test state update when device returns list with incorrect length."""
    device: GreeClimate = gree_climate_device()
    initial_options = list(device._options_to_fetch)  # Store initial options
    mock_detect_features.return_value = (
        False,
        False,
        False,
        initial_options,
    )  # Ensure mock returns initial list

    # Simulate an invalid response
    invalid_response_list: List[Any] = [1, 1]  # Length doesn't match initial_options
    device._api.get_status = AsyncMock(return_value=invalid_response_list)  # type: ignore[method-assign]

    device._device_online = True
    device._api._is_bound = True
    device._api.bind_and_get_key = AsyncMock(return_value=True)  # type: ignore[method-assign]
    device._max_online_attempts = 1

    await device.async_update()

    # Assertions
    mock_detect_features.assert_called_once_with(device._api, ANY)
    device._api.get_status.assert_called_once_with(initial_options)
    assert device.available is False
    assert "API list length mismatch" in caplog.text
    assert (
        f"Device {device.name} offline after {device._max_online_attempts} attempts."
        in caplog.text
    )


@patch(
    "custom_components.greev2.climate.detect_features",
    return_value=(False, False, False, []),
)  # Mock feature detection
async def test_update_sets_availability(
    mock_detect_features: AsyncMock,  # Add mock arg
    gree_climate_device: GreeClimateFactory,
    mock_hass: HomeAssistant, # Keep mock_hass
) -> None:
    """Test that update correctly sets the 'available' property on success/failure."""
    device: GreeClimate = gree_climate_device()
    initial_options = list(device._options_to_fetch)  # Store initial options
    mock_detect_features.return_value = (
        False,
        False,
        False,
        initial_options,
    )  # Ensure mock returns initial list

    # Mock successful response list
    mock_status_list: List[Any] = [0] * len(initial_options)

    # Ensure key exists, etc.
    device._api._is_bound = True
    device._api.bind_and_get_key = AsyncMock(return_value=True)  # type: ignore[method-assign]
    device._max_online_attempts = 1

    # --- Test 1: Success Case ---
    device._device_online = False
    device._online_attempts = 0
    device._has_temp_sensor = None  # Reset flag to ensure detection runs
    device._api.get_status = AsyncMock(return_value=mock_status_list)  # type: ignore[method-assign]
    device._api.get_status.side_effect = None  # Clear side effect

    await device.async_update()

    assert device.available is True
    assert device._device_online is True
    assert mock_detect_features.call_count == 1  # Called once
    assert device._api.get_status.call_count == 1

    # --- Test 2: Failure Case (API raises ConnectionError) ---
    mock_detect_features.reset_mock()  # Reset mock for next call
    device._api.get_status.reset_mock()
    device._device_online = True
    device._online_attempts = 0
    device._max_online_attempts = 1
    device._has_temp_sensor = None  # FIX: Reset flag to ensure detection runs
    device._api.get_status = AsyncMock(side_effect=ConnectionError("Simulated failure"))  # type: ignore[method-assign]

    await device.async_update()

    assert device.available is False
    assert device._device_online is False
    assert mock_detect_features.call_count == 1  # Called again
    assert device._api.get_status.call_count == 1

    # --- Test 3: Recovery Case ---
    mock_detect_features.reset_mock()
    device._api.get_status.reset_mock()
    device._device_online = False
    device._online_attempts = 0
    device._has_temp_sensor = None  # FIX: Reset flag to ensure detection runs
    device._api.get_status = AsyncMock(
        return_value=mock_status_list
    )  # FIX: Removed unused type ignore
    device._api.get_status.side_effect = None  # Clear side effect

    await device.async_update()

    assert device.available is True
    assert device._device_online is True
    assert mock_detect_features.call_count == 1  # Called again
    assert device._api.get_status.call_count == 1


# --- GCM Specific Tests ---


@patch(
    "custom_components.greev2.climate.detect_features",
    return_value=(False, False, False, []),
)  # Mock feature detection
async def test_update_gcm_calls_api_methods(
    mock_detect_features: AsyncMock,  # Add mock arg
    gree_climate_device: GreeClimateFactory,
    mock_hass: HomeAssistant, # Keep mock_hass
) -> None:
    """Test update calls correct API methods for GCM (v2) encryption. (Simplified)"""
    MOCK_GCM_KEY: str = "thisIsAMockKey16"
    device_v2: GreeClimate = gree_climate_device(encryption_version=2)
    initial_options = list(device_v2._options_to_fetch)  # Store initial options
    mock_detect_features.return_value = (
        False,
        False,
        False,
        initial_options,
    )  # Ensure mock returns initial list

    # Configure the mock API instance from the fixture
    mock_api = device_v2._api
    mock_api._encryption_key = MOCK_GCM_KEY.encode("utf8")
    mock_api._is_bound = True  # Assume bound for this test
    mock_api.bind_and_get_key = AsyncMock(return_value=True)  # type: ignore[method-assign]

    mock_status_values: List[Any] = [0] * len(initial_options)
    mock_api.get_status = AsyncMock(return_value=mock_status_values)  # type: ignore[method-assign]

    await device_v2.async_update()

    # Assertions on the fixture's mock API
    mock_detect_features.assert_called_once_with(mock_api, ANY)
    mock_api.get_status.assert_called_once_with(initial_options)


@patch(
    "custom_components.greev2.climate.detect_features",
    return_value=(False, False, False, []),
)  # Mock feature detection
async def test_update_gcm_key_retrieval_and_update(
    mock_detect_features: AsyncMock,  # Add mock arg
    gree_climate_device: GreeClimateFactory,
    mock_hass: HomeAssistant, # Keep mock_hass
) -> None:
    """Test update retrieves GCM key, updates API, and fetches status."""
    DEVICE_SPECIFIC_KEY = b"mockDeviceKey123"

    # --- Setup ---
    device_v2: GreeClimate = gree_climate_device(encryption_version=2)
    initial_options = list(device_v2._options_to_fetch)  # Store initial options
    mock_detect_features.return_value = (
        False,
        False,
        False,
        initial_options,
    )  # Ensure mock returns initial list

    # Configure the mock API instance from the fixture
    mock_api = device_v2._api
    mock_api._is_bound = False  # Start unbound
    mock_api._encryption_key = None
    mock_api.update_encryption_key = MagicMock()  # type: ignore[method-assign] # FIX: Add ignore

    # Mock return values for bind_and_get_key directly
    mock_api.bind_and_get_key = AsyncMock()  # type: ignore[method-assign]

    async def bind_side_effect_async():  # Make side effect async
        mock_api._encryption_key = DEVICE_SPECIFIC_KEY
        mock_api._is_bound = True
        return True

    mock_api.bind_and_get_key.side_effect = bind_side_effect_async

    # Mock return value for get_status (called after successful bind)
    mock_status_values = [0] * len(initial_options)
    options_map = {name: i for i, name in enumerate(initial_options)}
    mock_status_values[options_map["Pow"]] = 1
    mock_status_values[options_map["Mod"]] = 1
    mock_status_values[options_map["SetTem"]] = 23
    mock_status_values[options_map["WdSpd"]] = 1
    mock_status_values[options_map["Lig"]] = 1
    mock_api.get_status = AsyncMock(return_value=mock_status_values)  # type: ignore[method-assign]

    # --- Action ---
    await device_v2.async_update()

    # --- Assertions ---
    # 1. Verify Binding call
    mock_api.bind_and_get_key.assert_called_once()

    # 2. Verify API key update call
    mock_api.update_encryption_key.assert_called_once_with(DEVICE_SPECIFIC_KEY)

    # 3. Verify detect_features call (happens after bind, before get_status)
    mock_detect_features.assert_called_once_with(mock_api, ANY)

    # 4. Verify Status call
    mock_api.get_status.assert_called_once_with(
        initial_options
    )  # Should use initial options list

    # 5. Verify device state reflects the key update
    assert device_v2._api._encryption_key == DEVICE_SPECIFIC_KEY
    assert device_v2._api._is_bound is True

    # 6. Verify device state updated correctly from status list
    assert device_v2.hvac_mode == HVACMode.COOL
    assert device_v2.target_temperature == 23.0
    assert device_v2.fan_mode == FAN_MODES[1]  # Low
    assert device_v2._state.lights_state == STATE_ON  # Check state helper property


# External temperature sensor tests removed
