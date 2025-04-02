# pylint: disable=protected-access
"""Tests for the GreeDeviceApi get_status method."""

import json
import socket  # Import socket for timeout exception
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

# Import the class to test
from custom_components.greev2.device_api import GreeDeviceApi
from custom_components.greev2.const import DEFAULT_TIMEOUT

# Import constants if needed for setup
from ..conftest import MOCK_IP, MOCK_MAC, MOCK_PORT  # Adjusted import path


# pylint: disable=too-many-locals
async def test_api_get_status_v1_success() -> None:
    """Test successful get_status for V1 encryption."""
    # Arrange
    api = GreeDeviceApi(
        host=MOCK_IP,
        port=MOCK_PORT,
        mac=MOCK_MAC,
        timeout=DEFAULT_TIMEOUT,
        encryption_version=1,
    )
    api._is_bound = True  # Assume already bound
    mock_cipher = MagicMock(name="MockEcbCipher")
    api._cipher = mock_cipher  # Assign mock cipher

    properties_to_get = ["Pow", "SetTem", "Lig"]
    expected_status_values = [1, 25, 0]
    expected_response_pack = {"t": "statusok", "dat": expected_status_values}

    # Mock dependencies
    with (
        patch.object(api, "_fetch_result", new_callable=AsyncMock) as mock_fetch_result,
        patch.object(api, "_pad") as mock_pad,  # pylint: disable=unused-variable
        patch("base64.b64encode") as mock_b64encode,  # pylint: disable=unused-variable
    ):

        # Configure mocks
        mock_fetch_result.return_value = expected_response_pack
        cols_json = json.dumps(properties_to_get)
        plaintext_payload = f'{{"cols":{cols_json},"mac":"{MOCK_MAC}","t":"status"}}'
        mock_padded_payload = plaintext_payload + "padding"  # Simplified mock padding
        mock_pad.return_value = mock_padded_payload
        mock_encrypted_bytes = b"encrypted_data"
        mock_cipher.encrypt.return_value = mock_encrypted_bytes
        mock_b64_encoded_pack = "ZW5jcnlwdGVkX2RhdGE="  # base64 of "encrypted_data"
        mock_b64encode.return_value = mock_b64_encoded_pack.encode(
            "utf-8"
        )  # b64encode returns bytes

        # Act
        status_result = await api.get_status(properties_to_get)

        # Assert
        assert status_result == expected_status_values

        # Verify mocks
        mock_pad.assert_called_once_with(plaintext_payload)
        mock_cipher.encrypt.assert_called_once_with(mock_padded_payload.encode("utf8"))
        mock_b64encode.assert_called_once_with(mock_encrypted_bytes)

        expected_sent_payload_dict = {
            "cid": "app",
            "i": 0,
            "pack": mock_b64_encoded_pack,
            "t": "pack",
            "tcid": MOCK_MAC,
            "uid": 0,
        }
        mock_fetch_result.assert_awaited_once()
        call_args, _ = mock_fetch_result.call_args
        assert call_args[0] is mock_cipher  # Check correct cipher was passed
        assert json.loads(call_args[1]) == expected_sent_payload_dict  # Check payload


# pylint: disable=too-many-locals
async def test_api_get_status_v2_success() -> None:
    """Test successful get_status for V2 encryption."""
    # Arrange
    api = GreeDeviceApi(
        host=MOCK_IP,
        port=MOCK_PORT,
        mac=MOCK_MAC,
        timeout=DEFAULT_TIMEOUT,
        encryption_version=2,
    )
    api._is_bound = True  # Assume already bound
    device_key = b"test_device_key1"
    api._encryption_key = device_key  # Set the device key

    properties_to_get = ["Pow", "SetTem", "Lig"]
    expected_status_values = [1, 25, 0]
    mock_response_pack = "mock_response_pack_b64"  # pylint: disable=unused-variable
    mock_response_tag = "mock_response_tag_b64"  # pylint: disable=unused-variable
    # Note: _fetch_result for V2 decrypts internally, so it returns the *decrypted* pack
    expected_response_pack_decrypted = {"t": "statusok", "dat": expected_status_values}

    # Mock dependencies
    with (
        patch.object(api, "_fetch_result", new_callable=AsyncMock) as mock_fetch_result,
        patch.object(api, "_encrypt_gcm") as mock_encrypt_gcm,
        patch.object(api, "_get_gcm_cipher") as mock_get_gcm_cipher,
    ):

        # Configure mocks
        mock_request_pack = "mock_request_pack_b64"
        mock_request_tag = "mock_request_tag_b64"
        mock_encrypt_gcm.return_value = (mock_request_pack, mock_request_tag)
        mock_gcm_cipher = MagicMock(name="MockGcmCipher")
        mock_get_gcm_cipher.return_value = mock_gcm_cipher
        # _fetch_result needs to return the *decrypted* pack for get_status to process
        mock_fetch_result.return_value = expected_response_pack_decrypted

        cols_json = json.dumps(properties_to_get)
        plaintext_payload = f'{{"cols":{cols_json},"mac":"{MOCK_MAC}","t":"status"}}'

        # Act
        status_result = await api.get_status(properties_to_get)

        # Assert
        assert status_result == expected_status_values

        # Verify mocks
        mock_encrypt_gcm.assert_called_once_with(device_key, plaintext_payload)
        mock_get_gcm_cipher.assert_called_once_with(
            device_key
        )  # Cipher for fetch uses device key

        expected_sent_payload_dict = {
            "cid": "app",
            "i": 0,
            "pack": mock_request_pack,
            "t": "pack",
            "tcid": MOCK_MAC,
            "uid": 0,
            "tag": mock_request_tag,
        }
        mock_fetch_result.assert_awaited_once()
        call_args, _ = mock_fetch_result.call_args
        assert call_args[0] is mock_gcm_cipher  # Check correct cipher was passed
        assert json.loads(call_args[1]) == expected_sent_payload_dict  # Check payload


