import json  # Use standard json module
from typing import Any, Dict, List
from unittest.mock import MagicMock, call, patch

import pytest
from homeassistant.components.climate import HVACMode
from homeassistant.components.climate.const import FAN_MEDIUM, SWING_VERTICAL

# Import type alias from conftest
from .conftest import GreeClimateFactory

# Fixtures (mock_hass, gree_climate_device) are automatically discovered from conftest.py

# --- Command Method Tests (async wrappers) ---


@patch("custom_components.greev2.climate.GreeClimate.turn_on")
async def test_async_turn_on(
    mock_turn_on: MagicMock, gree_climate_device: GreeClimateFactory
) -> None:
    """Test turning the device on."""
    device = gree_climate_device()
    device._hvac_mode = HVACMode.OFF
    await device.async_turn_on()
    mock_turn_on.assert_called_once()


@patch("custom_components.greev2.climate.GreeClimate.turn_off")
async def test_async_turn_off(
    mock_turn_off: MagicMock, gree_climate_device: GreeClimateFactory
) -> None:
    """Test turning the device off."""
    device = gree_climate_device()
    device._hvac_mode = HVACMode.COOL
    await device.async_turn_off()
    mock_turn_off.assert_called_once()


@patch("custom_components.greev2.climate.GreeClimate.set_temperature")
async def test_async_set_temperature(
    mock_set_temperature: MagicMock, gree_climate_device: GreeClimateFactory
) -> None:
    """Test setting the target temperature."""
    device = gree_climate_device()
    test_temp: float = 24.0
    await device.async_set_temperature(temperature=test_temp)
    mock_set_temperature.assert_called_once_with(temperature=test_temp)


@pytest.mark.asyncio
@patch("custom_components.greev2.climate.GreeClimate.set_hvac_mode")
async def test_async_set_hvac_mode(
    mock_set_hvac_mode: MagicMock, gree_climate_device: GreeClimateFactory
) -> None:
    """Test setting HVAC mode calls the synchronous method."""
    device = gree_climate_device()
    await device.async_set_hvac_mode(hvac_mode=HVACMode.COOL)
    mock_set_hvac_mode.assert_called_once_with(HVACMode.COOL)


@pytest.mark.asyncio
@patch("custom_components.greev2.climate.GreeClimate.set_fan_mode")
async def test_async_set_fan_mode(
    mock_set_fan_mode: MagicMock, gree_climate_device: GreeClimateFactory
) -> None:
    """Test setting the fan mode calls the synchronous method."""
    device = gree_climate_device()
    await device.async_set_fan_mode(fan_mode=FAN_MEDIUM)
    mock_set_fan_mode.assert_called_once_with(FAN_MEDIUM)


@pytest.mark.asyncio
@patch("custom_components.greev2.climate.GreeClimate.set_swing_mode")
async def test_async_set_swing_mode(
    mock_set_swing_mode: MagicMock, gree_climate_device: GreeClimateFactory
) -> None:
    """Test setting the swing mode calls the synchronous method."""
    device = gree_climate_device()
    await device.async_set_swing_mode(swing_mode=SWING_VERTICAL)
    mock_set_swing_mode.assert_called_once_with(SWING_VERTICAL)


# --- Integration Tests (Service Call Flow) ---

# Removed @patch decorators as the API mock is now handled by the fixture
def test_set_hvac_mode_integration(
    gree_climate_device: GreeClimateFactory,
) -> None:
    """Test set_hvac_mode calls API via sync_state with correct payload."""
    # Arrange
    device = gree_climate_device() # Use fixture's mock API
    device._first_time_run = False
    device._ac_options["Pow"] = 1
    device._ac_options["Mod"] = 1 # Cool
    device._ac_options["WdSpd"] = 0
    device._ac_options["SwUpDn"] = 0
    device._has_temp_sensor = False
    device._has_anti_direct_blow = False
    device._has_light_sensor = False

    # Configure the mock API's get_status return value for this specific test scenario
    initial_state_list = [device._ac_options.get(key, 0) for key in device._options_to_fetch]
    device._api.get_status.return_value = initial_state_list
    # Configure the mock API's send_command return value
    device._api.send_command.return_value = {"r": 200, "opt": ["Pow", "Mod"], "p": [1, 4]}

    # Act
    device.set_hvac_mode(HVACMode.HEAT)

    # Assert
    device._api.send_command.assert_called_once() # Check call on the fixture's mock
    call_args, _ = device._api.send_command.call_args # Get args from the fixture's mock
    sent_opt_keys = call_args[0]
    sent_p_values = call_args[1]
    assert "Pow" in sent_opt_keys and "Mod" in sent_opt_keys
    pow_index = sent_opt_keys.index("Pow")
    mod_index = sent_opt_keys.index("Mod")
    assert sent_p_values[pow_index] == 1
    assert sent_p_values[mod_index] == 4 # HEAT mode index

