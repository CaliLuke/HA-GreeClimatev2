from typing import Any, Dict

# import pytest  # Removed unused import
from homeassistant.components.climate import ClimateEntityFeature, HVACMode
from homeassistant.const import UnitOfTemperature

from custom_components.greev2.climate import GreeClimate  # Import class for type hint
from custom_components.greev2.const import (  # Import constants from const.py
    DEFAULT_TARGET_TEMP_STEP,
    FAN_MODES,
    HVAC_MODES,
    MAX_TEMP,
    MIN_TEMP,
    PRESET_MODES,
    SWING_MODES,
    # DEFAULT_HORIZONTAL_SWING, # Removed unused import
)

# Import type alias from conftest
from .conftest import GreeClimateFactory

# Fixtures (mock_hass, gree_climate_device) are automatically discovered from conftest.py

# --- Property Tests ---


async def test_properties_before_update(
    gree_climate_device: GreeClimateFactory,
) -> None:
    """Test default property values before the first update/sync."""
    # Get the device instance by calling the factory with default horizontal swing (False)
    device: GreeClimate = gree_climate_device(horizontal_swing=False)

    # Check properties based on initial state set in __init__ and GreeClimateState
    assert device.hvac_mode == HVACMode.OFF  # Initial state Pow=0
    assert device.target_temperature is None  # Initial state SetTem=None
    assert device.current_temperature is None  # Not updated yet
    assert device.fan_mode is None  # Initial state WdSpd=None
    assert device.swing_mode is None  # Initial state SwUpDn=None
    assert device.preset_mode is None  # horizontal_swing=False
    assert device.min_temp == MIN_TEMP
    assert device.max_temp == MAX_TEMP
    assert device.target_temperature_step == DEFAULT_TARGET_TEMP_STEP
    assert device.temperature_unit == UnitOfTemperature.CELSIUS
    assert device.hvac_modes == HVAC_MODES
    assert device.fan_modes == FAN_MODES
    assert device.swing_modes == SWING_MODES
    assert device.preset_modes is None  # horizontal_swing=False
    assert device.supported_features & ClimateEntityFeature.TARGET_TEMPERATURE
    assert device.supported_features & ClimateEntityFeature.FAN_MODE
    assert device.supported_features & ClimateEntityFeature.SWING_MODE
    assert device.supported_features & ClimateEntityFeature.TURN_ON
    assert device.supported_features & ClimateEntityFeature.TURN_OFF
    assert not (
        device.supported_features & ClimateEntityFeature.PRESET_MODE
    )  # horizontal_swing=False


async def test_properties_after_state_update(
    gree_climate_device: GreeClimateFactory,
) -> None:
    """Test property values are correctly set after updating the state helper."""
    # Get the device instance by calling the factory with default horizontal swing (False)
    device: GreeClimate = gree_climate_device(horizontal_swing=False)

    # Simulate state being set by _async_sync_state updating the helper
    simulated_acOptions: Dict[str, Any] = {
        "Pow": 1,
        "Mod": 1,  # COOL index
        "SetTem": 23,
        "WdSpd": 2,  # Medium index
        "SwUpDn": 3,  # Middle-up index
        "SwingLfRig": 4,  # Middle position index (used by preset mode if enabled)
        "Quiet": 0,
        "Tur": 0,
        "StHt": 0,
        "TemSen": 26,  # Internal temp
        # Other optional features off/None
        "Lig": 0,
        "Blo": 0,
        "Health": 0,
        "SvSt": 0,
        "Air": 0,
        "SwhSlp": 0,
        "SlpMod": 0,
        "AntiDirectBlow": 0,
    }
    # Update the state helper directly
    device._state.update_options(simulated_acOptions)
    # Also update the has_temp_sensor flag in the state helper as detection would have run
    device._state._has_temp_sensor = True

    # Properties should now reflect the updated state via the helper
    assert device.hvac_mode == HVACMode.COOL
    assert device.target_temperature == 23.0
    assert device.fan_mode == FAN_MODES[2]  # Medium
    assert device.swing_mode == SWING_MODES[3]  # Fixed Middle-up
    assert device.preset_mode is None  # horizontal_swing=False
    assert (
        device.current_temperature == 26.0
    )  # Internal sensor reading via get_internal_temp


async def test_property_support_preset_mode(
    gree_climate_device: GreeClimateFactory,
) -> None:
    """Test preset mode support is enabled when horizontal_swing is true."""
    # Get the device instance by calling the factory, explicitly enabling horizontal swing
    device: GreeClimate = gree_climate_device(horizontal_swing=True)

    # Check that features and modes were set correctly during __init__
    assert device.supported_features & ClimateEntityFeature.PRESET_MODE
    assert device.preset_modes == PRESET_MODES

    # Simulate state update and check preset mode property
    device._state.update_options({"SwingLfRig": 1})  # FullSwing index
    assert device.preset_mode == PRESET_MODES[1]  # FullSwing


# Add more tests for other properties or specific states as needed
