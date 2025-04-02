# pylint: disable=protected-access
"""Tests for GreeClimate service call methods."""

from unittest.mock import patch, AsyncMock # Removed MagicMock, ANY

# import pytest # Removed unused
from homeassistant.components.climate import HVACMode

# Remove unused HA const imports
# from homeassistant.components.climate.const import FAN_MEDIUM, SWING_VERTICAL, SWING_OFF

# Import component specific constants
from custom_components.greev2.const import FAN_MODES, SWING_MODES

# Import type alias from conftest
from ..conftest import GreeClimateFactory  # Adjusted import path

# Fixtures (mock_hass, gree_climate_device) are automatically discovered from conftest.py

# --- Command Method Tests (Simple Call Verification) ---


@patch(
    "custom_components.greev2.climate.GreeClimate._async_sync_state",
    new_callable=AsyncMock,
)  # Patch internal sync method
async def test_async_turn_on_calls_sync(
    mock_sync: AsyncMock, gree_climate_device: GreeClimateFactory
) -> None:
    """Test async_turn_on calls _async_sync_state."""
    device = gree_climate_device()
    device.entity_id = "climate.test_gree_ac"  # FIX: Add dummy entity_id
    await device.async_turn_on()
    mock_sync.assert_called_once_with({"Pow": 1})


@patch(
    "custom_components.greev2.climate.GreeClimate._async_sync_state",
    new_callable=AsyncMock,
)  # Patch internal sync method
async def test_async_turn_off_calls_sync(
    mock_sync: AsyncMock, gree_climate_device: GreeClimateFactory
) -> None:
    """Test async_turn_off calls _async_sync_state."""
    device = gree_climate_device()
    device.entity_id = "climate.test_gree_ac"  # FIX: Add dummy entity_id
    await device.async_turn_off()
    mock_sync.assert_called_once_with({"Pow": 0})


@patch(
    "custom_components.greev2.climate.GreeClimate._async_sync_state",
    new_callable=AsyncMock,
)  # Patch internal sync method
async def test_async_set_temperature_calls_sync(
    mock_sync: AsyncMock, gree_climate_device: GreeClimateFactory
) -> None:
    """Test async_set_temperature calls _async_sync_state."""
    device = gree_climate_device()
    device.entity_id = "climate.test_gree_ac"  # FIX: Add dummy entity_id
    # Simulate device being ON using the state helper
    device._state.update_options({"Pow": 1, "Mod": 1})  # FIX: Added Mod=1
    test_temp: float = 24.0
    await device.async_set_temperature(temperature=test_temp)
    mock_sync.assert_called_once_with({"SetTem": 24, "StHt": 0})


@patch(
    "custom_components.greev2.climate.GreeClimate._async_sync_state",
    new_callable=AsyncMock,
)  # Patch internal sync method
async def test_async_set_hvac_mode_calls_sync(
    mock_sync: AsyncMock, gree_climate_device: GreeClimateFactory
) -> None:
    """Test async_set_hvac_mode calls _async_sync_state."""
    device = gree_climate_device()
    device.entity_id = "climate.test_gree_ac"  # FIX: Add dummy entity_id
    await device.async_set_hvac_mode(hvac_mode=HVACMode.COOL)
    mock_sync.assert_called_once_with({"Pow": 1, "Mod": 1})  # Mod=1 is COOL index


@patch(
    "custom_components.greev2.climate.GreeClimate._async_sync_state",
    new_callable=AsyncMock,
)  # Patch internal sync method
async def test_async_set_fan_mode_calls_sync(
    mock_sync: AsyncMock, gree_climate_device: GreeClimateFactory
) -> None:
    """Test async_set_fan_mode calls _async_sync_state."""
    device = gree_climate_device()
    device.entity_id = "climate.test_gree_ac"  # FIX: Add dummy entity_id
    # Simulate device being ON using the state helper
    device._state.update_options({"Pow": 1, "Mod": 1})  # FIX: Added Mod=1
    await device.async_set_fan_mode(
        fan_mode=FAN_MODES[3]
    )  # FIX: Use component's Medium (index 3)
    mock_sync.assert_called_once_with({"WdSpd": 3, "Tur": 0, "Quiet": 0})