# Removed @patch decorators
def test_set_temperature_integration(
    gree_climate_device: GreeClimateFactory,
) -> None:
    """Test set_temperature calls API via sync_state with correct payload."""
    # Arrange
    device = gree_climate_device() # Use fixture's mock API
    device._first_time_run = False
    device._ac_options["Pow"] = 1
    device._has_temp_sensor = False
    device._has_anti_direct_blow = False
    device._has_light_sensor = False
    device._ac_options["Mod"] = 1 # Cool
    device._ac_options["WdSpd"] = 0
    device._ac_options["SwUpDn"] = 0
    device._ac_options["StHt"] = 0

    # Configure mock API return values
    initial_state_list = [device._ac_options.get(key, 0) for key in device._options_to_fetch]
    device._api.get_status.return_value = initial_state_list
    device._api.send_command.return_value = {"r": 200, "opt": ["SetTem"], "p": [22]}

    # Act
    device.set_temperature(temperature=22.0)

    # Assert
    device._api.send_command.assert_called_once() # Check fixture's mock
    call_args, _ = device._api.send_command.call_args # Get args from fixture's mock
    sent_opt_keys = call_args[0]
    sent_p_values = call_args[1]
    assert "SetTem" in sent_opt_keys
    settem_index = sent_opt_keys.index("SetTem")
    assert sent_p_values[settem_index] == 22

# Removed @patch decorators
def test_set_fan_mode_integration(
    gree_climate_device: GreeClimateFactory,
) -> None:
    """Test set_fan_mode calls API via sync_state with correct payload."""
    # Arrange
    device = gree_climate_device() # Use fixture's mock API
    device._first_time_run = False
    device._ac_options["Pow"] = 1
    device._ac_options["Mod"] = 1 # Cool
    device._ac_options["WdSpd"] = 0
    device._ac_options["SwUpDn"] = 0
    device._has_temp_sensor = False
    device._has_anti_direct_blow = False
    device._has_light_sensor = False

    # Configure mock API return values
    initial_state_list = [device._ac_options.get(key, 0) for key in device._options_to_fetch]
    device._api.get_status.return_value = initial_state_list
    device._api.send_command.return_value = {"r": 200, "opt": ["WdSpd"], "p": [3]}

    # Act
    device.set_fan_mode("Medium")

    # Assert
    device._api.send_command.assert_called_once() # Check fixture's mock
    call_args, _ = device._api.send_command.call_args # Get args from fixture's mock
    sent_opt_keys = call_args[0]
    sent_p_values = call_args[1]
    assert ("WdSpd" in sent_opt_keys and "Tur" in sent_opt_keys and "Quiet" in sent_opt_keys)
    wdspd_index = sent_opt_keys.index("WdSpd")
    tur_index = sent_opt_keys.index("Tur")
    quiet_index = sent_opt_keys.index("Quiet")
    assert sent_p_values[wdspd_index] == 3
    assert sent_p_values[tur_index] == 0
    assert sent_p_values[quiet_index] == 0

# Removed @patch decorators
def test_turn_on_integration(
    gree_climate_device: GreeClimateFactory,
) -> None:
    """Test turn_on calls API via sync_state with correct payload."""
    # Arrange
    device = gree_climate_device() # Use fixture's mock API
    device._first_time_run = False
    device._has_temp_sensor = False
    device._has_anti_direct_blow = False
    device._has_light_sensor = False
    device._ac_options["Pow"] = 0
    device._ac_options["Mod"] = 1 # Cool
    device._ac_options["WdSpd"] = 0
    device._ac_options["SwUpDn"] = 0

    # Configure mock API return values
    initial_state_list = [device._ac_options.get(key, 0) for key in device._options_to_fetch]
    device._api.get_status.return_value = initial_state_list
    device._api.send_command.return_value = {"r": 200, "opt": ["Pow"], "p": [1]}

    # Act
    device.turn_on()

    # Assert
    device._api.send_command.assert_called_once() # Check fixture's mock
    call_args, _ = device._api.send_command.call_args # Get args from fixture's mock
    sent_opt_keys = call_args[0]
    sent_p_values = call_args[1]
    assert "Pow" in sent_opt_keys
    pow_index = sent_opt_keys.index("Pow")
    assert sent_p_values[pow_index] == 1

    # Prevent feature detection from modifying _options_to_fetch (Redundant?)
    # device._has_temp_sensor = False
    # device._has_anti_direct_blow = False
    # device._has_light_sensor = False

# Removed @patch decorators
def test_turn_off_integration(
    gree_climate_device: GreeClimateFactory,
) -> None:
    """Test turn_off calls API via sync_state with correct payload."""
    # Arrange
    device = gree_climate_device() # Use fixture's mock API
    device._first_time_run = False
    device._has_temp_sensor = False
    device._has_anti_direct_blow = False
    device._has_light_sensor = False
    device._ac_options["Pow"] = 1
    device._ac_options["Mod"] = 1 # Cool
    device._ac_options["WdSpd"] = 0
    device._ac_options["SwUpDn"] = 0

    # Configure mock API return values
    initial_state_list = [device._ac_options.get(key, 0) for key in device._options_to_fetch]
    device._api.get_status.return_value = initial_state_list
    device._api.send_command.return_value = {"r": 200, "opt": ["Pow"], "p": [0]}

    # Act
    device.turn_off()

    # Assert
    device._api.send_command.assert_called_once() # Check fixture's mock
    call_args, _ = device._api.send_command.call_args # Get args from fixture's mock
    sent_opt_keys = call_args[0]
    sent_p_values = call_args[1]
    assert "Pow" in sent_opt_keys
    pow_index = sent_opt_keys.index("Pow")
    assert sent_p_values[pow_index] == 0 # Power OFF
