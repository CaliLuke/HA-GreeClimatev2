"""Unit tests for climate_helpers.py."""

import socket
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch
import pytest

from homeassistant.components.climate import HVACMode

# Need constants for optional state tests
from homeassistant.const import STATE_ON, STATE_OFF, STATE_UNKNOWN

# Assuming consts are accessible or mocked if needed
from custom_components.greev2.const import (
    HVAC_MODES,
    FAN_MODES,
    SWING_MODES,
    PRESET_MODES,
    TEMP_OFFSET,  # Added TEMP_OFFSET
)

# Import detect_features and GreeDeviceApi for testing
from custom_components.greev2.climate_helpers import GreeClimateState, detect_features
from custom_components.greev2.device_api import GreeDeviceApi


# --- Fixtures ---


@pytest.fixture
def initial_state_options() -> Dict[str, Optional[int]]:
    """Return a default initial state dictionary."""
    return {
        "Pow": 1,
        "Mod": 1,
        "SetTem": 24,
        "WdSpd": 2,
        "Air": 0,
        "Blo": 0,
        "Health": 0,
        "SwhSlp": 0,
        "Lig": 1,
        "SwingLfRig": 0,
        "SwUpDn": 1,
        "Quiet": 0,
        "Tur": 0,
        "StHt": 0,
        "TemUn": 0,
        "HeatCoolType": 1,
        "TemRec": 25,
        "SvSt": 0,
        "SlpMod": 0,
        "TemSen": 26,
        "AntiDirectBlow": None,
        "LigSen": None,
    }


@pytest.fixture
def climate_state(initial_state_options: Dict[str, Optional[int]]) -> GreeClimateState:
    """Return a GreeClimateState instance with default options."""
    # Assume default horizontal swing and internal temp sensor for basic tests
    return GreeClimateState(
        initial_options=initial_state_options,
        horizontal_swing=True,
        has_temp_sensor=True,
    )


# --- Test Cases for GreeClimateState ---


def test_init(
    climate_state: GreeClimateState, initial_state_options: Dict[str, Optional[int]]
):
    """Test GreeClimateState initialization."""
    assert climate_state._ac_options == initial_state_options
    assert climate_state._horizontal_swing is True
    assert climate_state._has_temp_sensor is True


def test_update_options_dict(climate_state: GreeClimateState):
    """Test updating options with a dictionary."""
    climate_state.update_options({"Pow": 0, "SetTem": 20})
    assert climate_state._ac_options["Pow"] == 0
    assert climate_state._ac_options["SetTem"] == 20
    assert climate_state._ac_options["Mod"] == 1  # Unchanged


def test_update_options_list(climate_state: GreeClimateState):
    """Test updating options with lists."""
    keys = ["Mod", "WdSpd", "Lig"]
    values = [3, 4, 0]
    climate_state.update_options(keys, values)
    assert climate_state._ac_options["Mod"] == 3
    assert climate_state._ac_options["WdSpd"] == 4
    assert climate_state._ac_options["Lig"] == 0
    assert climate_state._ac_options["Pow"] == 1  # Unchanged


def test_update_options_invalid_type(climate_state: GreeClimateState, caplog):
    """Test updating options with invalid types logs errors."""
    climate_state.update_options({"SetTem": "invalid"})
    assert "Could not convert value 'invalid' to int for key 'SetTem'" in caplog.text
    assert climate_state._ac_options["SetTem"] is None

    climate_state.update_options(["SetTem"], ["invalid2"])
    assert "Could not convert value 'invalid2' to int for key 'SetTem'" in caplog.text
    assert climate_state._ac_options["SetTem"] is None


def test_update_options_mismatched_lists(climate_state: GreeClimateState, caplog):
    """Test updating options with mismatched lists logs an error."""
    climate_state.update_options(["Pow", "Mod"], [0])  # Mismatched length
    assert "Mismatched lengths for keys (2) and values (1)" in caplog.text


# --- Property Tests ---


def test_target_temperature_property(climate_state: GreeClimateState):
    """Test the target_temperature property."""
    assert climate_state.target_temperature == 24.0
    climate_state.update_options({"SetTem": 18})
    assert climate_state.target_temperature == 18.0
    climate_state.update_options({"StHt": 1})  # 8 degree heat
    assert climate_state.target_temperature == 8.0
    climate_state.update_options({"StHt": 0, "SetTem": None})
    assert climate_state.target_temperature is None


