from typing import Any, Dict

from homeassistant.components.climate import ClimateEntityFeature, HVACMode
from homeassistant.const import UnitOfTemperature

from custom_components.greev2.climate import (
    DEFAULT_TARGET_TEMP_STEP,
    FAN_MODES,
    HVAC_MODES,
    MAX_TEMP,
    MIN_TEMP,
    PRESET_MODES,
    SWING_MODES,
    GreeClimate,  # Import class for type hint
)

# Import type alias from conftest
from .conftest import GreeClimateFactory

# Fixtures (mock_hass, gree_climate_device) are automatically discovered from conftest.py

# --- Property Tests ---


async def test_properties_before_update(
    gree_climate_device: GreeClimateFactory,
) -> None:
    """Test default property values before the first update."""
    # Get the device instance by calling the factory
    device: GreeClimate = gree_climate_device()
    # Check properties that have default values before any update is run
    assert device.hvac_mode == HVACMode.OFF  # Default seems to be OFF based on __init__
    assert device.target_temperature is None
    assert device.current_temperature is None
    assert device.fan_mode is None
    assert device.swing_mode is None
    assert device.preset_mode is None  # Default factory has horizontal_swing=False
    assert device.min_temp == MIN_TEMP
    assert device.max_temp == MAX_TEMP
    assert device.target_temperature_step == DEFAULT_TARGET_TEMP_STEP
    assert device.temperature_unit == UnitOfTemperature.CELSIUS
    assert device.hvac_modes == HVAC_MODES
    assert device.fan_modes == FAN_MODES
    assert device.swing_modes == SWING_MODES
    # preset_modes property depends on horizontal_swing flag in __init__
    assert device.preset_modes is None  # Default factory has horizontal_swing=False
    assert device.supported_features & ClimateEntityFeature.TARGET_TEMPERATURE
    assert device.supported_features & ClimateEntityFeature.FAN_MODE
    assert device.supported_features & ClimateEntityFeature.SWING_MODE
    assert device.supported_features & ClimateEntityFeature.TURN_ON
    assert device.supported_features & ClimateEntityFeature.TURN_OFF
    # Preset mode support depends on horizontal_swing flag
    assert not (device.supported_features & ClimateEntityFeature.PRESET_MODE)


async def test_properties_after_update(gree_climate_device: GreeClimateFactory) -> None:
    """Test property values are correctly set after a simulated update."""
    # Get the device instance by calling the factory
    device: GreeClimate = gree_climate_device()
    # Simulate state being set by update/SyncState
    # Ensure all keys expected by UpdateHA* methods are present
    simulated_acOptions: Dict[str, Any] = {
        "Pow": 1,
        "Mod": 1,  # COOL index
        "SetTem": 23,
        "WdSpd": 2,  # Medium-Low index
        "SwUpDn": 3,  # Middle-up index
        "SwingLfRig": 4,  # Middle position index (used by preset mode)
        "Quiet": 0,
        "Tur": 0,
        "StHt": 0,
        "SwhSlp": 0,
        "SlpMod": 0,
        "Lig": 1,
        "Blo": 0,
        "Health": 0,
        "SvSt": 0,
        "Air": 0,
        "TemSen": None,  # Assume no internal sensor for this test
        "AntiDirectBlow": None,  # Assume feature not present or off
        "LigSen": None,  # Assume feature not present or off
        # Add other keys from _acOptions init if necessary
        "TemUn": 0,
        "HeatCoolType": 0,
        "TemRec": 0,
    }
    device._acOptions = (
        simulated_acOptions  # No longer need ignore after fixing _acOptions type
    )

    # Manually call the update methods to reflect _acOptions in properties
    # (Normally update() would call these via UpdateHAStateToCurrentACState)
    device.UpdateHAHvacMode()
    device.UpdateHATargetTemperature()
    device.UpdateHAFanMode()
    device.UpdateHACurrentSwingMode()
    device.UpdateHACurrentPresetMode()  # Call this even if horizontal_swing is false

    assert device.hvac_mode == HVACMode.COOL
    assert device.target_temperature == 23.0  # Should be float
    assert device.fan_mode == FAN_MODES[2]  # Medium-Low
    assert device.swing_mode == SWING_MODES[3]  # Fixed in the middle-up position
    # If horizontal_swing is False (default in fixture), preset_mode should be None
    assert device.preset_mode is None


async def test_property_support_preset_mode(
    gree_climate_device: GreeClimateFactory,
) -> None:
    """Test preset mode support is enabled when horizontal_swing is true."""
    # Get the device instance by calling the factory, enabling horizontal swing
    device: GreeClimate = gree_climate_device(horizontal_swing=True)
    assert device.supported_features & ClimateEntityFeature.PRESET_MODE
    assert device.preset_modes == PRESET_MODES


# Add more tests for other properties or specific states as needed
