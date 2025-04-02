#!/usr/bin/python
# Do basic imports
import base64
import json  # Use standard json
import logging
import socket
from datetime import timedelta
from typing import Any, Callable, Coroutine, Dict, List, Optional, Union

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from Crypto.Cipher import AES

# Simplify CipherType to Any for broader compatibility
CipherType = Any

from homeassistant.components.climate import (
    PLATFORM_SCHEMA as CLIMATE_PLATFORM_SCHEMA,  # Rename to avoid clash
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    UnitOfTemperature,  # Import for type hint
)
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
)  # For async_add_devices type
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

# Import the new API class
from .device_api import GreeDeviceApi  # CipherType is now Any, no need to import alias

REQUIREMENTS: List[str] = ["pycryptodome"]

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS: ClimateEntityFeature = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.FAN_MODE
    | ClimateEntityFeature.SWING_MODE
    | ClimateEntityFeature.TURN_ON
    | ClimateEntityFeature.TURN_OFF
)

DEFAULT_NAME: str = "Gree Climate"

CONF_TARGET_TEMP_STEP: str = "target_temp_step"
CONF_TEMP_SENSOR: str = "temp_sensor"
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

DEFAULT_PORT: int = 7000
DEFAULT_TIMEOUT: int = 10
DEFAULT_TARGET_TEMP_STEP: float = 1.0  # Use float for consistency

# from the remote control and gree app
MIN_TEMP: int = 16
MAX_TEMP: int = 30

# update() interval
SCAN_INTERVAL: timedelta = timedelta(seconds=60)

TEMP_OFFSET: int = 40

# fixed values in gree mode lists
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
PRESET_MODES: List[str] = [
    "Default",
    "Full swing",
    "Fixed in the leftmost position",
    "Fixed in the middle-left position",
    "Fixed in the middle postion",  # Typo? "position"
    "Fixed in the middle-right position",
    "Fixed in the rightmost position",
]

# GCM Constants (Placeholder - Values depend on actual Gree protocol reverse engineering)
GCM_DEFAULT_KEY: str = "{yxAHAY_Lm6pbC/<"  # Default key for GCM binding based on logs
GCM_IV: bytes = b"\x00" * 12  # Initialization Vector (often 12 bytes for GCM)
GCM_ADD: bytes = b""  # Additional Authenticated Data (if used by protocol)