def test_hvac_mode_property(climate_state: GreeClimateState):
    """Test the hvac_mode property."""
    # Initial state: Pow=1, Mod=1 (Cool)
    assert climate_state.hvac_mode == HVACMode.COOL

    climate_state.update_options({"Pow": 0})
    assert climate_state.hvac_mode == HVACMode.OFF

    climate_state.update_options({"Pow": 1, "Mod": 0})  # Auto
    assert climate_state.hvac_mode == HVACMode.AUTO  # FIX: Changed from HEAT_COOL

    climate_state.update_options({"Mod": 3})  # Fan Only
    assert climate_state.hvac_mode == HVACMode.FAN_ONLY

    climate_state.update_options({"Mod": 4})  # Heat
    assert climate_state.hvac_mode == HVACMode.HEAT

    climate_state.update_options({"Mod": 99})  # Invalid index
    assert climate_state.hvac_mode == HVACMode.OFF  # Should default to OFF


def test_fan_mode_property(climate_state: GreeClimateState):
    """Test the fan_mode property."""
    # Initial: WdSpd=2 -> Medium
    assert climate_state.fan_mode == FAN_MODES[2]  # Medium

    climate_state.update_options({"WdSpd": 0})  # Low
    assert climate_state.fan_mode == FAN_MODES[0]  # Low

    climate_state.update_options({"Tur": 1})  # Turbo
    assert climate_state.fan_mode == "Turbo"

    climate_state.update_options({"Tur": 0, "Quiet": 1})  # Quiet
    assert climate_state.fan_mode == "Quiet"

    climate_state.update_options({"Quiet": 0, "WdSpd": 4})  # High
    assert climate_state.fan_mode == FAN_MODES[4]  # High

    climate_state.update_options({"WdSpd": 99})  # Invalid
    assert climate_state.fan_mode is None


def test_swing_mode_property(climate_state: GreeClimateState):
    """Test the swing_mode property (vertical)."""
    # Initial: SwUpDn=1 -> Default
    assert climate_state.swing_mode == SWING_MODES[1]  # Default

    climate_state.update_options({"SwUpDn": 0})  # Swing
    assert climate_state.swing_mode == SWING_MODES[0]  # Swing

    climate_state.update_options({"SwUpDn": 6})  # FixedHighest
    assert climate_state.swing_mode == SWING_MODES[6]  # FixedHighest

    climate_state.update_options({"SwUpDn": 99})  # Invalid
    assert climate_state.swing_mode is None


def test_preset_mode_property(climate_state: GreeClimateState):
    """Test the preset_mode property (horizontal swing)."""
    # Initial: SwingLfRig=0 -> Default (horizontal_swing=True)
    assert climate_state.preset_mode == PRESET_MODES[0]  # Default

    climate_state.update_options({"SwingLfRig": 1})  # FullSwing
    assert climate_state.preset_mode == PRESET_MODES[1]  # FullSwing

    climate_state.update_options(
        {"SwingLfRig": 6}
    )  # FIX: Changed from 7 to 6 (FixedRightmost)
    assert climate_state.preset_mode == PRESET_MODES[6]  # FIX: Changed from 7 to 6

    climate_state.update_options({"SwingLfRig": 99})  # Invalid
    assert climate_state.preset_mode is None

    # Test when horizontal swing is disabled
    climate_state_no_h_swing = GreeClimateState(
        initial_options=climate_state._ac_options,
        horizontal_swing=False,  # Disabled
        has_temp_sensor=True,
    )
    assert climate_state_no_h_swing.preset_mode is None  # Should always be None


# --- Helper Method Tests ---


