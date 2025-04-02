"""Helper classes and functions for the Gree Climate platform."""

import logging
import socket  # Added import
from typing import Any, Dict, List, Optional, Tuple, Union

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.components.climate import HVACMode

# Assuming necessary consts are imported here or passed in
from .const import FAN_MODES, SWING_MODES, PRESET_MODES, TEMP_OFFSET, HVAC_MODES
from .device_api import GreeDeviceApi  # Needed for feature detection

_LOGGER = logging.getLogger(__name__)


class GreeClimateState:
    """Manages the internal state representation (_ac_options) and translation."""

    def __init__(
        self,
        initial_options: Dict[str, Optional[int]],
        horizontal_swing: bool,
        has_temp_sensor: bool,
    ):
        """Initialize the state manager."""
        self._ac_options: Dict[str, Optional[int]] = initial_options
        self._horizontal_swing = horizontal_swing  # Store flag
        self._has_temp_sensor = has_temp_sensor  # Store flag

    def update_options(
        self,
        new_options_to_override: Union[List[str], Dict[str, Any]],
        option_values_to_override: Optional[List[Any]] = None,
    ) -> None:
        """Update the internal _ac_options dictionary."""
        if option_values_to_override is not None and isinstance(
            new_options_to_override, list
        ):
            if len(new_options_to_override) != len(option_values_to_override):
                _LOGGER.error(
                    "update_options error: Mismatched lengths for keys (%d) and values (%d)",
                    len(new_options_to_override),
                    len(option_values_to_override),
                )
            else:
                for i, key in enumerate(new_options_to_override):
                    value = option_values_to_override[i]
                    try:
                        self._ac_options[key] = (
                            int(value) if value is not None else None
                        )
                    except (ValueError, TypeError):
                        _LOGGER.warning(
                            "Could not convert value '%s' to int for key '%s'. Storing as None.",
                            value,
                            key,
                        )
                        self._ac_options[key] = None
        elif isinstance(new_options_to_override, dict):
            for key, value in new_options_to_override.items():
                try:
                    self._ac_options[key] = int(value) if value is not None else None
                except (ValueError, TypeError):
                    _LOGGER.warning(
                        "Could not convert value '%s' to int for key '%s'. Storing as None.",
                        value,
                        key,
                    )
                    self._ac_options[key] = None
        else:
            _LOGGER.error("Invalid arguments passed to update_options.")
        # No return needed as it modifies self._ac_options directly

    # --- Properties for HA State ---
    @property
    def target_temperature(self) -> Optional[float]:
        """Return the target temperature based on internal state."""
        if self._ac_options.get("StHt") == 1:
            return 8.0
        set_temp = self._ac_options.get("SetTem")
        return float(set_temp) if set_temp is not None else None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the HVAC mode based on internal state."""
        pow_state = self._ac_options.get("Pow")
        if pow_state == 0:
            return HVACMode.OFF
        mod_index = self._ac_options.get("Mod")
        if mod_index is not None and 0 <= mod_index < len(HVAC_MODES):
            return HVAC_MODES[mod_index]
        _LOGGER.warning("Invalid HVAC mode index: %s", mod_index)
        return HVACMode.OFF  # Default to OFF if invalid

    @property
    def fan_mode(self) -> Optional[str]:
        """Return the fan mode based on internal state."""
        if self._ac_options.get("Tur") == 1:
            return "Turbo"
        if self._ac_options.get("Quiet") == 1:
            return "Quiet"
        speed_index = self._ac_options.get("WdSpd")
        if speed_index is not None and 0 <= speed_index < len(FAN_MODES):
            return FAN_MODES[speed_index]
        _LOGGER.warning("Invalid fan speed index: %s", speed_index)
        return None

    @property
    def swing_mode(self) -> Optional[str]:
        """Return the vertical swing mode based on internal state."""
        swing_index = self._ac_options.get("SwUpDn")
        if swing_index is not None and 0 <= swing_index < len(SWING_MODES):
            return SWING_MODES[swing_index]
        _LOGGER.warning("Invalid vertical swing index: %s", swing_index)
        return None

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the horizontal swing (preset) mode based on internal state."""
        if not self._horizontal_swing:  # Use stored flag
            return None
        preset_index = self._ac_options.get("SwingLfRig")
        if preset_index is not None and 0 <= preset_index < len(PRESET_MODES):
            return PRESET_MODES[preset_index]
        _LOGGER.warning("Invalid horizontal swing index: %s", preset_index)
        return None

    @property
    def lights_state(self) -> str:
        """Return the state of the lights."""
        lig_val = self._ac_options.get("Lig")
        return (
            STATE_ON if lig_val == 1 else STATE_OFF if lig_val == 0 else STATE_UNKNOWN
        )

    @property
    def xfan_state(self) -> str:
        """Return the state of XFan."""
        blo_val = self._ac_options.get("Blo")
        return (
            STATE_ON if blo_val == 1 else STATE_OFF if blo_val == 0 else STATE_UNKNOWN
        )

    @property
    def health_state(self) -> str:
        """Return the state of the Health mode."""
        health_val = self._ac_options.get("Health")
        return (
            STATE_ON
            if health_val == 1
            else STATE_OFF if health_val == 0 else STATE_UNKNOWN
        )

    @property
    def powersave_state(self) -> str:
        """Return the state of Power Save mode."""
        svst_val = self._ac_options.get("SvSt")
        return (
            STATE_ON if svst_val == 1 else STATE_OFF if svst_val == 0 else STATE_UNKNOWN
        )

    @property
    def sleep_state(self) -> str:
        """Return the state of Sleep mode."""
        swhslp_val = self._ac_options.get("SwhSlp")
        slpmod_val = self._ac_options.get("SlpMod")
        return (
            STATE_ON
            if (swhslp_val == 1 and slpmod_val == 1)
            else STATE_OFF if (swhslp_val == 0 and slpmod_val == 0) else STATE_UNKNOWN
        )

    @property
    def eightdegheat_state(self) -> str:
        """Return the state of 8 Degree Heat mode."""
        stht_val = self._ac_options.get("StHt")
        return (
            STATE_ON if stht_val == 1 else STATE_OFF if stht_val == 0 else STATE_UNKNOWN
        )

    @property
    def air_state(self) -> str:
        """Return the state of the Air mode/feature."""
        air_val = self._ac_options.get("Air")
        return (
            STATE_ON if air_val == 1 else STATE_OFF if air_val == 0 else STATE_UNKNOWN
        )

    @property
    def anti_direct_blow_state(self) -> str:
        """Return the state of Anti-Direct Blow."""
        # Note: This assumes the feature *exists*. The main climate class should handle availability.
        adb_val = self._ac_options.get("AntiDirectBlow")
        return (
            STATE_ON if adb_val == 1 else STATE_OFF if adb_val == 0 else STATE_UNKNOWN
        )

    # --- Helper Methods ---
    def get_internal_temp(self) -> Optional[float]:
        """Gets internal temperature from device state, applying offset if needed."""
        if not self._has_temp_sensor:  # Use stored flag
            return None
        temp_sen = self._ac_options.get("TemSen")
        if temp_sen is not None:
            temp_val = temp_sen if temp_sen <= TEMP_OFFSET else temp_sen - TEMP_OFFSET
            return float(temp_val)
        return None