PLATFORM_SCHEMA: vol.Schema = CLIMATE_PLATFORM_SCHEMA.extend(  # Use voluptuous.Schema
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
        vol.Required(CONF_MAC): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(
            CONF_TARGET_TEMP_STEP, default=DEFAULT_TARGET_TEMP_STEP
        ): vol.Coerce(float),
        vol.Optional(CONF_TEMP_SENSOR): cv.entity_id,
        vol.Optional(CONF_LIGHTS): cv.entity_id,
        vol.Optional(CONF_XFAN): cv.entity_id,
        vol.Optional(CONF_HEALTH): cv.entity_id,
        vol.Optional(CONF_POWERSAVE): cv.entity_id,
        vol.Optional(CONF_SLEEP): cv.entity_id,
        vol.Optional(CONF_EIGHTDEGHEAT): cv.entity_id,
        vol.Optional(CONF_AIR): cv.entity_id,
        vol.Optional(CONF_ENCRYPTION_KEY): cv.string,
        vol.Optional(CONF_UID): cv.positive_int,
        vol.Optional(CONF_AUTO_XFAN): cv.entity_id,
        vol.Optional(CONF_AUTO_LIGHT): cv.entity_id,
        vol.Optional(CONF_TARGET_TEMP): cv.entity_id,
        vol.Optional(CONF_ENCRYPTION_VERSION, default=1): cv.positive_int,
        vol.Optional(CONF_HORIZONTAL_SWING, default=False): cv.boolean,
        vol.Optional(CONF_ANTI_DIRECT_BLOW): cv.entity_id,
        vol.Optional(CONF_DISABLE_AVAILABLE_CHECK, default=False): cv.boolean,
        vol.Optional(CONF_MAX_ONLINE_ATTEMPTS, default=3): cv.positive_int,
        vol.Optional(CONF_LIGHT_SENSOR): cv.entity_id,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_devices: AddEntitiesCallback,
    discovery_info: Optional[DiscoveryInfoType] = None,
) -> None:
    """Set up the Gree Climate platform."""
    _LOGGER.info("Setting up Gree climate platform")
    name: str = config[CONF_NAME]  # Use direct access after schema validation
    ip_addr: str = config[CONF_HOST]
    port: int = config[CONF_PORT]
    mac_addr_str: str = config[CONF_MAC]
    mac_addr: bytes = mac_addr_str.encode().replace(b":", b"")
    timeout: int = config[CONF_TIMEOUT]

    target_temp_step: float = config[CONF_TARGET_TEMP_STEP]
    temp_sensor_entity_id: Optional[str] = config.get(CONF_TEMP_SENSOR)
    lights_entity_id: Optional[str] = config.get(CONF_LIGHTS)
    xfan_entity_id: Optional[str] = config.get(CONF_XFAN)
    health_entity_id: Optional[str] = config.get(CONF_HEALTH)
    powersave_entity_id: Optional[str] = config.get(CONF_POWERSAVE)
    sleep_entity_id: Optional[str] = config.get(CONF_SLEEP)
    eightdegheat_entity_id: Optional[str] = config.get(CONF_EIGHTDEGHEAT)
    air_entity_id: Optional[str] = config.get(CONF_AIR)
    target_temp_entity_id: Optional[str] = config.get(CONF_TARGET_TEMP)
    hvac_modes: List[HVACMode] = HVAC_MODES  # Use constant
    fan_modes: List[str] = FAN_MODES  # Use constant
    swing_modes: List[str] = SWING_MODES  # Use constant
    preset_modes: List[str] = PRESET_MODES  # Use constant
    encryption_key: Optional[str] = config.get(CONF_ENCRYPTION_KEY)
    uid: Optional[int] = config.get(CONF_UID)
    auto_xfan_entity_id: Optional[str] = config.get(CONF_AUTO_XFAN)
    auto_light_entity_id: Optional[str] = config.get(CONF_AUTO_LIGHT)
    horizontal_swing: bool = config[CONF_HORIZONTAL_SWING]  # Use direct access
    anti_direct_blow_entity_id: Optional[str] = config.get(CONF_ANTI_DIRECT_BLOW)
    light_sensor_entity_id: Optional[str] = config.get(CONF_LIGHT_SENSOR)
    encryption_version: int = config[CONF_ENCRYPTION_VERSION]  # Use direct access
    disable_available_check: bool = config[
        CONF_DISABLE_AVAILABLE_CHECK
    ]  # Use direct access
    max_online_attempts: int = config[CONF_MAX_ONLINE_ATTEMPTS]  # Use direct access

    _LOGGER.info("Adding Gree climate device to hass")

    async_add_devices(
        [
            GreeClimate(
                hass,
                name,
                ip_addr,
                port,
                mac_addr,
                timeout,
                target_temp_step,
                temp_sensor_entity_id,
                lights_entity_id,
                xfan_entity_id,
                health_entity_id,
                powersave_entity_id,
                sleep_entity_id,
                eightdegheat_entity_id,
                air_entity_id,
                target_temp_entity_id,
                anti_direct_blow_entity_id,
                hvac_modes,
                fan_modes,
                swing_modes,
                preset_modes,
                auto_xfan_entity_id,
                auto_light_entity_id,
                horizontal_swing,
                light_sensor_entity_id,
                encryption_version,
                disable_available_check,
                max_online_attempts,
                encryption_key,
                uid,
            )
        ]
    )


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

    _temp_sensor_entity_id: Optional[str]
    _lights_entity_id: Optional[str]
    _xfan_entity_id: Optional[str]
    _health_entity_id: Optional[str]
    _powersave_entity_id: Optional[str]
    _sleep_entity_id: Optional[str]
    _eightdegheat_entity_id: Optional[str]
    _air_entity_id: Optional[str]
    _target_temp_entity_id: Optional[str]
    _anti_direct_blow_entity_id: Optional[str]
    _light_sensor_entity_id: Optional[str]
    _auto_xfan_entity_id: Optional[str]
    _auto_light_entity_id: Optional[str]

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

    _firstTimeRun: bool = True
    _enable_light_sensor: bool = False
    _auto_light: bool = False
    _auto_xfan: bool = False

    encryption_version: int
    _encryption_key: Optional[bytes] = None
    _uid: int
    _api: GreeDeviceApi
    # CIPHER is deprecated, managed by _api

    # Type hint for _acOptions - values seem to be mostly int/None
    _acOptions: Dict[str, Optional[int]]
    _optionsToFetch: List[str]
    _preset_modes_list: List[str]  # Added for storing original list

    # Deprecated, remove if not used by HA core anymore
    _enable_turn_on_off_backwards_compatibility: bool = False

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        ip_addr: str,
        port: int,
        mac_addr: bytes,  # Passed as bytes from setup
        timeout: int,
        target_temp_step: float,
        temp_sensor_entity_id: Optional[str],
        lights_entity_id: Optional[str],
        xfan_entity_id: Optional[str],
        health_entity_id: Optional[str],
        powersave_entity_id: Optional[str],
        sleep_entity_id: Optional[str],
        eightdegheat_entity_id: Optional[str],
        air_entity_id: Optional[str],
        target_temp_entity_id: Optional[str],
        anti_direct_blow_entity_id: Optional[str],
        hvac_modes: List[HVACMode],
        fan_modes: List[str],
        swing_modes: List[str],
        preset_modes: List[str],
        auto_xfan_entity_id: Optional[str],
        auto_light_entity_id: Optional[str],
        horizontal_swing: bool,
        light_sensor_entity_id: Optional[str],
        encryption_version: int,
        disable_available_check: bool,
        max_online_attempts: int,
        encryption_key: Optional[str] = None,  # Passed as string from config
        uid: Optional[int] = None,
    ) -> None:
        """Initialize the Gree Climate device."""
        _LOGGER.info("Initialize the GREE climate device")
        self.hass = hass
        self._attr_name = name  # Use _attr_ prefix for HA properties
        self._ip_addr = ip_addr
        self._port = port
        self._mac_addr = mac_addr.decode("utf-8").lower()
        self._timeout = timeout
        self._attr_unique_id = "climate.gree_" + self._mac_addr  # Use _attr_ prefix
        self._device_online = None
        self._online_attempts = 0
        self._max_online_attempts = max_online_attempts
        self._disable_available_check = disable_available_check

        self._target_temperature = None
        self._attr_target_temperature_step = target_temp_step  # Use _attr_ prefix
        # self._unit_of_measurement = UnitOfTemperature.CELSIUS # Set via _attr_temperature_unit

        self._attr_hvac_modes = hvac_modes  # Use _attr_ prefix
        self._hvac_mode = HVACMode.OFF
        self._attr_fan_modes = fan_modes  # Use _attr_ prefix
        self._fan_mode = None
        self._attr_swing_modes = swing_modes  # Use _attr_ prefix
        self._swing_mode = None
        self._preset_modes_list = preset_modes  # Store original list
        self._preset_mode = None

        self._temp_sensor_entity_id = temp_sensor_entity_id
        self._lights_entity_id = lights_entity_id
        self._xfan_entity_id = xfan_entity_id
        self._health_entity_id = health_entity_id
        self._powersave_entity_id = powersave_entity_id
        self._sleep_entity_id = sleep_entity_id
        self._eightdegheat_entity_id = eightdegheat_entity_id
        self._air_entity_id = air_entity_id
        self._target_temp_entity_id = target_temp_entity_id
        self._anti_direct_blow_entity_id = anti_direct_blow_entity_id
        self._light_sensor_entity_id = light_sensor_entity_id
        self._auto_xfan_entity_id = auto_xfan_entity_id
        self._auto_light_entity_id = auto_light_entity_id

        self._horizontal_swing = horizontal_swing
        if self._horizontal_swing:
            self._attr_preset_modes = self._preset_modes_list  # Use _attr_ prefix
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE
        else:
            self._attr_preset_modes = None

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

        self._firstTimeRun = True

        self.encryption_version = encryption_version
        # self.CIPHER = None # Deprecated

        # Instantiate the API handler
        self._api = GreeDeviceApi(
            host=ip_addr,
            port=port,
            mac=self._mac_addr,  # Pass decoded MAC
            timeout=timeout,
            encryption_key=(
                encryption_key.encode("utf8") if encryption_key else None
            ),  # Pass key if exists
            encryption_version=encryption_version,  # Pass version
        )

        if encryption_key:
            _LOGGER.info("Using configured encryption key: %s", encryption_key)
            self._encryption_key = encryption_key.encode("utf8")
            # Store reference to key in GreeClimate for now, might be removable later
            if encryption_version == 1:
                # CIPHER object is now managed by GreeDeviceApi for v1
                pass  # Handled by API init
            elif encryption_version != 2:
                _LOGGER.error(
                    "Encryption version %s is not implemented.",
                    self.encryption_version,  # Use instance var
                )
        else:
            self._encryption_key = None

        if uid is not None:  # Check for None explicitly
            self._uid = uid
        else:
            self._uid = 0

        # Initialize _acOptions with expected keys and None values
        self._acOptions = {
            "Pow": None,
            "Mod": None,
            "SetTem": None,
            "WdSpd": None,
            "Air": None,
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
            # Add optional keys that might be fetched later
            "TemSen": None,
            "AntiDirectBlow": None,
            "LigSen": None,
        }
        # Define keys to fetch initially
        self._optionsToFetch = [
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

        # Setup state change listeners
        if temp_sensor_entity_id:
            _LOGGER.info("Setting up temperature sensor: %s", temp_sensor_entity_id)
            async_track_state_change_event(
                hass, temp_sensor_entity_id, self._async_temp_sensor_changed
            )

        if lights_entity_id:
            _LOGGER.info("Setting up lights entity: %s", lights_entity_id)
            async_track_state_change_event(
                hass, lights_entity_id, self._async_lights_entity_state_changed
            )

        if xfan_entity_id:
            _LOGGER.info("Setting up xfan entity: %s", xfan_entity_id)
            async_track_state_change_event(
                hass, xfan_entity_id, self._async_xfan_entity_state_changed
            )

        if health_entity_id:
            _LOGGER.info("Setting up health entity: %s", health_entity_id)
            async_track_state_change_event(
                hass, health_entity_id, self._async_health_entity_state_changed
            )

        if powersave_entity_id:
            _LOGGER.info("Setting up powersave entity: %s", powersave_entity_id)
            async_track_state_change_event(
                hass, powersave_entity_id, self._async_powersave_entity_state_changed
            )

        if sleep_entity_id:
            _LOGGER.info("Setting up sleep entity: %s", sleep_entity_id)
            async_track_state_change_event(
                hass, sleep_entity_id, self._async_sleep_entity_state_changed
            )

        if eightdegheat_entity_id:
            _LOGGER.info("Setting up 8℃ heat entity: %s", eightdegheat_entity_id)
            async_track_state_change_event(
                hass,
                eightdegheat_entity_id,
                self._async_eightdegheat_entity_state_changed,
            )

        if air_entity_id:
            _LOGGER.info("Setting up air entity: %s", air_entity_id)
            async_track_state_change_event(
                hass, air_entity_id, self._async_air_entity_state_changed
            )

        if target_temp_entity_id:
            _LOGGER.info("Setting up target temp entity: %s", target_temp_entity_id)
            async_track_state_change_event(
                hass,
                target_temp_entity_id,
                self._async_target_temp_entity_state_changed,
            )

        if anti_direct_blow_entity_id:
            _LOGGER.info(
                "Setting up anti direct blow entity: %s", anti_direct_blow_entity_id
            )
            async_track_state_change_event(
                hass,
                anti_direct_blow_entity_id,
                self._async_anti_direct_blow_entity_state_changed,
            )

        if light_sensor_entity_id:
            _LOGGER.info("Setting up light sensor entity: %s", light_sensor_entity_id)
            light_sensor_state: Optional[State] = self.hass.states.get(
                light_sensor_entity_id
            )
            if light_sensor_state is not None and light_sensor_state.state == STATE_ON:
                self._enable_light_sensor = True
            else:
                self._enable_light_sensor = False
            async_track_state_change_event(
                hass,
                light_sensor_entity_id,
                self._async_light_sensor_entity_state_changed,
            )
        else:
            self._enable_light_sensor = False

        if auto_light_entity_id:
            _LOGGER.info("Setting up auto light entity: %s", auto_light_entity_id)
            auto_light_state: Optional[State] = self.hass.states.get(
                auto_light_entity_id
            )
            if auto_light_state is not None and auto_light_state.state == STATE_ON:
                self._auto_light = True
            else:
                self._auto_light = False
            async_track_state_change_event(
                hass, auto_light_entity_id, self._async_auto_light_entity_state_changed
            )
        else:
            self._auto_light = False

        if auto_xfan_entity_id:
            _LOGGER.info("Setting up auto xfan entity: %s", auto_xfan_entity_id)
            auto_xfan_state: Optional[State] = self.hass.states.get(auto_xfan_entity_id)
            if auto_xfan_state is not None and auto_xfan_state.state == STATE_ON:
                self._auto_xfan = True
            else:
                self._auto_xfan = False
            async_track_state_change_event(
                hass, auto_xfan_entity_id, self._async_auto_xfan_entity_state_changed
            )
        else:
            self._auto_xfan = False

    def GetDeviceKey(self) -> bool:
        """Retrieve device encryption key (V1/ECB)."""
        _LOGGER.info("Retrieving HVAC encryption key (ECB)")
        GENERIC_GREE_DEVICE_KEY: str = "a3K8Bx%2r8Y7#xDh"
        try:
            # Create cipher with generic key
            generic_cipher: CipherType = AES.new(
                GENERIC_GREE_DEVICE_KEY.encode("utf8"), AES.MODE_ECB
            )
            # Call the API's pad method
            bind_payload: str = (
                '{"mac":"' + str(self._mac_addr) + '","t":"bind","uid":0}'
            )
            padded_data: bytes = self._api._pad(bind_payload).encode("utf8")
            encrypted_pack_bytes: bytes = generic_cipher.encrypt(padded_data)
            pack: str = base64.b64encode(encrypted_pack_bytes).decode("utf-8")
            jsonPayloadToSend: str = (
                '{"cid": "app","i": 1,"pack": "'
                + pack
                + '","t":"pack","tcid":"'
                + str(self._mac_addr)
                + '","uid": 0}'
            )
            # Call the API's fetch method
            result: Dict[str, Any] = self._api._fetch_result(
                generic_cipher, jsonPayloadToSend
            )
            new_key_str: str = result["key"]
            self._encryption_key = new_key_str.encode("utf8")
            # Update the API instance with the new key
            self._api.update_encryption_key(self._encryption_key)
        except Exception as e:  # Catch broader exceptions during binding
            _LOGGER.error(
                "Error getting device encryption key (ECB)! Error: %s", e, exc_info=True
            )
            self._device_online = False
            self._online_attempts = 0
            return False
        else:
            _LOGGER.info("Fetched device encrytion key (ECB): %s", self._encryption_key)
            # self.CIPHER = AES.new(self._encryption_key, AES.MODE_ECB) # Deprecated
            self._device_online = True
            self._online_attempts = 0
            return True

    def GetDeviceKeyGCM(self) -> bool:
        """Retrieve device encryption key (V2/GCM)."""
        _LOGGER.info("Retrieving HVAC encryption key (GCM)")
        GENERIC_GREE_DEVICE_KEY_GCM: bytes = GCM_DEFAULT_KEY.encode(
            "utf8"
        )  # Use constant
        try:
            plaintext: str = (
                '{"cid":"'
                + str(self._mac_addr)
                + '", "mac":"'
                + str(self._mac_addr)
                + '","t":"bind","uid":0}'
            )
            # Call API's encrypt method
            pack, tag = self._api._encrypt_gcm(GENERIC_GREE_DEVICE_KEY_GCM, plaintext)
            jsonPayloadToSend: str = (
                '{"cid": "app","i": 1,"pack": "'
                + pack
                + '","t":"pack","tcid":"'
                + str(self._mac_addr)
                + '","uid": 0, "tag" : "'
                + tag
                + '"}'
            )
            # Call the API's fetch method, need to get the correct cipher
            cipher_gcm: CipherType = self._api._get_gcm_cipher(
                GENERIC_GREE_DEVICE_KEY_GCM
            )
            result: Dict[str, Any] = self._api._fetch_result(
                cipher_gcm, jsonPayloadToSend
            )
            new_key_str: str = result["key"]
            self._encryption_key = new_key_str.encode("utf8")
            # Update the API instance with the newly fetched key
            self._api.update_encryption_key(self._encryption_key)
        except Exception as e:  # Catch broader exceptions
            _LOGGER.error(
                "Error getting device encryption key (GCM)! Error: %s", e, exc_info=True
            )
            self._device_online = False
            self._online_attempts = 0
            return False
        else:
            _LOGGER.info("Fetched device encrytion key (GCM): %s", self._encryption_key)
            self._device_online = True
            self._online_attempts = 0
            return True

    def GreeGetValues(self, propertyNames: List[str]) -> Optional[Dict[str, Any]]:
        """Get status values from the device using the API."""
        _LOGGER.debug("Calling API get_status for properties: %s", propertyNames)
        try:
            # Delegate fetching status to the API method
            status_data: Optional[Dict[str, Any]] = self._api.get_status(propertyNames)

            if status_data is not None:
                _LOGGER.debug(
                    "Successfully received status data via API: %s", status_data
                )
                return status_data
            else:
                _LOGGER.error("API get_status returned None, indicating failure.")
                # Return None to indicate failure more clearly
                return None
        except Exception as e:
            _LOGGER.error("Error calling self._api.get_status: %s", e, exc_info=True)
            # Return None on error
            return None

    def SetAcOptions(
        self,
        acOptions: Dict[str, Optional[int]],
        newOptionsToOverride: Union[List[str], Dict[str, Any]],  # Can be list or dict
        optionValuesToOverride: Optional[
            List[Any]
        ] = None,  # Should be List if newOptionsToOverride is List
    ) -> Dict[str, Optional[int]]:
        """Update the internal _acOptions dictionary."""
        if optionValuesToOverride is not None and isinstance(
            newOptionsToOverride, list
        ):
            _LOGGER.debug("Setting acOptions with retrieved HVAC values")
            if len(newOptionsToOverride) != len(optionValuesToOverride):
                _LOGGER.error(
                    "SetAcOptions error: Mismatched lengths for keys (%d) and values (%d)",
                    len(newOptionsToOverride),
                    len(optionValuesToOverride),
                )
                # Potentially raise error or return unchanged options?
                # For now, log and continue, but this indicates a problem.
            else:
                for i, key in enumerate(newOptionsToOverride):
                    value = optionValuesToOverride[i]
                    # Basic type check/conversion - assumes values are mostly int
                    try:
                        acOptions[key] = int(value) if value is not None else None
                    except (ValueError, TypeError):
                        _LOGGER.warning(
                            "Could not convert value '%s' to int for key '%s'. Storing as None.",
                            value,
                            key,
                        )
                        acOptions[key] = None
                    _LOGGER.debug("Setting %s: %s", key, acOptions[key])
            _LOGGER.debug("Done setting acOptions")
        elif isinstance(newOptionsToOverride, dict):
            _LOGGER.debug("Overwriting acOptions with new settings")
            for key, value in newOptionsToOverride.items():
                # Basic type check/conversion
                try:
                    acOptions[key] = int(value) if value is not None else None
                except (ValueError, TypeError):
                    _LOGGER.warning(
                        "Could not convert value '%s' to int for key '%s'. Storing as None.",
                        value,
                        key,
                    )
                    acOptions[key] = None
                _LOGGER.debug("Overwriting %s: %s", key, acOptions[key])
            _LOGGER.debug("Done overwriting acOptions")
        else:
            _LOGGER.error("Invalid arguments passed to SetAcOptions.")
            # Return unchanged options if arguments are invalid
        return acOptions

    def SendStateToAc(
        self, timeout: int
    ) -> Optional[Dict[str, Any]]:  # timeout seems unused now? API uses self._timeout
        """Send the current state (_acOptions) to the AC unit."""
        # Define default options
        opt_keys: List[str] = [
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

        # Add optional features if enabled
        if self._has_anti_direct_blow:
            opt_keys.append("AntiDirectBlow")
        if self._has_light_sensor:
            opt_keys.append("LigSen")  # Check actual key name used by device

        # Get the corresponding values from _acOptions
        # Note: Ensure the order matches opt_keys precisely!
        # Handle potential None values gracefully if needed by API
        p_values: List[Any] = [self._acOptions.get(key) for key in opt_keys]

        _LOGGER.debug(
            "Calling API send_command with opt_keys: %s, p_values: %s",
            opt_keys,
            p_values,
        )

        # Call the API method to handle sending the command
        try:
            # Pass opt_keys and the corresponding values
            # The API method now handles JSON construction, encryption, and network I/O
            receivedJsonPayload: Optional[Dict[str, Any]] = self._api.send_command(
                opt_keys, p_values
            )

            if receivedJsonPayload:
                _LOGGER.debug(
                    "Successfully sent command via API. Response pack: %s",
                    receivedJsonPayload,
                )
                # Potentially process the response here if needed by GreeClimate
                # For now, just logging success.
                return receivedJsonPayload  # Return the response pack
            else:
                _LOGGER.error(
                    "API send_command returned None or False, indicating failure."
                )
                return None
        except Exception as e:
            _LOGGER.error("Error calling self._api.send_command: %s", e, exc_info=True)
            return None

    def UpdateHATargetTemperature(self) -> None:
        """Update HA target temperature based on internal state."""
        # Sync set temperature to HA. If 8℃ heating is active we set the temp in HA to 8℃ so that it shows the same as the AC display.
        if self._acOptions.get("StHt") == 1:
            self._target_temperature = 8.0  # Use float
            _LOGGER.debug(
                "HA target temp set according to HVAC state to 8.0℃ since 8℃ heating mode is active"
            )
        else:
            set_temp = self._acOptions.get("SetTem")
            self._target_temperature = float(set_temp) if set_temp is not None else None

            if self._target_temp_entity_id and self._target_temperature is not None:
                target_temp_state: Optional[State] = self.hass.states.get(
                    self._target_temp_entity_id
                )
                if target_temp_state:
                    attr: Dict[str, Any] = dict(
                        target_temp_state.attributes
                    )  # Get mutable copy
                    if MIN_TEMP <= self._target_temperature <= MAX_TEMP:
                        self.hass.states.async_set(
                            self._target_temp_entity_id,
                            str(
                                self._target_temperature
                            ),  # Convert state to string for async_set
                            attr,
                        )
            _LOGGER.debug(
                "HA target temp set according to HVAC state to: %s",
                self._target_temperature,
            )

    def UpdateHAOptions(self) -> None:
        """Update HA state for various options based on internal state."""
        # Sync HA with retreived HVAC options
        # WdSpd = fanspeed (0=auto), SvSt = powersave, Air = Air in/out (1=air in, 2=air out), Health = health
        # SwhSlp,SlpMod = sleep (both needed for sleep deactivation), StHt = 8℃ deg heating, Lig = lights, Blo = xfan

        # Helper to update state
        def _update_entity_state(
            entity_id: Optional[str],
            current_val: Optional[str],
            new_state: Optional[str],
        ) -> Optional[str]:
            if new_state is None:
                _LOGGER.debug(
                    "New state for %s is None, skipping update.",
                    entity_id or "unknown entity",
                )
                return current_val  # Return old value if new is None

            _LOGGER.debug(
                "Updating HA option %s to: %s", entity_id or "internal", new_state
            )
            if entity_id:
                entity_state_obj: Optional[State] = self.hass.states.get(entity_id)
                if entity_state_obj:
                    attr: Dict[str, Any] = dict(entity_state_obj.attributes)
                    if new_state in (STATE_ON, STATE_OFF):  # Only update if valid state
                        # Check if state actually changed before setting
                        if entity_state_obj.state != new_state:
                            self.hass.states.async_set(entity_id, new_state, attr)
                        else:
                            _LOGGER.debug(
                                "HA state for %s already %s, not setting.",
                                entity_id,
                                new_state,
                            )
                    else:
                        _LOGGER.warning(
                            "Attempted to set invalid state %s for %s",
                            new_state,
                            entity_id,
                        )
                else:
                    _LOGGER.warning("Entity %s not found for state update.", entity_id)
            return new_state  # Return the new state that was set (or attempted)

        # Sync Lights
        lig_val = self._acOptions.get("Lig")
        new_lights_state = (
            STATE_ON if lig_val == 1 else STATE_OFF if lig_val == 0 else STATE_UNKNOWN
        )
        self._current_lights = _update_entity_state(
            self._lights_entity_id, self._current_lights, new_lights_state
        )

        # Sync XFan
        blo_val = self._acOptions.get("Blo")
        new_xfan_state = (
            STATE_ON if blo_val == 1 else STATE_OFF if blo_val == 0 else STATE_UNKNOWN
        )
        self._current_xfan = _update_entity_state(
            self._xfan_entity_id, self._current_xfan, new_xfan_state
        )

        # Sync Health
        health_val = self._acOptions.get("Health")
        new_health_state = (
            STATE_ON
            if health_val == 1
            else STATE_OFF if health_val == 0 else STATE_UNKNOWN
        )
        self._current_health = _update_entity_state(
            self._health_entity_id, self._current_health, new_health_state
        )

        # Sync PowerSave
        svst_val = self._acOptions.get("SvSt")
        new_powersave_state = (
            STATE_ON if svst_val == 1 else STATE_OFF if svst_val == 0 else STATE_UNKNOWN
        )
        self._current_powersave = _update_entity_state(
            self._powersave_entity_id, self._current_powersave, new_powersave_state
        )

        # Sync Sleep
        swhslp_val = self._acOptions.get("SwhSlp")
        slpmod_val = self._acOptions.get("SlpMod")
        new_sleep_state = (
            STATE_ON
            if (swhslp_val == 1 and slpmod_val == 1)
            else STATE_OFF if (swhslp_val == 0 and slpmod_val == 0) else STATE_UNKNOWN
        )
        self._current_sleep = _update_entity_state(
            self._sleep_entity_id, self._current_sleep, new_sleep_state
        )

        # Sync 8 Degree Heat
        stht_val = self._acOptions.get("StHt")
        new_8deg_state = (
            STATE_ON if stht_val == 1 else STATE_OFF if stht_val == 0 else STATE_UNKNOWN
        )
        self._current_eightdegheat = _update_entity_state(
            self._eightdegheat_entity_id, self._current_eightdegheat, new_8deg_state
        )

        # Sync Air
        air_val = self._acOptions.get("Air")
        new_air_state = (
            STATE_ON if air_val == 1 else STATE_OFF if air_val == 0 else STATE_UNKNOWN
        )  # Assuming 1=ON, 0=OFF
        self._current_air = _update_entity_state(
            self._air_entity_id, self._current_air, new_air_state
        )

        # Sync Anti Direct Blow (only if feature exists)
        if self._has_anti_direct_blow:
            adb_val = self._acOptions.get("AntiDirectBlow")
            new_adb_state = (
                STATE_ON
                if adb_val == 1
                else STATE_OFF if adb_val == 0 else STATE_UNKNOWN
            )
            self._current_anti_direct_blow = _update_entity_state(
                self._anti_direct_blow_entity_id,
                self._current_anti_direct_blow,
                new_adb_state,
            )

    def UpdateHAHvacMode(self) -> None:
        """Update HA HVAC mode based on internal state."""
        pow_state = self._acOptions.get("Pow")
        if pow_state == 0:
            self._hvac_mode = HVACMode.OFF
        else:
            mod_index = self._acOptions.get("Mod")
            if mod_index is not None and 0 <= mod_index < len(self._attr_hvac_modes):
                self._hvac_mode = self._attr_hvac_modes[mod_index]
            else:
                _LOGGER.warning("Invalid HVAC mode index received: %s", mod_index)
                self._hvac_mode = HVACMode.OFF  # Default to OFF if invalid
        _LOGGER.debug(
            "HA operation mode set according to HVAC state to: %s",
            self._hvac_mode,
        )

    def UpdateHACurrentSwingMode(self) -> None:
        """Update HA vertical swing mode based on internal state."""
        swing_index = self._acOptions.get("SwUpDn")
        if swing_index is not None and 0 <= swing_index < len(self._attr_swing_modes):
            self._swing_mode = self._attr_swing_modes[swing_index]
        else:
            _LOGGER.warning(
                "Invalid vertical swing mode index received: %s", swing_index
            )
            self._swing_mode = None  # Set to None if invalid
        _LOGGER.debug(
            "HA swing mode set according to HVAC state to: %s",
            self._swing_mode,
        )

    def UpdateHACurrentPresetMode(self) -> None:
        """Update HA horizontal swing (preset) mode based on internal state."""
        if not self._horizontal_swing:
            self._preset_mode = None
            return

        preset_index = self._acOptions.get("SwingLfRig")
        if (
            self._attr_preset_modes
            and preset_index is not None
            and 0 <= preset_index < len(self._attr_preset_modes)
        ):
            self._preset_mode = self._attr_preset_modes[preset_index]
        else:
            _LOGGER.warning(
                "Invalid horizontal swing (preset) mode index received: %s",
                preset_index,
            )
            self._preset_mode = None  # Set to None if invalid
        _LOGGER.debug(
            "HA preset mode set according to HVAC state to: %s",
            self._preset_mode,
        )

    def UpdateHAFanMode(self) -> None:
        """Update HA fan mode based on internal state."""
        if self._acOptions.get("Tur") == 1:
            self._fan_mode = "Turbo"
        elif (
            self._acOptions.get("Quiet") == 1
        ):  # Check for 1 specifically? Docs say >=1
            self._fan_mode = "Quiet"
        else:
            speed_index = self._acOptions.get("WdSpd")
            if speed_index is not None and 0 <= speed_index < len(self._attr_fan_modes):
                self._fan_mode = self._attr_fan_modes[speed_index]
            else:
                _LOGGER.warning("Invalid fan speed index received: %s", speed_index)
                self._fan_mode = None  # Set to None if invalid
        _LOGGER.debug(
            "HA fan mode set according to HVAC state to: %s",
            self._fan_mode,
        )

    def UpdateHACurrentTemperature(self) -> None:
        """Update HA current temperature based on internal state or sensor."""
        if not self._temp_sensor_entity_id:
            if self._has_temp_sensor:
                temp_sen = self._acOptions.get("TemSen")
                if temp_sen is not None:
                    # Apply offset logic
                    temp = float(
                        temp_sen if temp_sen <= TEMP_OFFSET else temp_sen - TEMP_OFFSET
                    )
                    # Use the HA unit system - assumes Celsius from device
                    # No conversion needed if device is Celsius and HA is Celsius
                    self._current_temperature = temp
                    _LOGGER.debug(
                        "HA current temperature set with device built-in sensor: %s %s",
                        self._current_temperature,
                        self._attr_temperature_unit,
                    )
                else:
                    _LOGGER.debug("Device temperature sensor value (TemSen) is None.")
                    self._current_temperature = None
            else:
                # No external sensor and no internal sensor detected/available
                self._current_temperature = None
                _LOGGER.debug(
                    "No internal or external temperature sensor configured/detected."
                )
        # If external sensor is configured, _async_update_current_temp handles updates

    def UpdateHAStateToCurrentACState(self) -> None:
        """Update all HA state properties based on the current _acOptions."""
        self.UpdateHATargetTemperature()
        self.UpdateHAOptions()
        self.UpdateHAHvacMode()
        self.UpdateHACurrentSwingMode()
        # Only update preset if supported
        if self._horizontal_swing:
            self.UpdateHACurrentPresetMode()
        self.UpdateHAFanMode()
        self.UpdateHACurrentTemperature()

    def SyncState(
        self, acOptions: Optional[Dict[str, Any]] = None
    ) -> None:  # Return None, side effects only
        """Fetch state, update internal state, optionally send commands, update HA state."""
        _LOGGER.debug("Starting SyncState")
        if acOptions is None:
            acOptions = {}  # Ensure acOptions is a dict

        # --- Feature Detection (Run only once or if status is None) ---
        if self._has_temp_sensor is None and not self._temp_sensor_entity_id:
            _LOGGER.debug("Attempting to check for built-in temperature sensor")
            try:
                temp_sensor_check = self.GreeGetValues(
                    ["TemSen"]
                )  # Returns dict or None
                if temp_sensor_check is not None and "TemSen" in temp_sensor_check:
                    self._has_temp_sensor = True
                    # Add TemSen to fetch list if not already present
                    if "TemSen" not in self._optionsToFetch:
                        self._optionsToFetch.append("TemSen")
                    _LOGGER.info("Device has a built-in temperature sensor.")
                else:
                    self._has_temp_sensor = False
                    _LOGGER.info(
                        "Device has no built-in temperature sensor or check failed."
                    )
            except Exception as e:
                _LOGGER.warning(
                    "Could not determine built-in temperature sensor status. Error: %s",
                    e,
                )
                # Assume false for now, might retry later?
                self._has_temp_sensor = False

        if self._has_anti_direct_blow is None and self._anti_direct_blow_entity_id:
            _LOGGER.debug("Attempting to check for anti-direct blow feature")
            try:
                adb_check = self.GreeGetValues(["AntiDirectBlow"])
                if adb_check is not None and "AntiDirectBlow" in adb_check:
                    self._has_anti_direct_blow = True
                    if "AntiDirectBlow" not in self._optionsToFetch:
                        self._optionsToFetch.append("AntiDirectBlow")
                    _LOGGER.info("Device has anti-direct blow feature.")
                else:
                    self._has_anti_direct_blow = False
                    _LOGGER.info(
                        "Device has no anti-direct blow feature or check failed."
                    )
            except Exception as e:
                _LOGGER.warning(
                    "Could not determine anti-direct blow status. Error: %s", e
                )
                self._has_anti_direct_blow = False

        if self._has_light_sensor is None and self._light_sensor_entity_id:
            _LOGGER.debug("Attempting to check for built-in light sensor")
            try:
                light_sensor_check = self.GreeGetValues(["LigSen"])  # Check actual key
                if light_sensor_check is not None and "LigSen" in light_sensor_check:
                    self._has_light_sensor = True
                    if "LigSen" not in self._optionsToFetch:
                        self._optionsToFetch.append("LigSen")
                    _LOGGER.info("Device has a built-in light sensor.")
                else:
                    self._has_light_sensor = False
                    _LOGGER.info("Device has no built-in light sensor or check failed.")
            except Exception as e:
                _LOGGER.warning(
                    "Could not determine built-in light sensor status. Error: %s", e
                )
                self._has_light_sensor = False

        # --- Fetch Current State ---
        currentValues_list: Optional[List[Any]] = None  # Use temporary name
        try:
            # Fetch data from the device. Based on logs and behavior, GreeGetValues likely
            # returns the raw list from the API's 'dat' field, despite its type hint.
            raw_api_result = self.GreeGetValues(self._optionsToFetch)

            # Validate the received data
            if not isinstance(raw_api_result, list):
                _LOGGER.error("GreeGetValues did not return a list as expected. Got: %s", type(raw_api_result))
                raise ConnectionError("API returned unexpected data type.")

            if len(raw_api_result) != len(self._optionsToFetch):
                _LOGGER.error("API list length mismatch. Expected %d, got %d: %s",
                              len(self._optionsToFetch), len(raw_api_result), raw_api_result)
                raise ConnectionError("API returned list with unexpected length.")

            # If validation passes, raw_api_result is the list we need
            received_data_list: List[Any] = raw_api_result
            _LOGGER.debug("Successfully received status list from API: %s", received_data_list)

        except Exception as e:  # Catch connection errors or validation errors above
            _LOGGER.warning(
                "Could not connect with or process data from device during SyncState. Error: %s", e
            )
            if not self._disable_available_check:
                self._online_attempts += 1
                if self._online_attempts >= self._max_online_attempts:  # Use >=
                    _LOGGER.info(
                        "Could not connect with device %s times. Setting offline.",
                        self._max_online_attempts,
                    )
                    self._device_online = False
            # Exit SyncState if connection/processing failed
            return
        else:
            # Connection and data retrieval successful, reset attempts and mark online
            if not self._disable_available_check:
                if not self._device_online:
                    _LOGGER.info("Device back online.")
                self._device_online = True
                self._online_attempts = 0

            # --- Update Internal State ---
            # Set latest status from device using the validated list
            # SetAcOptions can handle list of keys and list of values
            self._acOptions = self.SetAcOptions(
                self._acOptions, self._optionsToFetch, received_data_list
            )
            _LOGGER.debug("Updated _acOptions with received data.")


            # Overwrite status with our choices if commands were passed (acOptions is a dict)
            if acOptions:  # Check if command dict is not empty
                self._acOptions = self.SetAcOptions(self._acOptions, acOptions)

            # --- Send Commands (if needed) ---
            # If not the first (boot) run AND commands were passed, update state towards the HVAC
            if not self._firstTimeRun and acOptions:
                self.SendStateToAc(self._timeout)  # timeout arg seems unused?
            elif self._firstTimeRun:
                # loop used once for Gree Climate initialisation only
                self._firstTimeRun = False

            # --- Update HA State ---
            self.UpdateHAStateToCurrentACState()

            _LOGGER.debug("Finished SyncState")
            # No return value needed

    # --- State Change Callbacks ---

    async def _async_temp_sensor_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle temperature sensor state changes."""
        entity_id: str = event.data["entity_id"]
        old_state: Optional[State] = event.data.get("old_state")  # Use .get for safety
        new_state: Optional[State] = event.data.get("new_state")
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
        # schedule_update_ha_state(True) forces immediate update, consider False
        self.async_schedule_update_ha_state(False)

    @callback
    def _async_update_current_temp(self, state: State) -> None:
        """Update current temperature from sensor state."""
        _LOGGER.debug(
            "Thermostat updated with changed temp_sensor state | %s", state.state
        )
        unit: Optional[str] = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        try:
            _state_val: str = state.state
            _LOGGER.debug("Current state temp_sensor: %s", _state_val)
            if self.represents_float(_state_val):
                temp_value = float(_state_val)
                # Ensure unit matches HA config if possible, though ClimateEntity handles conversion
                # For now, assume sensor provides value in HA's configured unit or Celsius
                self._current_temperature = temp_value
                _LOGGER.debug("Current temp set to: %s", self._current_temperature)
            else:
                _LOGGER.warning(
                    "Temp sensor state '%s' is not a valid float.", _state_val
                )
                # Optionally set _current_temperature to None or keep old value?
                # Setting to None if invalid seems safer.
                self._current_temperature = None
        except (ValueError, TypeError) as ex:
            _LOGGER.error("Unable to update from temp_sensor: %s", ex)
            self._current_temperature = None  # Set to None on error

    def represents_float(self, s: Any) -> bool:
        """Check if a string represents a float."""
        if not isinstance(s, str):
            return False  # Only check strings
        try:
            float(s)
            return True
        except ValueError:
            return False

    async def _async_lights_entity_state_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle lights entity state changes."""
        entity_id: str = event.data["entity_id"]
        old_state: Optional[State] = event.data.get("old_state")
        new_state: Optional[State] = event.data.get("new_state")
        old_state_str: str = str(old_state.state) if old_state else "None"
        new_state_str: str = str(new_state.state) if new_state else "None"

        _LOGGER.debug(
            "lights_entity state changed: %s from %s to %s",
            entity_id,
            old_state_str,
            new_state_str,
        )
        if new_state is None or new_state.state is None:
            return
        # Avoid initial 'off' state triggering command if HA just started
        if new_state.state == STATE_OFF and old_state is None:
            _LOGGER.debug(
                "lights_entity initial state is off, ignoring to avoid potential startup beep."
            )
            return
        # Check if state actually changed compared to internal tracking
        if new_state.state == self._current_lights:
            _LOGGER.debug(
                "lights_entity state change matches internal state, ignoring."
            )
            return

        self._async_update_current_lights(new_state)
        # No need to schedule update here, SyncState handles HA state updates

    @callback
    def _async_update_current_lights(self, state: State) -> None:
        """Update HVAC lights based on entity state."""
        _LOGGER.debug(
            "Updating HVAC with changed lights_entity state | %s", state.state
        )
        if state.state == STATE_ON:
            self.SyncState({"Lig": 1})
        elif state.state == STATE_OFF:
            self.SyncState({"Lig": 0})
        else:
            _LOGGER.error(
                "Unable to update from lights_entity: Invalid state %s", state.state
            )

    async def _async_xfan_entity_state_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle xfan entity state changes."""
        entity_id: str = event.data["entity_id"]
        old_state: Optional[State] = event.data.get("old_state")
        new_state: Optional[State] = event.data.get("new_state")
        old_state_str: str = str(old_state.state) if old_state else "None"
        new_state_str: str = str(new_state.state) if new_state else "None"

        _LOGGER.debug(
            "xfan_entity state changed: %s from %s to %s",
            entity_id,
            old_state_str,
            new_state_str,
        )
        if new_state is None or new_state.state is None:
            return
        if new_state.state == STATE_OFF and old_state is None:
            _LOGGER.debug("xfan_entity initial state is off, ignoring.")
            return
        if new_state.state == self._current_xfan:
            _LOGGER.debug("xfan_entity state change matches internal state, ignoring.")
            return
        # Check if HVAC mode allows XFan
        if self._hvac_mode not in (HVACMode.COOL, HVACMode.DRY):
            _LOGGER.info("Cannot set xfan in %s mode", self._hvac_mode)
            # Optionally revert the HA helper switch state?
            # For now, just don't send command.
            return

        self._async_update_current_xfan(new_state)

    @callback
    def _async_update_current_xfan(self, state: State) -> None:
        """Update HVAC xfan based on entity state."""
        _LOGGER.debug("Updating HVAC with changed xfan_entity state | %s", state.state)
        if state.state == STATE_ON:
            self.SyncState({"Blo": 1})
        elif state.state == STATE_OFF:
            self.SyncState({"Blo": 0})
        else:
            _LOGGER.error(
                "Unable to update from xfan_entity: Invalid state %s", state.state
            )

    # ... Repeat similar pattern for other optional entity callbacks ...
    # _async_health_entity_state_changed, _async_update_current_health
    # _async_powersave_entity_state_changed, _async_update_current_powersave (check mode)
    # _async_sleep_entity_state_changed, _async_update_current_sleep (check mode)
    # _async_eightdegheat_entity_state_changed, _async_update_current_eightdegheat (check mode)
    # _async_air_entity_state_changed, _async_update_current_air
    # _async_anti_direct_blow_entity_state_changed, _async_update_current_anti_direct_blow
    # _async_light_sensor_entity_state_changed, _async_update_light_sensor (updates internal flag)
    # _async_auto_light_entity_state_changed, _async_update_auto_light (updates internal flag + sends command)
    # _async_auto_xfan_entity_state_changed, _async_update_auto_xfan (updates internal flag + sends command)
    # _async_target_temp_entity_state_changed, _async_update_current_target_temp

    # --- Simplified Callbacks (Example for Health) ---
    async def _async_health_entity_state_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle health entity state changes."""
        new_state: Optional[State] = event.data.get("new_state")
        if (
            new_state is None
            or new_state.state is None
            or new_state.state == self._current_health
        ):
            return
        # Avoid initial 'off' state triggering command
        if new_state.state == STATE_OFF and event.data.get("old_state") is None:
            return
        self._async_update_current_health(new_state)

    @callback
    def _async_update_current_health(self, state: State) -> None:
        """Update HVAC health based on entity state."""
        _LOGGER.debug("Updating HVAC health state to: %s", state.state)
        if state.state == STATE_ON:
            self.SyncState({"Health": 1})
        elif state.state == STATE_OFF:
            self.SyncState({"Health": 0})

    # --- Properties ---

    # Name and Unique ID are handled by _attr_name, _attr_unique_id

    # Should poll is handled by _attr_should_poll

    # Temperature unit is handled by _attr_temperature_unit

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        # Value updated by UpdateHACurrentTemperature or _async_update_current_temp
        _LOGGER.debug("current_temperature(): %s", self._current_temperature)
        return self._current_temperature

    # Min/Max temp handled by _attr_min_temp, _attr_max_temp

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        # Value updated by UpdateHATargetTemperature
        _LOGGER.debug("target_temperature(): %s", self._target_temperature)
        return self._target_temperature

    # Target temp step handled by _attr_target_temperature_step

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation mode ie. heat, cool, idle."""
        # Value updated by UpdateHAHvacMode
        _LOGGER.debug("hvac_mode(): %s", self._hvac_mode)
        return self._hvac_mode

    # HVAC modes list handled by _attr_hvac_modes

    @property
    def fan_mode(self) -> Optional[str]:
        """Return the fan mode."""
        # Value updated by UpdateHAFanMode
        _LOGGER.debug("fan_mode(): %s", self._fan_mode)
        return self._fan_mode

    # Fan modes list handled by _attr_fan_modes

    @property
    def swing_mode(self) -> Optional[str]:
        """Return the swing mode."""
        # Value updated by UpdateHACurrentSwingMode
        _LOGGER.debug("swing_mode(): %s", self._swing_mode)
        return self._swing_mode

    # Swing modes list handled by _attr_swing_modes

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the preset mode (horizontal swing)."""
        # Value updated by UpdateHACurrentPresetMode
        # Returns None if horizontal swing not supported/enabled
        _LOGGER.debug("preset_mode(): %s", self._preset_mode)
        return self._preset_mode if self._horizontal_swing else None

    # Preset modes list handled by _attr_preset_modes (conditionally set in __init__)

    # Supported features handled by _attr_supported_features (conditionally updated in __init__)

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        if self._disable_available_check:
            return True
        else:
            is_avail = bool(self._device_online)
            _LOGGER.debug("available(): %s", is_avail)
            return is_avail

    # --- Service Methods ---

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        temperature: Optional[float] = kwargs.get(ATTR_TEMPERATURE)
        _LOGGER.debug("set_temperature(): %s", temperature)
        if temperature is not None:
            # Check if device is powered on
            if self._acOptions.get("Pow") != 0:
                temp_int = int(temperature)  # Gree uses integer temps
                if MIN_TEMP <= temp_int <= MAX_TEMP:
                    _LOGGER.debug("SyncState with SetTem=%d", temp_int)
                    self.SyncState({"SetTem": temp_int})
                    # No need to schedule update, SyncState handles it
                else:
                    _LOGGER.warning(
                        "Requested temperature %s is out of range (%d-%d)",
                        temperature,
                        MIN_TEMP,
                        MAX_TEMP,
                    )
            else:
                _LOGGER.warning("Cannot set temperature when device is off.")
        else:
            _LOGGER.warning("set_temperature called without temperature value.")

    def set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        _LOGGER.debug("set_swing_mode(): %s", swing_mode)
        if self._acOptions.get("Pow") != 0:
            if swing_mode in self._attr_swing_modes:
                swing_index = self._attr_swing_modes.index(swing_mode)
                _LOGGER.debug("SyncState with SwUpDn=%d", swing_index)
                self.SyncState({"SwUpDn": swing_index})
            else:
                _LOGGER.error("Invalid swing mode requested: %s", swing_mode)
        else:
            _LOGGER.warning("Cannot set swing mode when device is off.")

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode (horizontal swing)."""
        _LOGGER.debug("set_preset_mode(): %s", preset_mode)
        if not self._horizontal_swing:
            _LOGGER.warning(
                "Horizontal swing (preset mode) is not supported or enabled."
            )
            return
        if self._acOptions.get("Pow") != 0:
            if self._attr_preset_modes and preset_mode in self._attr_preset_modes:
                preset_index = self._attr_preset_modes.index(preset_mode)
                _LOGGER.debug("SyncState with SwingLfRig=%d", preset_index)
                self.SyncState({"SwingLfRig": preset_index})
            else:
                _LOGGER.error("Invalid preset mode requested: %s", preset_mode)
        else:
            _LOGGER.warning("Cannot set preset mode when device is off.")

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        _LOGGER.debug("set_fan_mode(): %s", fan_mode)
        if self._acOptions.get("Pow") != 0:
            command: Dict[str, int] = {
                "Tur": 0,
                "Quiet": 0,
            }  # Default to normal fan speed
            fan_mode_lower = fan_mode.lower()

            if fan_mode_lower == "turbo":
                _LOGGER.debug("Enabling turbo mode")
                command["Tur"] = 1
            elif fan_mode_lower == "quiet":
                _LOGGER.debug("Enabling quiet mode")
                command["Quiet"] = 1
            elif fan_mode in self._attr_fan_modes:
                fan_index = self._attr_fan_modes.index(fan_mode)
                _LOGGER.debug("Setting normal fan mode index to %d", fan_index)
                command["WdSpd"] = fan_index
            else:
                _LOGGER.error("Invalid fan mode requested: %s", fan_mode)
                return  # Don't send command if invalid

            self.SyncState(command)
        else:
            _LOGGER.warning("Cannot set fan mode when device is off.")

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new operation mode."""
        _LOGGER.debug("set_hvac_mode(): %s", hvac_mode)
        command: Dict[str, int] = {}
        if hvac_mode == HVACMode.OFF:
            command["Pow"] = 0
            # Auto light logic when turning off
            if self._auto_light:
                command["Lig"] = 0
                if self._has_light_sensor and self._enable_light_sensor:
                    command["LigSen"] = 1  # Check actual key name
        else:
            if hvac_mode in self._attr_hvac_modes:
                command["Pow"] = 1
                command["Mod"] = self._attr_hvac_modes.index(hvac_mode)
                # Auto light logic when turning on
                if self._auto_light:
                    command["Lig"] = 1
                    if self._has_light_sensor and self._enable_light_sensor:
                        command["LigSen"] = 0  # Check actual key name
                # Auto xfan logic
                if self._auto_xfan and hvac_mode in (HVACMode.COOL, HVACMode.DRY):
                    command["Blo"] = 1
            else:
                _LOGGER.error("Invalid HVAC mode requested: %s", hvac_mode)
                return  # Don't send command if invalid

        self.SyncState(command)

    def turn_on(self) -> None:
        """Turn on."""
        _LOGGER.debug("turn_on()")
        # Set to a default mode if turning on from off? Or just power on?
        # Current implementation just sets power on, mode remains as last set.
        command: Dict[str, int] = {"Pow": 1}
        if self._auto_light:
            command["Lig"] = 1
            if self._has_light_sensor and self._enable_light_sensor:
                command["LigSen"] = 0  # Check actual key name
        self.SyncState(command)

    def turn_off(self) -> None:
        """Turn off."""
        _LOGGER.debug("turn_off()")
        command: Dict[str, int] = {"Pow": 0}
        if self._auto_light:
            command["Lig"] = 0
            if self._has_light_sensor and self._enable_light_sensor:
                command["LigSen"] = 1  # Check actual key name
        self.SyncState(command)

    # --- HA Lifecycle Methods ---

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        _LOGGER.debug("Gree climate device added to hass()")
        # Perform initial update
        await self.async_update()

    async def async_update(self) -> None:  # Renamed and made async
        """Fetch state from device. Handles encryption key retrieval."""
        _LOGGER.debug("async_update() called")

        # Run blocking network I/O in executor
        await self.hass.async_add_executor_job(self._update_sync)

    def _update_sync(self) -> None:  # New synchronous wrapper for blocking code
        """Synchronous part of update logic."""
        if not self._encryption_key:
            key_retrieved: bool = False
            if self.encryption_version == 1:
                key_retrieved = self.GetDeviceKey()
            elif self.encryption_version == 2:
                key_retrieved = self.GetDeviceKeyGCM()
            else:
                _LOGGER.error(
                    "Encryption version %s is not implemented for key retrieval.",
                    self.encryption_version,
                )
                # Mark as unavailable if key cannot be retrieved due to version
                if not self._disable_available_check:
                    self._device_online = False
                return  # Stop update if key retrieval not possible

            if not key_retrieved:
                _LOGGER.warning("Failed to retrieve encryption key during update.")
                # Device will be marked offline by GetDeviceKey methods
                return  # Stop update if key retrieval failed
            else:
                # Key retrieved successfully, proceed to sync state
                self.SyncState()
        else:
            # Key already exists, just sync state
            self.SyncState()

    # --- Stubs for missing optional entity callbacks ---

    async def _async_powersave_entity_state_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle powersave entity state changes."""
        # TODO: Implement logic similar to other callbacks
        _LOGGER.debug("Powersave entity changed: %s", event.data.get("new_state"))
        pass

    async def _async_sleep_entity_state_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle sleep entity state changes."""
        # TODO: Implement logic similar to other callbacks
        _LOGGER.debug("Sleep entity changed: %s", event.data.get("new_state"))
        pass

    async def _async_eightdegheat_entity_state_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle 8degheat entity state changes."""
        # TODO: Implement logic similar to other callbacks
        _LOGGER.debug("8degheat entity changed: %s", event.data.get("new_state"))
        pass

    async def _async_air_entity_state_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle air entity state changes."""
        # TODO: Implement logic similar to other callbacks
        _LOGGER.debug("Air entity changed: %s", event.data.get("new_state"))
        pass

    async def _async_anti_direct_blow_entity_state_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle anti_direct_blow entity state changes."""
        # TODO: Implement logic similar to other callbacks
        _LOGGER.debug(
            "Anti_direct_blow entity changed: %s", event.data.get("new_state")
        )
        pass

    async def _async_light_sensor_entity_state_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle light_sensor entity state changes."""
        # TODO: Implement logic similar to other callbacks
        _LOGGER.debug("Light_sensor entity changed: %s", event.data.get("new_state"))
        pass

    async def _async_auto_light_entity_state_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle auto_light entity state changes."""
        # TODO: Implement logic similar to other callbacks
        _LOGGER.debug("Auto_light entity changed: %s", event.data.get("new_state"))
        pass

    async def _async_auto_xfan_entity_state_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle auto_xfan entity state changes."""
        # TODO: Implement logic similar to other callbacks
        _LOGGER.debug("Auto_xfan entity changed: %s", event.data.get("new_state"))
        pass

    # Add type hints for remaining optional entity callbacks...
    # ... (omitted for brevity, follow pattern of _async_health_entity_state_changed) ...

    async def _async_target_temp_entity_state_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle target temp entity state changes."""
        new_state: Optional[State] = event.data.get("new_state")
        if new_state is None or new_state.state is None:
            return
        # Check if state actually changed compared to internal tracking
        try:
            new_temp_float = float(new_state.state)
            if new_temp_float == self._target_temperature:
                _LOGGER.debug(
                    "target_temp_entity state change matches internal state, ignoring."
                )
                return
        except (ValueError, TypeError):
            _LOGGER.warning(
                "Invalid state received from target_temp_entity: %s", new_state.state
            )
            return

        # Avoid initial 'off' state triggering command (unlikely for temp sensor)
        if new_state.state == STATE_OFF and event.data.get("old_state") is None:
            return

        self._async_update_current_target_temp(new_state)

    @callback
    def _async_update_current_target_temp(self, state: State) -> None:
        """Update HVAC target temp based on entity state."""
        try:
            s_float = float(state.state)
            s_int = int(s_float)  # Gree uses int temps
            _LOGGER.debug("Updating HVAC target temp to: %d", s_int)
            if MIN_TEMP <= s_int <= MAX_TEMP:
                self.SyncState({"SetTem": s_int})
            else:
                _LOGGER.warning(
                    "Target temp %s from entity is out of range (%d-%d)",
                    s_float,
                    MIN_TEMP,
                    MAX_TEMP,
                )
        except (ValueError, TypeError):
            _LOGGER.error(
                "Unable to update target temp from entity state: %s", state.state
            )