def test_get_internal_temp(climate_state: GreeClimateState):
    """Test the get_internal_temp helper method."""
    # Initial: TemSen=26, has_temp_sensor=True
    assert climate_state.get_internal_temp() == 26.0

    climate_state.update_options({"TemSen": 55})  # Value requiring offset
    # TEMP_OFFSET is 40, so 55 - 40 = 15
    assert climate_state.get_internal_temp() == 15.0

    climate_state.update_options({"TemSen": None})
    assert climate_state.get_internal_temp() is None

    # Test when internal sensor is disabled/not detected
    climate_state_no_sensor = GreeClimateState(
        initial_options=climate_state._ac_options,
        horizontal_swing=True,
        has_temp_sensor=False,  # Disabled
    )
    climate_state_no_sensor.update_options({"TemSen": 30})  # Set a value
    assert climate_state_no_sensor.get_internal_temp() is None  # Should still be None


# --- Optional State Property Tests ---


def test_lights_state_property(climate_state: GreeClimateState):
    """Test the lights_state property."""
    climate_state.update_options({"Lig": 1})
    assert climate_state.lights_state == STATE_ON
    climate_state.update_options({"Lig": 0})
    assert climate_state.lights_state == STATE_OFF
    climate_state.update_options({"Lig": None})
    assert climate_state.lights_state == STATE_UNKNOWN


def test_xfan_state_property(climate_state: GreeClimateState):
    """Test the xfan_state property."""
    climate_state.update_options({"Blo": 1})
    assert climate_state.xfan_state == STATE_ON
    climate_state.update_options({"Blo": 0})
    assert climate_state.xfan_state == STATE_OFF
    climate_state.update_options({"Blo": None})
    assert climate_state.xfan_state == STATE_UNKNOWN


def test_health_state_property(climate_state: GreeClimateState):
    """Test the health_state property."""
    climate_state.update_options({"Health": 1})
    assert climate_state.health_state == STATE_ON
    climate_state.update_options({"Health": 0})
    assert climate_state.health_state == STATE_OFF
    climate_state.update_options({"Health": None})
    assert climate_state.health_state == STATE_UNKNOWN


def test_powersave_state_property(climate_state: GreeClimateState):
    """Test the powersave_state property."""
    climate_state.update_options({"SvSt": 1})
    assert climate_state.powersave_state == STATE_ON
    climate_state.update_options({"SvSt": 0})
    assert climate_state.powersave_state == STATE_OFF
    climate_state.update_options({"SvSt": None})
    assert climate_state.powersave_state == STATE_UNKNOWN


def test_sleep_state_property(climate_state: GreeClimateState):
    """Test the sleep_state property."""
    # Sleep ON requires SwhSlp=1 AND SlpMod=1
    climate_state.update_options({"SwhSlp": 1, "SlpMod": 1})
    assert climate_state.sleep_state == STATE_ON
    # Sleep OFF requires SwhSlp=0 AND SlpMod=0
    climate_state.update_options({"SwhSlp": 0, "SlpMod": 0})
    assert climate_state.sleep_state == STATE_OFF
    # Other combinations are UNKNOWN
    climate_state.update_options({"SwhSlp": 1, "SlpMod": 0})
    assert climate_state.sleep_state == STATE_UNKNOWN
    climate_state.update_options({"SwhSlp": 0, "SlpMod": 1})
    assert climate_state.sleep_state == STATE_UNKNOWN
    climate_state.update_options({"SwhSlp": None, "SlpMod": None})
    assert climate_state.sleep_state == STATE_UNKNOWN


def test_eightdegheat_state_property(climate_state: GreeClimateState):
    """Test the eightdegheat_state property."""
    climate_state.update_options({"StHt": 1})
    assert climate_state.eightdegheat_state == STATE_ON
    climate_state.update_options({"StHt": 0})
    assert climate_state.eightdegheat_state == STATE_OFF
    climate_state.update_options({"StHt": None})
    assert climate_state.eightdegheat_state == STATE_UNKNOWN


def test_air_state_property(climate_state: GreeClimateState):
    """Test the air_state property."""
    climate_state.update_options({"Air": 1})
    assert climate_state.air_state == STATE_ON
    climate_state.update_options({"Air": 0})
    assert climate_state.air_state == STATE_OFF
    climate_state.update_options({"Air": None})
    assert climate_state.air_state == STATE_UNKNOWN