@pytest.mark.parametrize(
    "failure_mode, mock_return, encryption_version",
    [
        (socket.timeout("Simulated timeout"), None, 1),  # Socket timeout V1
        (ConnectionError("Simulated connection error"), None, 2),  # Connection error V2
        (ValueError("Simulated value error in fetch"), None, 1),  # Value error V1
        (
            json.JSONDecodeError("Simulated JSON error", "", 0),
            None,
            2,
        ),  # JSON decode error V2
        (Exception("Generic simulated error"), None, 1),  # Generic error V1
        (
            None,
            {"t": "statusok", "dat": [1]},
            1,
        ),  # Response length mismatch V1 (request 2, get 1)
        (
            None,
            {"t": "statusok", "dat": "not_a_list"},
            2,
        ),  # Response 'dat' not a list V2
        (None, {"t": "statusok"}, 1),  # Response missing 'dat' V1
        ("not_bound", None, 1),  # API not bound V1
    ],
)
async def test_api_get_status_failure(
    failure_mode, mock_return, encryption_version
) -> None:
    """Test get_status failure scenarios."""
    # Arrange
    api = GreeDeviceApi(
        host=MOCK_IP,
        port=MOCK_PORT,
        mac=MOCK_MAC,
        timeout=DEFAULT_TIMEOUT,
        encryption_version=encryption_version,
    )
    properties_to_get = ["Pow", "SetTem"]  # Example properties (length 2)

    if failure_mode == "not_bound":
        api._is_bound = False
    else:
        api._is_bound = True
        # Set up key/cipher as needed for the specific version to reach _fetch_result
        if encryption_version == 1:
            api._cipher = MagicMock(name="MockEcbCipher")
            api._cipher.encrypt.return_value = b"dummy_encrypted"
        else:  # V2
            api._encryption_key = b"dummy_key"

    # Patch dependencies
    with (
        patch.object(api, "_fetch_result", new_callable=AsyncMock) as mock_fetch_result,
        patch.object(
            api, "_pad", return_value="padded"
        ) as mock_pad,  # pylint: disable=unused-variable
        patch(
            "base64.b64encode", return_value=b"encoded"
        ) as mock_b64encode,  # pylint: disable=unused-variable
        patch.object(
            api, "_encrypt_gcm", return_value=("pack", "tag")
        ) as mock_encrypt_gcm,  # pylint: disable=unused-variable
        patch.object(
            api, "_get_gcm_cipher", return_value=MagicMock()
        ) as mock_get_gcm_cipher,  # pylint: disable=unused-variable
    ):

        if failure_mode != "not_bound":
            if isinstance(failure_mode, Exception):
                mock_fetch_result.side_effect = failure_mode
            else:  # Simulate bad return data
                mock_fetch_result.return_value = mock_return

        # Act & Assert
        if failure_mode == "not_bound":
            status_result = await api.get_status(properties_to_get)
            assert status_result is None
            mock_fetch_result.assert_not_awaited()
        elif isinstance(failure_mode, (socket.timeout, ConnectionError, ValueError, json.JSONDecodeError, KeyError, TypeError)) or mock_return is not None:
            # Specific exceptions or bad return data should be caught and return None
            status_result = await api.get_status(properties_to_get)
            assert status_result is None
            mock_fetch_result.assert_awaited_once()
        else:
            # Generic Exception should propagate
            with pytest.raises(Exception, match="Generic simulated error"):
                await api.get_status(properties_to_get)
            # Ensure fetch was still called
            mock_fetch_result.assert_awaited_once()