@patch(
    "custom_components.greev2.climate.GreeClimate._async_sync_state",
    new_callable=AsyncMock,
)  # Patch internal sync method
async def test_async_set_swing_mode_calls_sync(
    mock_sync: AsyncMock, gree_climate_device: GreeClimateFactory
) -> None:
    """Test async_set_swing_mode calls _async_sync_state."""
    device = gree_climate_device()
    device.entity_id = "climate.test_gree_ac"  # FIX: Add dummy entity_id
    # Simulate device being ON using the state helper
    device._state.update_options({"Pow": 1, "Mod": 1})  # FIX: Added Mod=1
    await device.async_set_swing_mode(
        swing_mode=SWING_MODES[1]
    )  # FIX: Use component's Swing Full Range (index 1)
    mock_sync.assert_called_once_with({"SwUpDn": 1})  # FIX: Check for index 1


# --- Integration Tests (Service Call Flow) ---


@patch("custom_components.greev2.climate.detect_features")  # Patch detect_features
async def test_set_hvac_mode_integration(
    mock_detect: AsyncMock,  # Add mock arg
    gree_climate_device: GreeClimateFactory,
) -> None:
    """Test set_hvac_mode calls API via sync_state with correct payload."""
    # Arrange
    device = gree_climate_device()  # Use fixture's mock API
    device.entity_id = "climate.test_gree_ac"  # FIX: Add dummy entity_id
    initial_options = list(device._options_to_fetch)
    # Simulate feature detection returning initial state
    mock_detect.return_value = (False, False, False, initial_options)

    # Set initial state using the state helper (Device ON, COOL)
    device._state.update_options({"Pow": 1, "Mod": 1, "WdSpd": 0, "SwUpDn": 0})
    device._first_time_run = False  # Assume initial update already happened

    # Configure the mock API's get_status return value based on current state
    current_state_values = [
        device._state._ac_options.get(key, 0) for key in initial_options
    ]
    device._api.get_status = AsyncMock(return_value=current_state_values)  # type: ignore[method-assign]
    device._api.send_command = AsyncMock(return_value={"r": 200})  # type: ignore[method-assign]

    # Act
    await device.async_set_hvac_mode(HVACMode.HEAT)  # Call async version

    # Assert
    device._api.get_status.assert_called_once_with(
        initial_options
    )  # Called by _async_sync_state
    device._api.send_command.assert_called_once()
    call_args, _ = device._api.send_command.call_args
    sent_opt_keys = call_args[0]
    sent_p_values = call_args[1]
    assert "Pow" in sent_opt_keys and "Mod" in sent_opt_keys
    pow_index = sent_opt_keys.index("Pow")
    mod_index = sent_opt_keys.index("Mod")
    assert sent_p_values[pow_index] == 1
    assert sent_p_values[mod_index] == 4  # HEAT mode index


@patch("custom_components.greev2.climate.detect_features")  # Patch detect_features
async def test_set_temperature_integration(
    mock_detect: AsyncMock,  # Add mock arg
    gree_climate_device: GreeClimateFactory,
) -> None:
    """Test set_temperature calls API via sync_state with correct payload."""
    # Arrange
    device = gree_climate_device()  # Use fixture's mock API
    device.entity_id = "climate.test_gree_ac"  # FIX: Add dummy entity_id
    initial_options = list(device._options_to_fetch)
    mock_detect.return_value = (False, False, False, initial_options)

    # Set initial state (Device ON, COOL, StHt=0)
    device._state.update_options({"Pow": 1, "Mod": 1, "StHt": 0})
    device._first_time_run = False

    # Configure mock API return values
    current_state_values = [
        device._state._ac_options.get(key, 0) for key in initial_options
    ]
    device._api.get_status = AsyncMock(return_value=current_state_values)  # type: ignore[method-assign]
    device._api.send_command = AsyncMock(return_value={"r": 200})  # type: ignore[method-assign]

    # Act
    await device.async_set_temperature(temperature=22.0)  # Call async version

    # Assert
    device._api.get_status.assert_called_once_with(initial_options)
    device._api.send_command.assert_called_once()
    call_args, _ = device._api.send_command.call_args
    sent_opt_keys = call_args[0]
    sent_p_values = call_args[1]
    assert "SetTem" in sent_opt_keys and "StHt" in sent_opt_keys
    settem_index = sent_opt_keys.index("SetTem")
    stht_index = sent_opt_keys.index("StHt")
    assert sent_p_values[settem_index] == 22
    assert sent_p_values[stht_index] == 0  # Ensure 8deg heat is turned off