def test_anti_direct_blow_state_property(climate_state: GreeClimateState):
    """Test the anti_direct_blow_state property."""
    # Assumes feature exists for state calculation
    climate_state.update_options({"AntiDirectBlow": 1})
    assert climate_state.anti_direct_blow_state == STATE_ON
    climate_state.update_options({"AntiDirectBlow": 0})
    assert climate_state.anti_direct_blow_state == STATE_OFF
    climate_state.update_options({"AntiDirectBlow": None})
    assert climate_state.anti_direct_blow_state == STATE_UNKNOWN


# --- detect_features Tests ---


@pytest.mark.asyncio
async def test_detect_features_all_found():
    """Test detect_features when all features are found."""
    mock_api = AsyncMock(spec=GreeDeviceApi)
    # Simulate successful API responses (return a list, content doesn't matter here)
    mock_api.get_status.side_effect = [
        [25],  # TemSen found
        [1],  # AntiDirectBlow found
        [1],  # LigSen found
    ]
    initial_options = ["Pow", "Mod"]
    expected_options = ["Pow", "Mod", "TemSen", "AntiDirectBlow", "LigSen"]

    has_temp, has_adb, has_light, final_options = await detect_features(
        mock_api, initial_options
    )

    assert has_temp is True
    assert has_adb is True
    assert has_light is True
    assert sorted(final_options) == sorted(
        expected_options
    )  # Sort for comparison consistency
    assert mock_api.get_status.call_count == 3
    mock_api.get_status.assert_any_call(["TemSen"])
    mock_api.get_status.assert_any_call(["AntiDirectBlow"])
    mock_api.get_status.assert_any_call(["LigSen"])


@pytest.mark.asyncio
async def test_detect_features_none_found():
    """Test detect_features when no features are found."""
    mock_api = AsyncMock(spec=GreeDeviceApi)
    # Simulate API responses indicating feature not found (e.g., return None or empty list)
    mock_api.get_status.side_effect = [
        None,  # TemSen not found
        None,  # AntiDirectBlow not found
        None,  # LigSen not found
    ]
    initial_options = ["Pow", "Mod"]
    expected_options = ["Pow", "Mod"]  # Should remain unchanged

    has_temp, has_adb, has_light, final_options = await detect_features(
        mock_api, initial_options
    )

    assert has_temp is False
    assert has_adb is False
    assert has_light is False
    assert sorted(final_options) == sorted(expected_options)
    assert mock_api.get_status.call_count == 3


@pytest.mark.asyncio
async def test_detect_features_some_found():
    """Test detect_features when only some features are found."""
    mock_api = AsyncMock(spec=GreeDeviceApi)
    mock_api.get_status.side_effect = [
        [25],  # TemSen found
        None,  # AntiDirectBlow not found
        [1],  # LigSen found
    ]
    initial_options = ["Pow", "Mod", "TemSen"]  # TemSen already present
    expected_options = ["Pow", "Mod", "TemSen", "LigSen"]  # Only LigSen should be added

    has_temp, has_adb, has_light, final_options = await detect_features(
        mock_api, initial_options
    )

    assert has_temp is True
    assert has_adb is False
    assert has_light is True
    assert sorted(final_options) == sorted(expected_options)
    assert mock_api.get_status.call_count == 3


@pytest.mark.asyncio
async def test_detect_features_api_error(caplog):
    """Test detect_features when API calls raise errors."""
    mock_api = AsyncMock(spec=GreeDeviceApi)
    mock_api.get_status.side_effect = [
        socket.timeout("Test timeout"),  # Error on TemSen
        [1],  # ADB found
        ConnectionError("Test connection error"),  # Error on LigSen
    ]
    initial_options = ["Pow", "Mod"]
    expected_options = ["Pow", "Mod", "AntiDirectBlow"]  # Only ADB should be added

    has_temp, has_adb, has_light, final_options = await detect_features(
        mock_api, initial_options
    )

    assert has_temp is False  # Failed detection defaults to False
    assert has_adb is True
    assert has_light is False  # Failed detection defaults to False
    assert sorted(final_options) == sorted(expected_options)
    assert mock_api.get_status.call_count == 3
    assert "Error detecting internal temperature sensor: Test timeout" in caplog.text
    assert "Error detecting light sensor: Test connection error" in caplog.text


# TODO: Adapt existing tests (test_properties.py, test_update.py, etc.) - This is partially done
