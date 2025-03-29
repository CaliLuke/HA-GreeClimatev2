# import pytest # Removed unused import
from homeassistant.components.climate import ClimateEntityFeature, HVACMode
from homeassistant.const import UnitOfTemperature

from custom_components.gree.climate import (DEFAULT_TARGET_TEMP_STEP,
                                            FAN_MODES, HVAC_MODES, MAX_TEMP,
                                            MIN_TEMP, PRESET_MODES,
                                            SWING_MODES)

# Fixtures (mock_hass, gree_climate_device) are automatically discovered from conftest.py

# --- Property Tests ---


async def test_properties_before_update(gree_climate_device):
    """Test default property values before the first update."""
    # Get the device instance by calling the factory
    device = gree_climate_device()
    # Check properties that have default values before any update is run
    assert device.hvac_mode == HVACMode.OFF  # Default seems to be OFF based on __init__
    assert device.target_temperature is None
    assert device.current_temperature is None
    assert device.fan_mode is None
    assert device.swing_mode is None
    assert device.preset_mode is None
    assert device.min_temp == MIN_TEMP
    assert device.max_temp == MAX_TEMP
    assert device.target_temperature_step == DEFAULT_TARGET_TEMP_STEP
    assert device.temperature_unit == UnitOfTemperature.CELSIUS
    assert device.hvac_modes == HVAC_MODES
    assert device.fan_modes == FAN_MODES
    assert device.swing_modes == SWING_MODES
    assert device.preset_modes == PRESET_MODES
    assert device.supported_features & ClimateEntityFeature.TARGET_TEMPERATURE
    assert device.supported_features & ClimateEntityFeature.FAN_MODE
    assert device.supported_features & ClimateEntityFeature.SWING_MODE
    assert device.supported_features & ClimateEntityFeature.TURN_ON
    assert device.supported_features & ClimateEntityFeature.TURN_OFF
    # Preset mode support depends on horizontal_swing flag
    assert not device.supported_features & ClimateEntityFeature.PRESET_MODE


async def test_properties_after_update(gree_climate_device):
    """Test property values are correctly set after a simulated update."""
    # Get the device instance by calling the factory
    device = gree_climate_device()
    # Simulate state being set by update/SyncState
    device._acOptions = {
        "Pow": 1,
        "Mod": 1,  # COOL
        "SetTem": 23,
        "WdSpd": 2,  # Medium-Low
        "SwUpDn": 3,  # Middle-up
        "SwingLfRig": 4,  # Middle position
        "Quiet": 0,
        "Tur": 0,
        "StHt": 0,
        "SwhSlp": 0,
        "SlpMod": 0,
        "Lig": 1,
        # ... add other relevant keys if needed ...
    }
    # Manually call the update methods to reflect _acOptions in properties
    # (Normally update() would call these)
    device.UpdateHAHvacMode()
    device.UpdateHATargetTemperature()
    device.UpdateHAFanMode()
    device.UpdateHACurrentSwingMode()
    device.UpdateHACurrentPresetMode()  # Call this even if horizontal_swing is false

    assert device.hvac_mode == HVACMode.COOL
    assert device.target_temperature == 23
    assert device.fan_mode == FAN_MODES[2]
    assert device.swing_mode == SWING_MODES[3]
    # If horizontal_swing is False (default), preset_mode should be None
    assert device.preset_mode is None


async def test_property_support_preset_mode(gree_climate_device):
    """Test preset mode support is enabled when horizontal_swing is true."""
    # Get the device instance by calling the factory, enabling horizontal swing
    device = gree_climate_device(horizontal_swing=True)
    assert device.supported_features & ClimateEntityFeature.PRESET_MODE
    assert device.preset_modes == PRESET_MODES


# Add more tests for other properties or specific states as needed
