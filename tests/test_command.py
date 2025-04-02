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
    # Get the device instance by calling the factory
    device = gree_climate_device()
    # Ensure device starts 'off' (or set initial state if needed)
    # Setting internal state might be less brittle than relying on _acOptions
    device._hvac_mode = HVACMode.OFF

    await device.async_turn_on()
    # Assert the synchronous method was called
    # Use ANY for hass to simplify mocking
    mock_turn_on.assert_called_once()


@patch("custom_components.greev2.climate.GreeClimate.turn_off")
async def test_async_turn_off(
    mock_turn_off: MagicMock, gree_climate_device: GreeClimateFactory
) -> None:
    """Test turning the device off."""
    # Get the device instance by calling the factory
    device = gree_climate_device()
    # Ensure device starts 'on' (or set initial state if needed)
    # Setting internal state might be less brittle
    device._hvac_mode = HVACMode.COOL  # Use a valid ON mode
    # device._acOptions["Pow"] = 1 # Also set this if turn_off uses it directly

    await device.async_turn_off()
    mock_turn_off.assert_called_once()


@patch("custom_components.greev2.climate.GreeClimate.set_temperature")
async def test_async_set_temperature(
    mock_set_temperature: MagicMock, gree_climate_device: GreeClimateFactory
) -> None:
    """Test setting the target temperature."""
    # Get the device instance by calling the factory
    device = gree_climate_device()
    test_temp: float = 24.0

    # Call the async service method
    await device.async_set_temperature(temperature=test_temp)
    # Assert the synchronous method was called
    mock_set_temperature.assert_called_once_with(temperature=test_temp)


@pytest.mark.asyncio
@patch("custom_components.greev2.climate.GreeClimate.set_hvac_mode")
async def test_async_set_hvac_mode(
    mock_set_hvac_mode: MagicMock, gree_climate_device: GreeClimateFactory
) -> None:
    """Test setting HVAC mode calls the synchronous method."""
    # Get the device instance by calling the factory
    device = gree_climate_device()
    await device.async_set_hvac_mode(hvac_mode=HVACMode.COOL)
    # Assert with positional argument
    mock_set_hvac_mode.assert_called_once_with(HVACMode.COOL)


@pytest.mark.asyncio
@patch("custom_components.greev2.climate.GreeClimate.set_fan_mode")
async def test_async_set_fan_mode(
    mock_set_fan_mode: MagicMock, gree_climate_device: GreeClimateFactory
) -> None:
    """Test setting the fan mode calls the synchronous method."""
    # Get the device instance by calling the factory
    device = gree_climate_device()
    await device.async_set_fan_mode(fan_mode=FAN_MEDIUM)
    # Assert with positional argument
    mock_set_fan_mode.assert_called_once_with(FAN_MEDIUM)


@pytest.mark.asyncio
@patch("custom_components.greev2.climate.GreeClimate.set_swing_mode")
async def test_async_set_swing_mode(
    mock_set_swing_mode: MagicMock, gree_climate_device: GreeClimateFactory
) -> None:
    """Test setting the swing mode calls the synchronous method."""
    # Get the device instance by calling the factory
    device = gree_climate_device()
    await device.async_set_swing_mode(swing_mode=SWING_VERTICAL)
    # Assert with positional argument
    mock_set_swing_mode.assert_called_once_with(SWING_VERTICAL)


# --- Direct Method Tests ---


