import pytest
from unittest.mock import patch, MagicMock, call
import json # Use standard json module

from homeassistant.components.climate import HVACMode
from homeassistant.components.climate.const import FAN_MEDIUM, SWING_VERTICAL

# Fixtures (mock_hass, gree_climate_device) are automatically discovered from conftest.py

# --- Command Method Tests (async wrappers) ---


@patch("custom_components.gree.climate.GreeClimate.turn_on")
async def test_async_turn_on(mock_turn_on, gree_climate_device):
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


@patch("custom_components.gree.climate.GreeClimate.turn_off")
async def test_async_turn_off(mock_turn_off, gree_climate_device):
    """Test turning the device off."""
    # Get the device instance by calling the factory
    device = gree_climate_device()
    # Ensure device starts 'on' (or set initial state if needed)
    # Setting internal state might be less brittle
    device._hvac_mode = HVACMode.HEAT_COOL
    # device._acOptions["Pow"] = 1 # Also set this if turn_off uses it directly

    await device.async_turn_off()
    mock_turn_off.assert_called_once()


@patch(
    "custom_components.gree.climate.GreeClimate.set_temperature"
)  # Patch synchronous method
async def test_async_set_temperature(mock_set_temperature, gree_climate_device):
    """Test setting the target temperature."""
    # Get the device instance by calling the factory
    device = gree_climate_device()
    test_temp = 24.0

    # Call the async service method
    await device.async_set_temperature(temperature=test_temp)
    # Assert the synchronous method was called
    mock_set_temperature.assert_called_once_with(temperature=test_temp)


@pytest.mark.asyncio
@patch("custom_components.gree.climate.GreeClimate.set_hvac_mode")
async def test_async_set_hvac_mode(mock_set_hvac_mode, gree_climate_device):
    """Test setting HVAC mode calls the synchronous method."""
    # Get the device instance by calling the factory
    device = gree_climate_device()
    await device.async_set_hvac_mode(hvac_mode=HVACMode.COOL)
    # Assert with positional argument
    mock_set_hvac_mode.assert_called_once_with(HVACMode.COOL)


@pytest.mark.asyncio
@patch("custom_components.gree.climate.GreeClimate.set_fan_mode")
async def test_async_set_fan_mode(mock_set_fan_mode, gree_climate_device):
    """Test setting the fan mode calls the synchronous method."""
    # Get the device instance by calling the factory
    device = gree_climate_device()
    await device.async_set_fan_mode(fan_mode=FAN_MEDIUM)
    # Assert with positional argument
    mock_set_fan_mode.assert_called_once_with(FAN_MEDIUM)


@pytest.mark.asyncio
@patch("custom_components.gree.climate.GreeClimate.set_swing_mode")
async def test_async_set_swing_mode(mock_set_swing_mode, gree_climate_device):
    """Test setting the swing mode calls the synchronous method."""
    # Get the device instance by calling the factory
    device = gree_climate_device()
    await device.async_set_swing_mode(swing_mode=SWING_VERTICAL)
    # Assert with positional argument
    mock_set_swing_mode.assert_called_once_with(SWING_VERTICAL)


# --- Direct Method Tests ---


@patch("custom_components.gree.device_api.GreeDeviceApi._fetch_result")
@patch("custom_components.gree.device_api.GreeDeviceApi._get_gcm_cipher")
@patch("custom_components.gree.device_api.GreeDeviceApi._encrypt_gcm")
def test_send_state_to_ac_gcm(
    mock_encrypt_gcm,
    mock_get_gcm_cipher,
    mock_fetch_result,
    gree_climate_device,  # Use the fixture
):
    """Test the synchronous SendStateToAc method with GCM encryption."""
    TEST_GCM_KEY = "testGcmKey123456"  # 16 bytes

    # 1. Setup V2 device with a known key
    device = gree_climate_device(encryption_key=TEST_GCM_KEY, encryption_version=2)
    # Ensure the API object also has the key set correctly by the fixture/init
    assert device._api._encryption_key == TEST_GCM_KEY.encode("utf8")
    assert device.encryption_version == 2
    # Store key directly on device instance as well (SendStateToAc uses this)
    device._encryption_key = TEST_GCM_KEY.encode("utf8")

    # Set initial state (e.g., turning Cool mode on at 22C)
    # Use the internal _acOptions dictionary directly
    initial_options = {
        "Pow": 1,
        "Mod": HVACMode.COOL.value,
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
        # Add AntiDirectBlow/LigSen if testing those features
    }
    device._acOptions = initial_options.copy()  # Use a copy

    # 2. Setup Mock return values for API calls
    mock_pack = "mock_encrypted_state_pack"
    mock_tag = "mock_state_tag"
    mock_encrypt_gcm.return_value = (mock_pack, mock_tag)

    mock_gcm_cipher_instance = MagicMock()
    mock_get_gcm_cipher.return_value = mock_gcm_cipher_instance

    # Mock the result from the device after sending command
    mock_fetch_result.return_value = {"r": 200, "opt": ["Pow"], "p": [1]}

    # 3. Action: Call SendStateToAc directly
    device.SendStateToAc(device._timeout)

    # 4. Assertions
    # 4a. Check _encrypt_gcm call
    # Construct the expected statePackJson based on initial_options
    ordered_keys = [
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

    # Construct the expected payload dictionary
    expected_payload_dict = {
        "opt": ordered_keys,
        "p": [initial_options.get(k) for k in ordered_keys], # Get values in order
        "t": "cmd"
    }
    # Convert HVACMode enum to string value for comparison
    for i, val in enumerate(expected_payload_dict["p"]):
        if isinstance(val, HVACMode):
             expected_payload_dict["p"][i] = val.value
        elif isinstance(val, bool):
             expected_payload_dict["p"][i] = int(val)
        # Add other necessary conversions if initial_options contains types
        # not directly serializable or needing specific formatting matching send_command

    # Use json to create the expected JSON string, matching send_command
    expected_statePackJson = json.dumps(expected_payload_dict, separators=(",", ":"))

    mock_encrypt_gcm.assert_called_once_with(
        TEST_GCM_KEY.encode("utf8"), expected_statePackJson
    )

    # 4b. Check _get_gcm_cipher call
    mock_get_gcm_cipher.assert_called_once_with(TEST_GCM_KEY.encode("utf8"))

    # 4c. Check _fetch_result call
    expected_payload_dict = {
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
    actual_cipher_arg = actual_call_args[0]
    actual_payload_str = actual_call_args[1]

    assert actual_cipher_arg is mock_gcm_cipher_instance
    assert json.loads(actual_payload_str) == expected_payload_dict


# Add more tests for other command methods as needed