@patch("custom_components.greev2.climate.detect_features")  # Patch detect_features
async def test_set_fan_mode_integration(
    mock_detect: AsyncMock,  # Add mock arg
    gree_climate_device: GreeClimateFactory,
) -> None:
    """Test set_fan_mode calls API via sync_state with correct payload."""
    # Arrange
    device = gree_climate_device()  # Use fixture's mock API
    device.entity_id = "climate.test_gree_ac"  # FIX: Add dummy entity_id
    initial_options = list(device._options_to_fetch)
    mock_detect.return_value = (False, False, False, initial_options)

    # Set initial state (Device ON, COOL)
    device._state.update_options({"Pow": 1, "Mod": 1})
    device._first_time_run = False

    # Configure mock API return values
    current_state_values = [
        device._state._ac_options.get(key, 0) for key in initial_options
    ]
    device._api.get_status = AsyncMock(return_value=current_state_values)  # type: ignore[method-assign]
    device._api.send_command = AsyncMock(return_value={"r": 200})  # type: ignore[method-assign]

    # Act
    await device.async_set_fan_mode(
        FAN_MODES[3]
    )  # FIX: Use component's Medium (Index 3)

    # Assert
    device._api.get_status.assert_called_once_with(initial_options)
    device._api.send_command.assert_called_once()
    call_args, _ = device._api.send_command.call_args
    sent_opt_keys = call_args[0]
    sent_p_values = call_args[1]
    assert (
        "WdSpd" in sent_opt_keys and "Tur" in sent_opt_keys and "Quiet" in sent_opt_keys
    )
    wdspd_index = sent_opt_keys.index("WdSpd")
    tur_index = sent_opt_keys.index("Tur")
    quiet_index = sent_opt_keys.index("Quiet")
    assert sent_p_values[wdspd_index] == 3  # Medium index
    assert sent_p_values[tur_index] == 0
    assert sent_p_values[quiet_index] == 0


@patch("custom_components.greev2.climate.detect_features")  # Patch detect_features
async def test_turn_on_integration(
    mock_detect: AsyncMock,  # Add mock arg
    gree_climate_device: GreeClimateFactory,
) -> None:
    """Test turn_on calls API via sync_state with correct payload."""
    # Arrange
    device = gree_climate_device()  # Use fixture's mock API
    device.entity_id = "climate.test_gree_ac"  # FIX: Add dummy entity_id
    initial_options = list(device._options_to_fetch)
    mock_detect.return_value = (False, False, False, initial_options)

    # Set initial state (Device OFF)
    device._state.update_options({"Pow": 0})
    device._first_time_run = False

    # Configure mock API return values
    current_state_values = [
        device._state._ac_options.get(key, 0) for key in initial_options
    ]
    device._api.get_status = AsyncMock(return_value=current_state_values)  # type: ignore[method-assign]
    device._api.send_command = AsyncMock(return_value={"r": 200})  # type: ignore[method-assign]

    # Act
    await device.async_turn_on()  # Call async version

    # Assert
    device._api.get_status.assert_called_once_with(initial_options)
    device._api.send_command.assert_called_once()
    call_args, _ = device._api.send_command.call_args
    sent_opt_keys = call_args[0]
    sent_p_values = call_args[1]
    assert "Pow" in sent_opt_keys
    pow_index = sent_opt_keys.index("Pow")
    assert sent_p_values[pow_index] == 1  # Power ON


@patch("custom_components.greev2.climate.detect_features")  # Patch detect_features
async def test_turn_off_integration(
    mock_detect: AsyncMock,  # Add mock arg
    gree_climate_device: GreeClimateFactory,
) -> None:
    """Test turn_off calls API via sync_state with correct payload."""
    # Arrange
    device = gree_climate_device()  # Use fixture's mock API
    device.entity_id = "climate.test_gree_ac"  # FIX: Add dummy entity_id
    initial_options = list(device._options_to_fetch)
    mock_detect.return_value = (False, False, False, initial_options)

    # Set initial state (Device ON)
    device._state.update_options({"Pow": 1})
    device._first_time_run = False

    # Configure mock API return values
    current_state_values = [
        device._state._ac_options.get(key, 0) for key in initial_options
    ]
    device._api.get_status = AsyncMock(return_value=current_state_values)  # type: ignore[method-assign]
    device._api.send_command = AsyncMock(return_value={"r": 200})  # type: ignore[method-assign]

    # Act
    await device.async_turn_off()  # Call async version

    # Assert
    device._api.get_status.assert_called_once_with(initial_options)
    device._api.send_command.assert_called_once()
    call_args, _ = device._api.send_command.call_args
    sent_opt_keys = call_args[0]
    sent_p_values = call_args[1]
    assert "Pow" in sent_opt_keys
    pow_index = sent_opt_keys.index("Pow")
    assert sent_p_values[pow_index] == 0  # Power OFF