@patch("custom_components.greev2.device_api.GreeDeviceApi._fetch_result")
@patch("custom_components.greev2.device_api.GreeDeviceApi._get_gcm_cipher")
@patch("custom_components.greev2.device_api.GreeDeviceApi._encrypt_gcm")
def test_send_state_to_ac_gcm(
    mock_encrypt_gcm: MagicMock,
    mock_get_gcm_cipher: MagicMock,
    mock_fetch_result: MagicMock,
    gree_climate_device: GreeClimateFactory,  # Use the fixture
) -> None:
    """Test the synchronous SendStateToAc method with GCM encryption."""
    TEST_GCM_KEY: str = "testGcmKey123456"  # 16 bytes

    # 1. Setup V2 device with a known key
    device = gree_climate_device(encryption_key=TEST_GCM_KEY, encryption_version=2)
    # Ensure the API object also has the key set correctly by the fixture/init
    assert device._api._encryption_key == TEST_GCM_KEY.encode("utf8")
    assert device.encryption_version == 2
    # Store key directly on device instance as well (SendStateToAc uses this)
    # device._encryption_key = TEST_GCM_KEY.encode("utf8") # Already set by init

    # Set initial state (e.g., turning Cool mode on at 22C)
    # Use the internal _acOptions dictionary directly
    initial_options: Dict[str, Any] = {
        "Pow": 1,
        "Mod": HVACMode.COOL.value,  # Use value for consistency
        "SetTem": 22,
        "WdSpd": 1,
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
        "HeatCoolType": 0,
        "TemRec": 0,
        "SvSt": 0,
        "SlpMod": 0,
        # Add optional keys if needed, ensure they match _acOptions structure
        "TemSen": None,
        "AntiDirectBlow": None,
        "LigSen": None,
    }
    device._ac_options = initial_options.copy()  # Use correct attribute name

    # 2. Setup Mock return values for API calls
    mock_pack: str = "mock_encrypted_state_pack"
    mock_tag: str = "mock_state_tag"
    mock_encrypt_gcm.return_value = (mock_pack, mock_tag)

    mock_gcm_cipher_instance = MagicMock()
    mock_get_gcm_cipher.return_value = mock_gcm_cipher_instance

    # Mock the result from the device after sending command
    mock_fetch_result.return_value = {"r": 200, "opt": ["Pow"], "p": [1]}

    # 3. Action: Call send_state_to_ac directly
    # timeout arg was removed from send_state_to_ac
    device.send_state_to_ac()

    # 4. Assertions
    # 4a. Check _encrypt_gcm call
    # Construct the expected statePackJson based on initial_options
    ordered_keys: List[str] = [
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

    # Handle potential feature flags (_has_anti_direct_blow, _has_light_sensor)
    # For this basic test, assume they are False/None initially
    device._has_anti_direct_blow = False
    device._has_light_sensor = False
    # Add keys if features were enabled
    # if device._has_anti_direct_blow: ordered_keys.append("AntiDirectBlow")
    # if device._has_light_sensor: ordered_keys.append("LigSen")

    # Construct the expected payload dictionary
    expected_payload_dict: Dict[str, Any] = {
        "opt": ordered_keys,
        "p": [initial_options.get(k) for k in ordered_keys],  # Get values in order
        "t": "cmd",
    }
    # Convert values if necessary (already done in send_command, check consistency)
    # The send_command method handles conversions, so expected 'p' should match initial_options here

    # Use json to create the expected JSON string, matching send_command
    expected_statePackJson: str = json.dumps(
        expected_payload_dict, separators=(",", ":")
    )

    mock_encrypt_gcm.assert_called_once_with(
        TEST_GCM_KEY.encode("utf8"), expected_statePackJson
    )

    # 4b. Check _get_gcm_cipher call
    mock_get_gcm_cipher.assert_called_once_with(TEST_GCM_KEY.encode("utf8"))

    # 4c. Check _fetch_result call
    expected_fetch_payload_dict: Dict[str, Any] = {
        "cid": "app",
        "i": 0,  # SendStateToAc uses i=0
        "pack": mock_pack,
        "t": "pack",
        "tcid": device._mac_addr,  # Use the device's mac
        "uid": 0,  # Assuming default uid
        "tag": mock_tag,
    }
    # Convert dict to JSON string for comparison, ensuring order matches climate.py if needed
    # Using json.loads on the actual call argument is safer
    mock_fetch_result.assert_called_once()
    actual_call_args, _ = mock_fetch_result.call_args
    actual_cipher_arg: Any = actual_call_args[0]
    actual_payload_str: str = actual_call_args[1]

    assert actual_cipher_arg is mock_gcm_cipher_instance
    assert json.loads(actual_payload_str) == expected_fetch_payload_dict


# Add more tests for other command methods as needed
