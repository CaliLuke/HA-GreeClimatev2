"""Constants for the Gree Climate V2 integration."""

from datetime import timedelta
from typing import List

from homeassistant.components.climate import ClimateEntityFeature, HVACMode
from homeassistant.const import (
    UnitOfTemperature,
)  # Needed for type hints if used, but not directly used here yet

DOMAIN = "greev2"

# Default values
DEFAULT_NAME: str = "Gree Climate"
DEFAULT_PORT: int = 7000
DEFAULT_TIMEOUT: int = 10
DEFAULT_TARGET_TEMP_STEP: float = 1.0
DEFAULT_MIN_TEMP: int = 16
DEFAULT_MAX_TEMP: int = 30
DEFAULT_SCAN_INTERVAL_SECONDS: int = 60
DEFAULT_HORIZONTAL_SWING: bool = False  # Default based on previous YAML schema
DEFAULT_DISABLE_AVAILABILITY_CHECK: bool = (
    False  # Default based on previous YAML schema
)
DEFAULT_MAX_ONLINE_ATTEMPTS: int = 3  # Default based on previous YAML schema


# Configuration constants
CONF_NAME: str = "name"
CONF_HOST: str = "host"
CONF_PORT: str = "port"
CONF_TEMP_SENSOR: str = "temp_sensor"

CONF_MAC: str = "mac"
CONF_TIMEOUT: str = "timeout"

CONF_TARGET_TEMP_STEP: str = "target_temp_step"
CONF_LIGHTS: str = "lights"
CONF_XFAN: str = "xfan"
CONF_HEALTH: str = "health"
CONF_POWERSAVE: str = "powersave"
CONF_SLEEP: str = "sleep"
CONF_EIGHTDEGHEAT: str = "eightdegheat"
CONF_AIR: str = "air"
CONF_ENCRYPTION_KEY: str = "encryption_key"
CONF_UID: str = "uid"
CONF_AUTO_XFAN: str = "auto_xfan"
CONF_AUTO_LIGHT: str = "auto_light"
CONF_TARGET_TEMP: str = "target_temp"
CONF_HORIZONTAL_SWING: str = "horizontal_swing"
CONF_ANTI_DIRECT_BLOW: str = "anti_direct_blow"
CONF_ENCRYPTION_VERSION: str = "encryption_version"
CONF_DISABLE_AVAILABLE_CHECK: str = "disable_available_check"
CONF_MAX_ONLINE_ATTEMPTS: str = "max_online_attempts"
CONF_LIGHT_SENSOR: str = "light_sensor"

# Device limits and features
MIN_TEMP: int = DEFAULT_MIN_TEMP
MAX_TEMP: int = DEFAULT_MAX_TEMP
TEMP_OFFSET: int = 40  # Offset used for internal temperature sensor readings

# Update interval
SCAN_INTERVAL: timedelta = timedelta(seconds=DEFAULT_SCAN_INTERVAL_SECONDS)

# Supported features
SUPPORT_FLAGS: ClimateEntityFeature = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.FAN_MODE
    | ClimateEntityFeature.SWING_MODE
    | ClimateEntityFeature.TURN_ON
    | ClimateEntityFeature.TURN_OFF
    # PRESET_MODE is added conditionally in climate.py based on config
)

# Fixed values in gree mode lists
HVAC_MODES: List[HVACMode] = [
    HVACMode.AUTO,
    HVACMode.COOL,
    HVACMode.DRY,
    HVACMode.FAN_ONLY,
    HVACMode.HEAT,
    HVACMode.OFF,
]

FAN_MODES: List[str] = [
    "Auto",
    "Low",
    "Medium-Low",
    "Medium",
    "Medium-High",
    "High",
    "Turbo",
    "Quiet",
]

SWING_MODES: List[str] = [
    "Default",
    "Swing in full range",
    "Fixed in the upmost position",
    "Fixed in the middle-up position",
    "Fixed in the middle position",
    "Fixed in the middle-low position",
    "Fixed in the lowest position",
    "Swing in the downmost region",
    "Swing in the middle-low region",
    "Swing in the middle region",
    "Swing in the middle-up region",
    "Swing in the upmost region",
]

# Preset modes correspond to Horizontal Swing
PRESET_MODES: List[str] = [
    "Default",
    "Full swing",
    "Fixed in the leftmost position",
    "Fixed in the middle-left position",
    "Fixed in the middle position",  # Corrected typo
    "Fixed in the middle-right position",
    "Fixed in the rightmost position",
]

# GCM Constants (Used for V2 encryption binding/communication)
GCM_DEFAULT_KEY: str = "{yxAHAY_Lm6pbC/<"  # Default key for GCM binding based on logs
GCM_IV: bytes = (
    b"\x54\x40\x78\x44\x49\x67\x5a\x51\x6c\x5e\x63\x13"  # From device_api.py
)
GCM_ADD: bytes = b"qualcomm-test"  # From device_api.py
