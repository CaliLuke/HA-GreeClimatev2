# pylint: disable=protected-access
"""Home Assistant platform for Gree Climate V2 devices."""

import logging
import socket  # Keep socket

# Need Optional for type hints, Union for set_ac_options
from typing import Any, Dict, List, Optional, Union

# Third-party imports
# import voluptuous as vol # Unused
# from Crypto.Cipher import AES # Unused

# Home Assistant imports
# import homeassistant.helpers.config_validation as cv # Unused
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
    # CONF_PORT, # Unused
    # CONF_TIMEOUT, # Unused
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,  # Keep for potential future use in options flow
)

# from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType # Unused
from homeassistant.config_entries import ConfigEntry

# Import format_mac and DeviceInfo
from homeassistant.helpers.device_registry import format_mac, DeviceInfo


# Local imports
from .device_api import GreeDeviceApi
from .climate_helpers import GreeClimateState, detect_features

# Import constants needed for defaults and config keys
# from . import const # Unused
from .const import (
    CONF_ENCRYPTION_VERSION,
    CONF_TEMP_SENSOR,  # Added
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DEFAULT_TARGET_TEMP_STEP,
    # Import correct mode lists and new defaults
    HVAC_MODES,  # Corrected name
    FAN_MODES,  # Corrected name
    SWING_MODES,  # Corrected name
    PRESET_MODES,  # Corrected name
    DEFAULT_HORIZONTAL_SWING,  # Corrected import
    DEFAULT_DISABLE_AVAILABILITY_CHECK,  # Corrected import
    DEFAULT_MAX_ONLINE_ATTEMPTS,  # Corrected import
    MIN_TEMP,
    MAX_TEMP,
    SUPPORT_FLAGS,
    TEMP_OFFSET,  # Keep if used in update_ha_current_temperature
    DOMAIN,  # Import DOMAIN for device info
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


# pylint: disable=too-many-instance-attributes, too-many-public-methods, abstract-method
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
    _attr_device_info: DeviceInfo  # Added for area support

    # Internal state (Config/API related)
    _ip_addr: str
    _port: int
    _mac_addr: str  # Store as string
    _timeout: int
    _device_online: Optional[bool] = None
    _online_attempts: int = 0
    _max_online_attempts: int
    _disable_available_check: bool
    _temp_sensor_entity_id: Optional[str]  # Added back
    _horizontal_swing: bool
    _first_time_run: bool = True
    encryption_version: int
    _encryption_key: Optional[bytes] = None
    _uid: int = 0
    _api: GreeDeviceApi
    _options_to_fetch: List[str]
    _preset_modes_list: List[str]  # Keep for preset mode configuration

    # State managed by GreeClimateState helper
    _state: GreeClimateState

    # Feature flags (determined during runtime)
    _has_temp_sensor: Optional[bool] = None
    _has_anti_direct_blow: Optional[bool] = None
    _has_light_sensor: Optional[bool] = None

    # Current temperature (handled separately due to external sensor)
    _current_temperature: Optional[float] = None

    # Deprecated/Unused?
    _enable_light_sensor: bool = False
    _auto_light: bool = False
    _auto_xfan: bool = False
    _enable_turn_on_off_backwards_compatibility: bool = False

    # pylint: disable=too-many-statements
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Gree Climate device from a config entry."""
        _LOGGER.info(
            "Initialize the GREE climate device from config entry: %s", entry.entry_id
        )
        self.hass = hass
        self._entry = entry

        # --- Extract data from ConfigEntry ---
        data = entry.data
        self._attr_name = data.get(CONF_NAME, DEFAULT_NAME)
        self._ip_addr = data[CONF_HOST]
        self._mac_addr = format_mac(data[CONF_MAC])
        area_id = data.get("area_id")
        # Extract optional temp sensor entity ID
        self._temp_sensor_entity_id = data.get(CONF_TEMP_SENSOR)
        try:
            self.encryption_version = int(data.get(CONF_ENCRYPTION_VERSION, "2"))
        except (ValueError, TypeError):
            _LOGGER.warning(
                "Invalid encryption version '%s' in config entry, defaulting to 2",
                data.get(CONF_ENCRYPTION_VERSION),
            )
            self.encryption_version = 2

        # --- Use Defaults for other parameters ---
        self._port = DEFAULT_PORT
        self._timeout = DEFAULT_TIMEOUT
        self._attr_target_temperature_step = DEFAULT_TARGET_TEMP_STEP
        self._attr_hvac_modes = HVAC_MODES
        self._attr_fan_modes = FAN_MODES
        self._attr_swing_modes = SWING_MODES
        self._preset_modes_list = PRESET_MODES
        self._horizontal_swing = DEFAULT_HORIZONTAL_SWING
        self._disable_available_check = DEFAULT_DISABLE_AVAILABILITY_CHECK
        self._max_online_attempts = DEFAULT_MAX_ONLINE_ATTEMPTS

        # --- Set initial internal state (flags, identifiers, etc.) ---
        self._attr_unique_id = entry.unique_id or f"climate.gree_{self._mac_addr}"
        self._device_online = None
        self._online_attempts = 0
        # _target_temperature, _hvac_mode, _fan_mode, _swing_mode, _preset_mode
        # will be derived from _state later. Initialize basic ones.
        # self._hvac_mode = HVACMode.OFF # Start as OFF - Now derived from _state
        self._has_temp_sensor = None  # Will be detected
        self._has_anti_direct_blow = None  # Will be detected
        self._has_light_sensor = None  # Will be detected
        self._current_temperature = None  # Keep for external sensor logic
        self._first_time_run = True
        self._encryption_key = None

        # --- Configure Preset Modes based on horizontal swing ---
        if self._horizontal_swing:
            self._attr_preset_modes = self._preset_modes_list
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE
        else:
            self._attr_preset_modes = None

        # --- Set Device Info ---
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._mac_addr)},
            name=self._attr_name,
            manufacturer="Gree",
            suggested_area=area_id,
            configuration_url=f"http://{self._ip_addr}",
        )

        # --- Instantiate the API handler ---
        self._api = GreeDeviceApi(
            host=self._ip_addr,
            port=self._port,
            mac=self._mac_addr,
            timeout=self._timeout,
            encryption_key=None,
            encryption_version=self.encryption_version,
        )

        # --- Initialize State Manager ---
        initial_ac_options = {  # Define the initial dictionary structure
            "Pow": 0,
            "Mod": None,
            "SetTem": None,
            "WdSpd": None,
            "Air": None,  # Start Pow=0 (Off)
            "Blo": None,
            "Health": None,
            "SwhSlp": None,
            "Lig": None,
            "SwingLfRig": None,
            "SwUpDn": None,
            "Quiet": None,
            "Tur": None,
            "StHt": None,
            "TemUn": None,
            "HeatCoolType": None,
            "TemRec": None,
            "SvSt": None,
            "SlpMod": None,
            "TemSen": None,
            "AntiDirectBlow": None,
            "LigSen": None,
        }
        # Pass flags needed by GreeClimateState properties/methods
        # Pass False for has_temp_sensor initially, it will be updated after detection.
        self._state = GreeClimateState(
            initial_options=initial_ac_options,
            horizontal_swing=self._horizontal_swing,
            has_temp_sensor=False,  # Initial value, will be updated by detect_features
        )

        # --- Initialize fetch list ---
        # This list might be modified by feature detection later
        self._options_to_fetch = [
            "Pow",
            "Mod",
            "SetTem",
            "WdSpd",
            "Air",
            "Blo",
            "Health",
            "SwhSlp",
            "Lig",
            "SwingLfRig",
            "SwUpDn",
            "Quiet",
            "Tur",
            "StHt",
            "TemUn",
            "HeatCoolType",
            "TemRec",
            "SvSt",
            "SlpMod",
        ]

        # --- Setup state change listeners ---
        # Listener registration moved to async_added_to_hass

    # Obsolete methods removed

    # pylint: disable=too-many-statements, too-many-branches
    async def _async_sync_state(
        self, ac_options_to_send: Optional[Dict[str, Any]] = None
    ) -> None:  # Renamed and made async, changed arg name
        """Fetch state, update internal state, optionally send commands, update HA state."""
        if ac_options_to_send is None:
            ac_options_to_send = {}

        # --- Feature Detection (only if not done before) ---
        if self._has_temp_sensor is None:  # Check if detection is needed
            _LOGGER.debug("Performing initial feature detection...")
            try:
                (
                    detected_temp,
                    detected_adb,
                    detected_light,
                    updated_options_list,
                ) = await detect_features(
                    self._api, self._options_to_fetch
                )  # Use helper

                self._has_temp_sensor = detected_temp
                self._has_anti_direct_blow = detected_adb
                self._has_light_sensor = detected_light
                self._options_to_fetch = (
                    updated_options_list  # Update fetch list based on detection
                )

                # Update the state helper with the detected temp sensor status
                # This assumes _state is already initialized in __init__
                self._state._has_temp_sensor = (
                    self._has_temp_sensor
                )  # Update flag in state helper

                _LOGGER.info(
                    "Feature detection results: Temp=%s, ADB=%s, Light=%s",
                    self._has_temp_sensor,
                    self._has_anti_direct_blow,
                    self._has_light_sensor,
                )
                _LOGGER.debug("Updated options to fetch: %s", self._options_to_fetch)

            except (
                socket.timeout,
                socket.error,
                ConnectionError,
                ValueError,
                TypeError,
            ) as e:
                _LOGGER.error("Error during initial feature detection: %s", e)
                # Assume features are false if detection fails
                self._has_temp_sensor = False
                self._has_anti_direct_blow = False
                self._has_light_sensor = False
                if hasattr(self, "_state"):  # Ensure _state exists before accessing
                    self._state._has_temp_sensor = False  # Update state helper too

        # --- Fetch Current State ---
        try:
            received_data_list = await self._api.get_status(self._options_to_fetch)
            if received_data_list is None:
                raise ConnectionError("API get_status returned None")
            if not isinstance(received_data_list, list):
                raise ConnectionError(
                    f"API returned unexpected type: {type(received_data_list)}"
                )
            if len(received_data_list) != len(self._options_to_fetch):
                _LOGGER.error(
                    "API list length mismatch: Received %d values for %d requested options. Opts: %s, Rcvd: %s",
                    len(received_data_list),
                    len(self._options_to_fetch),
                    self._options_to_fetch,
                    received_data_list,
                )
                raise ConnectionError(
                    f"API list length mismatch: {len(received_data_list)} vs {len(self._options_to_fetch)}"
                )

        except (
            socket.timeout,
            socket.error,
            ConnectionError,
            ValueError,
            TypeError,
        ) as e:  # Catch specific errors
            if not self._disable_available_check:
                self._online_attempts += 1
                if (
                    self._online_attempts >= self._max_online_attempts
                    and self._device_online is not False
                ):
                    _LOGGER.info(
                        "Device %s offline after %s attempts. Error: %s",
                        self.name,
                        self._max_online_attempts,
                        e,
                    )
                    self._device_online = False
            return  # Exit if fetch fails

        # --- Connection Success ---
        if not self._disable_available_check:
            if self._device_online is not True:
                _LOGGER.info("Device %s back online.", self.name)
            self._device_online = True
            self._online_attempts = 0

        # --- Update Internal State using Helper ---
        # Update state with fetched values
        self._state.update_options(
            self._options_to_fetch, received_data_list
        )  # Use helper
        # If specific options were sent (e.g., from a service call), update state with those too
        if ac_options_to_send:
            self._state.update_options(ac_options_to_send)  # Use helper

        # --- Send Commands (if needed) ---
        if not self._first_time_run and ac_options_to_send:
            opt_keys, p_values = list(ac_options_to_send.keys()), list(
                ac_options_to_send.values()
            )
            _LOGGER.debug("Sending command: %s = %s", opt_keys, p_values)
            try:
                send_result = await self._api.send_command(opt_keys, p_values)
                if not send_result:
                    _LOGGER.error("API send_command failed.")
            except (
                socket.timeout,
                socket.error,
                ConnectionError,
                ValueError,
                TypeError,
            ) as e:  # Catch specific errors
                _LOGGER.error("Error sending command: %s", e, exc_info=True)
        elif self._first_time_run:
            self._first_time_run = False

        # --- Update HA State ---
        # HA state is now derived directly from properties reading self._state

    # --- Properties ---
    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        # If external sensor used, return its value stored in self._current_temperature
        if self._temp_sensor_entity_id:
            return self._current_temperature
        # Otherwise, get from internal state helper
        return self._state.get_internal_temp()

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        return self._state.target_temperature  # Delegate

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation ie. heat, cool, idle."""
        return self._state.hvac_mode  # Delegate

    @property
    def fan_mode(self) -> Optional[str]:
        """Return the fan setting."""
        return self._state.fan_mode  # Delegate

    @property
    def swing_mode(self) -> Optional[str]:
        """Return the swing setting."""
        return self._state.swing_mode  # Delegate

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the preset setting."""
        return self._state.preset_mode  # Delegate

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return True if self._disable_available_check else bool(self._device_online)

    # --- Service Methods ---
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature: Optional[float] = kwargs.get(ATTR_TEMPERATURE)
        _LOGGER.debug("Service call: set_temperature(%s)", temperature)
        if temperature is not None:
            # Use state helper to check power state
            if self._state.hvac_mode != HVACMode.OFF:  # Use state helper
                temp_int = int(temperature)
                if MIN_TEMP <= temp_int <= MAX_TEMP:
                    # Send command via sync_state
                    await self._async_sync_state(
                        {"SetTem": temp_int, "StHt": 0}
                    )  # Ensure StHt is off
                else:
                    _LOGGER.warning(
                        "Temp %s out of range (%d-%d)", temperature, MIN_TEMP, MAX_TEMP
                    )
            else:
                _LOGGER.warning("Cannot set temperature when device is off.")
        else:
            _LOGGER.warning("set_temperature called without temperature value.")
        # self.async_write_ha_state() # Removed

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing mode."""
        _LOGGER.debug("Service call: set_swing_mode(%s)", swing_mode)
        if self._state.hvac_mode != HVACMode.OFF:  # Use state helper
            if swing_mode in self._attr_swing_modes:
                await self._async_sync_state(
                    {"SwUpDn": self._attr_swing_modes.index(swing_mode)}
                )
            else:
                _LOGGER.error("Invalid swing mode requested: %s", swing_mode)
        else:
            _LOGGER.warning("Cannot set swing mode when device is off.")
        # self.async_write_ha_state() # Removed

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        _LOGGER.debug("Service call: set_preset_mode(%s)", preset_mode)
        if not self._horizontal_swing:
            _LOGGER.warning("Horizontal swing not supported.")
            return
        if self._state.hvac_mode != HVACMode.OFF:  # Use state helper
            if self._attr_preset_modes and preset_mode in self._attr_preset_modes:
                await self._async_sync_state(
                    {"SwingLfRig": self._attr_preset_modes.index(preset_mode)}
                )
            else:
                _LOGGER.error("Invalid preset mode requested: %s", preset_mode)
        else:
            _LOGGER.warning("Cannot set preset mode when device is off.")
        # self.async_write_ha_state() # Removed

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        _LOGGER.debug("Service call: set_fan_mode(%s)", fan_mode)
        if self._state.hvac_mode != HVACMode.OFF:  # Use state helper
            command: Dict[str, int] = {"Tur": 0, "Quiet": 0}  # Reset Tur/Quiet
            fan_mode_lower = fan_mode.lower()
            if fan_mode_lower == "turbo":
                command["Tur"] = 1
                # WdSpd might need adjustment based on device behavior with Turbo
            elif fan_mode_lower == "quiet":
                command["Quiet"] = 1
                # WdSpd might need adjustment based on device behavior with Quiet
            elif fan_mode in self._attr_fan_modes:
                command["WdSpd"] = self._attr_fan_modes.index(fan_mode)
            else:
                _LOGGER.error("Invalid fan mode requested: %s", fan_mode)
                return
            await self._async_sync_state(command)
        else:
            _LOGGER.warning("Cannot set fan mode when device is off.")
        # self.async_write_ha_state() # Removed

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        _LOGGER.debug("Service call: set_hvac_mode(%s)", hvac_mode)
        command: Dict[str, int] = {}
        if hvac_mode == HVACMode.OFF:
            command["Pow"] = 0
        else:
            if hvac_mode in self._attr_hvac_modes:
                command["Pow"] = 1
                command["Mod"] = self._attr_hvac_modes.index(hvac_mode)
            else:
                _LOGGER.error("Invalid HVAC mode requested: %s", hvac_mode)
                return
        await self._async_sync_state(command)
        # self.async_write_ha_state() # Removed

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        _LOGGER.debug("Service call: turn_on()")
        await self._async_sync_state({"Pow": 1})
        # self.async_write_ha_state() # Removed

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        _LOGGER.debug("Service call: turn_off()")
        await self._async_sync_state({"Pow": 0})
        # self.async_write_ha_state() # Removed

    # --- HA Lifecycle Methods ---
    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        _LOGGER.debug("Gree climate device %s added to hass", self.name)
        # Add listener for external temp sensor if configured
        if self._temp_sensor_entity_id:
            _LOGGER.debug(
                "Adding state listener for temp sensor %s", self._temp_sensor_entity_id
            )
            # Get initial state
            new_state = self.hass.states.get(self._temp_sensor_entity_id)
            if new_state:
                self._async_update_current_temp(
                    new_state
                )  # Update internal _current_temperature

            # Register for future state changes
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    self._temp_sensor_entity_id,
                    self._async_temp_sensor_changed,
                )
            )
        # Perform initial update (will also do feature detection)
        await self.async_update()

    async def async_update(self) -> None:
        """Update the entity."""
        # Directly await the async internal update method
        await self._async_update_internal()
        # State update is implicitly handled by properties reading from self._state now

    async def _async_update_internal(self) -> None:  # Renamed and made async
        """Asynchronous update logic. Handles binding and state sync."""
        if not self._api._is_bound:
            try:
                bind_success = await self._api.bind_and_get_key()  # Added await
                if not bind_success:
                    if not self._disable_available_check:
                        self._device_online = False
                    return
                else:
                    _LOGGER.info("Binding successful for %s.", self.name)
                    self._encryption_key = self._api._encryption_key
                    if self._encryption_key is not None:
                        self._api.update_encryption_key(self._encryption_key)
                    else:
                        _LOGGER.error("Binding ok but key is None for %s.", self.name)
            except (
                socket.timeout,
                socket.error,
                ConnectionError,
                ValueError,
                TypeError,
            ) as e:  # Catch specific errors
                _LOGGER.error("Exception during binding for %s: %s", self.name, e)
                if not self._disable_available_check:
                    self._device_online = False
                return

        if self._api._is_bound:
            try:
                await self._async_sync_state()  # Call async sync state
            except (
                socket.timeout,
                socket.error,
                ConnectionError,
                ValueError,
                TypeError,
            ) as e:  # Catch specific errors
                _LOGGER.error("Error during sync_state for %s: %s", self.name, e)
                if not self._disable_available_check:
                    self._device_online = False
        elif not self._disable_available_check:
            self._device_online = False

    # --- State Change Callbacks (Added back for Temp Sensor) ---

    async def _async_temp_sensor_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle temperature sensor state changes."""
        entity_id: str = event.data["entity_id"]
        new_state: Optional[State] = event.data.get("new_state")
        old_state: Optional[State] = event.data.get(
            "old_state"
        )  # Keep for debug if needed
        old_state_str: str = str(old_state.state) if old_state else "None"
        new_state_str: str = str(new_state.state) if new_state else "None"

        _LOGGER.debug(
            "temp_sensor state changed | %s from %s to %s",
            entity_id,
            old_state_str,
            new_state_str,
        )
        if new_state is None or new_state.state in (STATE_UNKNOWN, None):
            _LOGGER.debug("New temp_sensor state is unknown or None, ignoring.")
            return
        self._async_update_current_temp(new_state)
        # Request HA state update after internal temp is updated
        self.async_write_ha_state()

    @callback
    def _async_update_current_temp(self, state: State) -> None:
        """Update internal _current_temperature from sensor state."""
        # This method only updates the internal variable used by the current_temperature property
        # when an external sensor is configured. It does NOT interact with self._state.
        _LOGGER.debug(
            "Updating internal _current_temperature from sensor: %s", state.state
        )
        unit: Optional[str] = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        try:
            _state_val: str = state.state
            if self.represents_float(_state_val):
                temp_value = float(_state_val)
                if unit == UnitOfTemperature.FAHRENHEIT:
                    celsius_temp = (temp_value - 32.0) * 5.0 / 9.0
                    self._current_temperature = round(celsius_temp, 1)
                    _LOGGER.debug(
                        "External sensor (%s °F) converted to %s °C for _current_temperature",
                        temp_value,
                        self._current_temperature,
                    )
                else:
                    self._current_temperature = temp_value
                    _LOGGER.debug(
                        "External sensor (%s %s) stored directly in _current_temperature",
                        temp_value,
                        unit or "°C assumed",
                    )
            else:
                _LOGGER.warning(
                    "Temp sensor state '%s' is not a valid float.", _state_val
                )
                self._current_temperature = None
        except (ValueError, TypeError) as ex:
            _LOGGER.error(
                "Unable to update _current_temperature from temp_sensor: %s", ex
            )
            self._current_temperature = None

    # --- Helper Methods (Added back) ---
    def represents_float(self, s: Any) -> bool:
        """Check if a string represents a float."""
        if not isinstance(s, str):
            return False
        try:
            float(s)
            return True
        except ValueError:
            return False