async def detect_features(
    api: GreeDeviceApi, current_options: List[str]
) -> Tuple[bool, bool, bool, List[str]]:
    """Detect optional device features using API calls."""
    has_temp_sensor = False
    has_anti_direct_blow = False
    has_light_sensor = False
    options_to_fetch = list(current_options)  # Work on a copy

    # Detect Temp Sensor (TemSen)
    try:
        # Check if device responds to "TemSen" query
        response = await api.get_status(["TemSen"])
        # Check if response is not None and is a list (expected format)
        if response is not None and isinstance(response, list):
            has_temp_sensor = True
            _LOGGER.debug("Internal temperature sensor detected.")
            if "TemSen" not in options_to_fetch:
                options_to_fetch.append("TemSen")
        else:
            _LOGGER.debug(
                "Internal temperature sensor not detected or invalid response."
            )
    except (socket.timeout, socket.error, ConnectionError, ValueError, TypeError) as e:
        _LOGGER.warning("Error detecting internal temperature sensor: %s", e)
        # Keep has_temp_sensor as False

    # Detect Anti-Direct Blow (AntiDirectBlow)
    try:
        response = await api.get_status(["AntiDirectBlow"])
        if response is not None and isinstance(response, list):
            has_anti_direct_blow = True
            _LOGGER.debug("Anti-direct blow feature detected.")
            if "AntiDirectBlow" not in options_to_fetch:
                options_to_fetch.append("AntiDirectBlow")
        else:
            _LOGGER.debug("Anti-direct blow feature not detected or invalid response.")
    except (socket.timeout, socket.error, ConnectionError, ValueError, TypeError) as e:
        _LOGGER.warning("Error detecting anti-direct blow feature: %s", e)
        # Keep has_anti_direct_blow as False

    # Detect Light Sensor (LigSen)
    try:
        response = await api.get_status(["LigSen"])
        if response is not None and isinstance(response, list):
            has_light_sensor = True
            _LOGGER.debug("Light sensor detected.")
            if "LigSen" not in options_to_fetch:
                options_to_fetch.append("LigSen")
        else:
            _LOGGER.debug("Light sensor not detected or invalid response.")
    except (socket.timeout, socket.error, ConnectionError, ValueError, TypeError) as e:
        _LOGGER.warning("Error detecting light sensor: %s", e)
        # Keep has_light_sensor as False

    return has_temp_sensor, has_anti_direct_blow, has_light_sensor, options_to_fetch
