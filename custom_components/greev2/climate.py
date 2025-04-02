"""Home Assistant platform for Gree Climate V2 devices."""

import base64
import logging
from datetime import timedelta

# Need Optional for type hints, Union for set_ac_options
from typing import Any, Dict, List, Optional, Union

# Third-party imports
import voluptuous as vol
from Crypto.Cipher import AES

# Home Assistant imports
import homeassistant.helpers.config_validation as cv
from homeassistant.components.climate import (
    # PLATFORM_SCHEMA is no longer used
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)

# Import HA constants used directly
from homeassistant.const import (
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PORT, # Keep for const default reference
    CONF_TIMEOUT, # Keep for const default reference
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event, # Keep for potential future use in options flow
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import format_mac


# Local imports
from .device_api import GreeDeviceApi
# Import constants needed for defaults and config keys
from . import const # Keep this top-level import
from .const import (
    CONF_ENCRYPTION_VERSION,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DEFAULT_TARGET_TEMP_STEP,
    # Import correct mode lists and new defaults
    HVAC_MODES, # Corrected name
    FAN_MODES, # Corrected name
    SWING_MODES, # Corrected name
    PRESET_MODES, # Corrected name
    DEFAULT_HORIZONTAL_SWING, # Corrected import
    DEFAULT_DISABLE_AVAILABILITY_CHECK, # Corrected import
    DEFAULT_MAX_ONLINE_ATTEMPTS, # Corrected import
    MIN_TEMP,
    MAX_TEMP,
    SUPPORT_FLAGS,
    TEMP_OFFSET, # Keep if used in update_ha_current_temperature
)


# Simplify CipherType to Any for broader compatibility
CipherType = Any

# REQUIREMENTS list is obsolete, managed by manifest.json

_LOGGER = logging.getLogger(__name__)


# PLATFORM_SCHEMA is removed as configuration is via Config Flow


# async_setup_platform is removed as setup is via Config Flow


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Gree climate platform from a config entry."""
    _LOGGER.info("Setting up Gree climate platform entry: %s", entry.entry_id)

    # Instantiate the GreeClimate entity using the config entry
    # Pass hass and the entry itself to the constructor
    device = GreeClimate(hass, entry)

    # Add the entity to Home Assistant
    async_add_entities([device])


class GreeClimate(ClimateEntity):
    """Representation of a Gree Climate device."""

    # Declare types for instance variables
    _attr_name: str
    _attr_unique_id: str
    _attr_should_poll: bool = True  # Default should_poll
    _attr_temperature_unit: str = UnitOfTemperature.CELSIUS  # Use HA Constant
    _attr_hvac_modes: List[HVACMode]
    _attr_fan_modes: List[str]
    _attr_swing_modes: List[str]
    _attr_preset_modes: Optional[List[str]]  # Can be None if horizontal_swing is false
    _attr_target_temperature_step: float
    _attr_min_temp: float = float(MIN_TEMP)
    _attr_max_temp: float = float(MAX_TEMP)
    _attr_supported_features: ClimateEntityFeature = SUPPORT_FLAGS  # Base flags

    # Internal state
    _ip_addr: str
    _port: int
    _mac_addr: str  # Store as string
    _timeout: int
    _device_online: Optional[bool] = None
    _online_attempts: int = 0
    _max_online_attempts: int
    _disable_available_check: bool

    _target_temperature: Optional[float] = None
    _hvac_mode: HVACMode = HVACMode.OFF
    _fan_mode: Optional[str] = None
    _swing_mode: Optional[str] = None
    _preset_mode: Optional[str] = None

    # Optional entity IDs are no longer configured via YAML/init
    # These might be reintroduced later via Options Flow if needed
    # _temp_sensor_entity_id: Optional[str] = None
    # _lights_entity_id: Optional[str] = None
    # ... etc ...

    _horizontal_swing: bool
    _has_temp_sensor: Optional[bool] = None
    _has_anti_direct_blow: Optional[bool] = None
    _has_light_sensor: Optional[bool] = None

    _current_temperature: Optional[float] = None
    _current_lights: Optional[str] = None  # STATE_ON/STATE_OFF/STATE_UNKNOWN
    _current_xfan: Optional[str] = None
    _current_health: Optional[str] = None
    _current_powersave: Optional[str] = None
    _current_sleep: Optional[str] = None
    _current_eightdegheat: Optional[str] = None
    _current_air: Optional[str] = None
    _current_anti_direct_blow: Optional[str] = None

    _first_time_run: bool = True
    # Flags previously controlled by optional entities - manage via Options Flow later?
    _enable_light_sensor: bool = False
    _auto_light: bool = False
    _auto_xfan: bool = False

    encryption_version: int
    _encryption_key: Optional[bytes] = None # Key is retrieved during bind
    _uid: int = 0 # UID not used in config flow setup
    _api: GreeDeviceApi
    # CIPHER is deprecated, managed by _api

    # Type hint for _ac_options - values seem to be mostly int/None
    _ac_options: Dict[str, Optional[int]]
    _options_to_fetch: List[str]
    _preset_modes_list: List[str]  # Added for storing original list

    # Deprecated, remove if not used by HA core anymore
    _enable_turn_on_off_backwards_compatibility: bool = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Gree Climate device from a config entry."""
        _LOGGER.info("Initialize the GREE climate device from config entry: %s", entry.entry_id)
        self.hass = hass
        self._entry = entry # Store entry for potential future use (e.g., options flow)

        # --- Extract data from ConfigEntry ---
        data = entry.data
        self._attr_name = data.get(CONF_NAME, DEFAULT_NAME)
        self._ip_addr = data[CONF_HOST] # Required field in config flow
        self._mac_addr = format_mac(data[CONF_MAC]) # Required, format it
        # Get encryption version, default to 2 if missing (should be present from config flow)
        try:
            self.encryption_version = int(data.get(CONF_ENCRYPTION_VERSION, "2"))
        except (ValueError, TypeError):
            _LOGGER.warning("Invalid encryption version '%s' in config entry, defaulting to 2", data.get(CONF_ENCRYPTION_VERSION))
            self.encryption_version = 2

        # --- Use Defaults for other parameters ---
        # TODO: Consider making these configurable via Options Flow later
        self._port = DEFAULT_PORT
        self._timeout = DEFAULT_TIMEOUT
        self._attr_target_temperature_step = DEFAULT_TARGET_TEMP_STEP
        # Use corrected constant names for modes/settings
        self._attr_hvac_modes = HVAC_MODES
        self._attr_fan_modes = FAN_MODES
        self._attr_swing_modes = SWING_MODES
        self._preset_modes_list = PRESET_MODES
        self._horizontal_swing = DEFAULT_HORIZONTAL_SWING
        self._disable_available_check = DEFAULT_DISABLE_AVAILABILITY_CHECK
        self._max_online_attempts = DEFAULT_MAX_ONLINE_ATTEMPTS

        # --- Set initial internal state ---
        self._attr_unique_id = entry.unique_id or f"climate.gree_{self._mac_addr}" # Use entry unique_id if available
        self._device_online = None
        self._online_attempts = 0
        self._target_temperature = None
        self._hvac_mode = HVACMode.OFF
        self._fan_mode = None
        self._swing_mode = None
        self._preset_mode = None
        self._has_temp_sensor = None
        self._has_anti_direct_blow = None
        self._has_light_sensor = None
        self._current_temperature = None
        self._current_lights = None
        self._current_xfan = None
        self._current_health = None
        self._current_powersave = None
        self._current_sleep = None
        self._current_eightdegheat = None
        self._current_air = None
        self._current_anti_direct_blow = None
        self._first_time_run = True
        self._encryption_key = None # Key will be obtained during bind

        # --- Configure Preset Modes based on horizontal swing ---
        if self._horizontal_swing:
            self._attr_preset_modes = self._preset_modes_list
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE
        else:
            self._attr_preset_modes = None

        # --- Instantiate the API handler ---
        # Key is not passed here; it will be obtained during the first update/bind
        self._api = GreeDeviceApi(
            host=self._ip_addr,
            port=self._port,
            mac=self._mac_addr,
            timeout=self._timeout,
            encryption_key=None, # Key obtained via bind_and_get_key
            encryption_version=self.encryption_version,
        )

        # --- Initialize _ac_options and fetch list ---
        self._ac_options = {
            "Pow": None, "Mod": None, "SetTem": None, "WdSpd": None, "Air": None,
            "Blo": None, "Health": None, "SwhSlp": None, "Lig": None, "SwingLfRig": None,
            "SwUpDn": None, "Quiet": None, "Tur": None, "StHt": None, "TemUn": None,
            "HeatCoolType": None, "TemRec": None, "SvSt": None, "SlpMod": None,
            # Add optional keys that might be fetched later
            "TemSen": None, "AntiDirectBlow": None, "LigSen": None,
        }
        self._options_to_fetch = [
            "Pow", "Mod", "SetTem", "WdSpd", "Air", "Blo", "Health", "SwhSlp", "Lig",
            "SwingLfRig", "SwUpDn", "Quiet", "Tur", "StHt", "TemUn", "HeatCoolType",
            "TemRec", "SvSt", "SlpMod",
        ]

        # State change listener setup removed - handled by Options Flow if needed

    def set_ac_options(
        self,
        ac_options: Dict[str, Optional[int]],
        new_options_to_override: Union[
            List[str], Dict[str, Any]
        ],  # Can be list or dict
        option_values_to_override: Optional[
            List[Any]
        ] = None,  # Should be List if new_options_to_override is List
    ) -> Dict[str, Optional[int]]:
        """Update the internal _ac_options dictionary."""
        if option_values_to_override is not None and isinstance(
            new_options_to_override, list
        ):
            # _LOGGER.debug("Setting ac_options with retrieved HVAC values") # Reduce noise
            if len(new_options_to_override) != len(option_values_to_override):
                _LOGGER.error("set_ac_options error: Mismatched lengths for keys (%d) and values (%d)", len(new_options_to_override), len(option_values_to_override))
            else:
                for i, key in enumerate(new_options_to_override):
                    value = option_values_to_override[i]
                    try: ac_options[key] = int(value) if value is not None else None
                    except (ValueError, TypeError):
                        _LOGGER.warning("Could not convert value '%s' to int for key '%s'. Storing as None.", value, key)
                        ac_options[key] = None
        elif isinstance(new_options_to_override, dict):
            # _LOGGER.debug("Overwriting ac_options with new settings") # Reduce noise
            for key, value in new_options_to_override.items():
                try: ac_options[key] = int(value) if value is not None else None
                except (ValueError, TypeError):
                    _LOGGER.warning("Could not convert value '%s' to int for key '%s'. Storing as None.", value, key)
                    ac_options[key] = None
                # _LOGGER.debug("Overwriting %s: %s", key, ac_options[key]) # Reduce noise
        else: _LOGGER.error("Invalid arguments passed to set_ac_options.")
        return ac_options

    def update_ha_target_temperature(self) -> None:
        """Update HA target temperature based on internal state."""
        if self._ac_options.get("StHt") == 1: self._target_temperature = 8.0
        else:
            set_temp = self._ac_options.get("SetTem")
            self._target_temperature = float(set_temp) if set_temp is not None else None

    def update_ha_options(self) -> None:
        """Update internal state vars for various options based on _ac_options."""
        lig_val = self._ac_options.get("Lig"); self._current_lights = STATE_ON if lig_val == 1 else STATE_OFF if lig_val == 0 else STATE_UNKNOWN
        blo_val = self._ac_options.get("Blo"); self._current_xfan = STATE_ON if blo_val == 1 else STATE_OFF if blo_val == 0 else STATE_UNKNOWN
        health_val = self._ac_options.get("Health"); self._current_health = STATE_ON if health_val == 1 else STATE_OFF if health_val == 0 else STATE_UNKNOWN
        svst_val = self._ac_options.get("SvSt"); self._current_powersave = STATE_ON if svst_val == 1 else STATE_OFF if svst_val == 0 else STATE_UNKNOWN
        swhslp_val = self._ac_options.get("SwhSlp"); slpmod_val = self._ac_options.get("SlpMod"); self._current_sleep = STATE_ON if (swhslp_val == 1 and slpmod_val == 1) else STATE_OFF if (swhslp_val == 0 and slpmod_val == 0) else STATE_UNKNOWN
        stht_val = self._ac_options.get("StHt"); self._current_eightdegheat = STATE_ON if stht_val == 1 else STATE_OFF if stht_val == 0 else STATE_UNKNOWN
        air_val = self._ac_options.get("Air"); self._current_air = STATE_ON if air_val == 1 else STATE_OFF if air_val == 0 else STATE_UNKNOWN
        if self._has_anti_direct_blow:
            adb_val = self._ac_options.get("AntiDirectBlow"); self._current_anti_direct_blow = STATE_ON if adb_val == 1 else STATE_OFF if adb_val == 0 else STATE_UNKNOWN

    def update_ha_hvac_mode(self) -> None:
        """Update HA HVAC mode based on internal state."""
        pow_state = self._ac_options.get("Pow")
        if pow_state == 0: self._hvac_mode = HVACMode.OFF
        else:
            mod_index = self._ac_options.get("Mod")
            if mod_index is not None and 0 <= mod_index < len(self._attr_hvac_modes): self._hvac_mode = self._attr_hvac_modes[mod_index]
            else: _LOGGER.warning("Invalid HVAC mode index: %s", mod_index); self._hvac_mode = HVACMode.OFF

    def update_ha_current_swing_mode(self) -> None:
        """Update HA vertical swing mode based on internal state."""
        swing_index = self._ac_options.get("SwUpDn")
        if swing_index is not None and 0 <= swing_index < len(self._attr_swing_modes): self._swing_mode = self._attr_swing_modes[swing_index]
        else: _LOGGER.warning("Invalid vertical swing index: %s", swing_index); self._swing_mode = None

    def update_ha_current_preset_mode(self) -> None:
        """Update HA horizontal swing (preset) mode based on internal state."""
        if not self._horizontal_swing: self._preset_mode = None; return
        preset_index = self._ac_options.get("SwingLfRig")
        if self._attr_preset_modes and preset_index is not None and 0 <= preset_index < len(self._attr_preset_modes): self._preset_mode = self._attr_preset_modes[preset_index]
        else: _LOGGER.warning("Invalid horizontal swing index: %s", preset_index); self._preset_mode = None

    def update_ha_fan_mode(self) -> None:
        """Update HA fan mode based on internal state."""
        if self._ac_options.get("Tur") == 1: self._fan_mode = "Turbo"
        elif self._ac_options.get("Quiet") == 1: self._fan_mode = "Quiet"
        else:
            speed_index = self._ac_options.get("WdSpd")
            if speed_index is not None and 0 <= speed_index < len(self._attr_fan_modes): self._fan_mode = self._attr_fan_modes[speed_index]
            else: _LOGGER.warning("Invalid fan speed index: %s", speed_index); self._fan_mode = None

    def update_ha_current_temperature(self) -> None:
        """Update HA current temperature based on internal state."""
        if self._has_temp_sensor:
            temp_sen = self._ac_options.get("TemSen")
            if temp_sen is not None:
                temp_val = temp_sen if temp_sen <= TEMP_OFFSET else temp_sen - TEMP_OFFSET
                self._current_temperature = float(temp_val)
            else: self._current_temperature = None
        else: self._current_temperature = None

    def update_ha_state_to_current_ac_state(self) -> None:
        """Update all HA state properties based on the current _ac_options."""
        self.update_ha_target_temperature()
        self.update_ha_options()
        self.update_ha_hvac_mode()
        self.update_ha_current_swing_mode()
        if self._horizontal_swing: self.update_ha_current_preset_mode()
        self.update_ha_fan_mode()
        self.update_ha_current_temperature()

    def sync_state(self, ac_options: Optional[Dict[str, Any]] = None) -> None:
        """Fetch state, update internal state, optionally send commands, update HA state."""
        if ac_options is None: ac_options = {}

        # --- Feature Detection --- (Simplified)
        if self._has_temp_sensor is None:
            try: self._has_temp_sensor = self._api.get_status(["TemSen"]) is not None; _LOGGER.info("Temp sensor detected: %s", self._has_temp_sensor)
            except Exception: self._has_temp_sensor = False
            if self._has_temp_sensor and "TemSen" not in self._options_to_fetch: self._options_to_fetch.append("TemSen")
        if self._has_anti_direct_blow is None:
             try: self._has_anti_direct_blow = self._api.get_status(["AntiDirectBlow"]) is not None; _LOGGER.info("Anti-direct blow detected: %s", self._has_anti_direct_blow)
             except Exception: self._has_anti_direct_blow = False
             if self._has_anti_direct_blow and "AntiDirectBlow" not in self._options_to_fetch: self._options_to_fetch.append("AntiDirectBlow")
        if self._has_light_sensor is None:
            try: self._has_light_sensor = self._api.get_status(["LigSen"]) is not None; _LOGGER.info("Light sensor detected: %s", self._has_light_sensor)
            except Exception: self._has_light_sensor = False
            if self._has_light_sensor and "LigSen" not in self._options_to_fetch: self._options_to_fetch.append("LigSen")

        # --- Fetch Current State ---
        # Store expected length *before* calling get_status
        expected_len = len(self._options_to_fetch)
        try:
            received_data_list = self._api.get_status(self._options_to_fetch)
            if received_data_list is None: raise ConnectionError("API get_status returned None")
            if not isinstance(received_data_list, list): raise ConnectionError(f"API returned unexpected type: {type(received_data_list)}")
            # Compare received length against the length *before* feature detection might have added keys
            if len(received_data_list) != expected_len: raise ConnectionError(f"API list length mismatch: {len(received_data_list)} vs {expected_len}")
        except Exception as e:
            if not self._disable_available_check:
                self._online_attempts += 1
                if self._online_attempts >= self._max_online_attempts and self._device_online is not False:
                    _LOGGER.info("Device %s offline after %s attempts. Error: %s", self.name, self._max_online_attempts, e)
                    self._device_online = False
            return

        # --- Connection Success ---
        if not self._disable_available_check:
            if self._device_online is not True: _LOGGER.info("Device %s back online.", self.name)
            self._device_online = True; self._online_attempts = 0

        # --- Update Internal State ---
        # Use expected_len to slice received_data_list if feature detection added keys
        # This ensures set_ac_options receives lists of matching lengths
        self._ac_options = self.set_ac_options(self._ac_options, self._options_to_fetch[:expected_len], received_data_list[:expected_len])
        if ac_options: self._ac_options = self.set_ac_options(self._ac_options, ac_options)

        # --- Send Commands (if needed) ---
        if not self._first_time_run and ac_options:
            opt_keys, p_values = list(ac_options.keys()), list(ac_options.values())
            _LOGGER.debug("Sending command: %s = %s", opt_keys, p_values)
            try:
                if not self._api.send_command(opt_keys, p_values): _LOGGER.error("API send_command failed.")
            except Exception as e: _LOGGER.error("Error sending command: %s", e, exc_info=True)
        elif self._first_time_run: self._first_time_run = False

        # --- Update HA State ---
        self.update_ha_state_to_current_ac_state()

    # --- Properties ---
    @property
    def current_temperature(self) -> Optional[float]: return self._current_temperature
    @property
    def target_temperature(self) -> Optional[float]: return self._target_temperature
    @property
    def hvac_mode(self) -> HVACMode: return self._hvac_mode
    @property
    def fan_mode(self) -> Optional[str]: return self._fan_mode
    @property
    def swing_mode(self) -> Optional[str]: return self._swing_mode
    @property
    def preset_mode(self) -> Optional[str]: return self._preset_mode if self._horizontal_swing else None
    @property
    def available(self) -> bool: return True if self._disable_available_check else bool(self._device_online)

    # --- Service Methods ---
    def set_temperature(self, **kwargs: Any) -> None:
        temperature: Optional[float] = kwargs.get(ATTR_TEMPERATURE)
        _LOGGER.debug("Service call: set_temperature(%s)", temperature)
        if temperature is not None:
            if self._ac_options.get("Pow") != 0:
                temp_int = int(temperature)
                if MIN_TEMP <= temp_int <= MAX_TEMP: self.sync_state({"SetTem": temp_int})
                else: _LOGGER.warning("Temp %s out of range (%d-%d)", temperature, MIN_TEMP, MAX_TEMP)
            else: _LOGGER.warning("Cannot set temperature when device is off.")
        else: _LOGGER.warning("set_temperature called without temperature value.")

    def set_swing_mode(self, swing_mode: str) -> None:
        _LOGGER.debug("Service call: set_swing_mode(%s)", swing_mode)
        if self._ac_options.get("Pow") != 0:
            if swing_mode in self._attr_swing_modes: self.sync_state({"SwUpDn": self._attr_swing_modes.index(swing_mode)})
            else: _LOGGER.error("Invalid swing mode requested: %s", swing_mode)
        else: _LOGGER.warning("Cannot set swing mode when device is off.")

    def set_preset_mode(self, preset_mode: str) -> None:
        _LOGGER.debug("Service call: set_preset_mode(%s)", preset_mode)
        if not self._horizontal_swing: _LOGGER.warning("Horizontal swing not supported."); return
        if self._ac_options.get("Pow") != 0:
            if self._attr_preset_modes and preset_mode in self._attr_preset_modes: self.sync_state({"SwingLfRig": self._attr_preset_modes.index(preset_mode)})
            else: _LOGGER.error("Invalid preset mode requested: %s", preset_mode)
        else: _LOGGER.warning("Cannot set preset mode when device is off.")

    def set_fan_mode(self, fan_mode: str) -> None:
        _LOGGER.debug("Service call: set_fan_mode(%s)", fan_mode)
        if self._ac_options.get("Pow") != 0:
            command: Dict[str, int] = {"Tur": 0, "Quiet": 0}
            fan_mode_lower = fan_mode.lower()
            if fan_mode_lower == "turbo": command["Tur"] = 1
            elif fan_mode_lower == "quiet": command["Quiet"] = 1
            elif fan_mode in self._attr_fan_modes: command["WdSpd"] = self._attr_fan_modes.index(fan_mode)
            else: _LOGGER.error("Invalid fan mode requested: %s", fan_mode); return
            self.sync_state(command)
        else: _LOGGER.warning("Cannot set fan mode when device is off.")

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        _LOGGER.debug("Service call: set_hvac_mode(%s)", hvac_mode)
        command: Dict[str, int] = {}
        if hvac_mode == HVACMode.OFF: command["Pow"] = 0
        else:
            if hvac_mode in self._attr_hvac_modes:
                command["Pow"] = 1; command["Mod"] = self._attr_hvac_modes.index(hvac_mode)
            else: _LOGGER.error("Invalid HVAC mode requested: %s", hvac_mode); return
        self.sync_state(command)

    def turn_on(self) -> None: _LOGGER.debug("Service call: turn_on()"); self.sync_state({"Pow": 1})
    def turn_off(self) -> None: _LOGGER.debug("Service call: turn_off()"); self.sync_state({"Pow": 0})

    # --- HA Lifecycle Methods ---
    async def async_added_to_hass(self) -> None:
        _LOGGER.debug("Gree climate device %s added to hass", self.name)
        await self.async_update()

    async def async_update(self) -> None: await self.hass.async_add_executor_job(self._update_sync)

    def _update_sync(self) -> None:
        """Synchronous part of update logic. Handles binding and state sync."""
        if not self._api._is_bound:
            # _LOGGER.info("API not bound for %s, attempting bind...", self.name) # Reduce noise
            try:
                if not self._api.bind_and_get_key():
                    if not self._disable_available_check: self._device_online = False; return
                else:
                    _LOGGER.info("Binding successful for %s.", self.name)
                    self._encryption_key = self._api._encryption_key
                    if self._encryption_key is not None: self._api.update_encryption_key(self._encryption_key)
                    else: _LOGGER.error("Binding ok but key is None for %s.", self.name)
            except Exception as e:
                _LOGGER.error("Exception during binding for %s: %s", self.name, e)
                if not self._disable_available_check: self._device_online = False; return

        if self._api._is_bound:
            try: self.sync_state()
            except Exception as e:
                _LOGGER.error("Error during sync_state for %s: %s", self.name, e)
                if not self._disable_available_check: self._device_online = False
        elif not self._disable_available_check: self._device_online = False # Mark offline if not bound after attempt
