# pylint: disable=protected-access
"""Tests for the GreeDeviceApi send_command method."""

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
async def test_api_send_command_v1_success() -> None:
    """Test successful send_command for V1 encryption."""
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

    opt_keys = ["Pow", "SetTem"]
    p_values = [1, 23]
    expected_response_pack = {
        "t": "cmdok",
        "opt": opt_keys,
        "p": p_values,
    }  # Example success response

    # Mock dependencies
    with (
        patch.object(api, "_fetch_result", new_callable=AsyncMock) as mock_fetch_result,
        patch.object(api, "_pad") as mock_pad,
        patch("base64.b64encode") as mock_b64encode,
    ):

        # Configure mocks
        mock_fetch_result.return_value = expected_response_pack
        command_payload_dict = {"opt": opt_keys, "p": p_values, "t": "cmd"}
        plaintext_payload = json.dumps(command_payload_dict, separators=(",", ":"))
        mock_padded_payload = plaintext_payload + "padding"  # Simplified mock padding
        mock_pad.return_value = mock_padded_payload
        mock_encrypted_bytes = b"encrypted_cmd_data"
        mock_cipher.encrypt.return_value = mock_encrypted_bytes
        mock_b64_encoded_pack = (
            "ZW5jcnlwdGVkX2NtZF9kYXRh"  # base64 of "encrypted_cmd_data"
        )
        mock_b64encode.return_value = mock_b64_encoded_pack.encode("utf-8")

        # Act
        command_result = await api.send_command(opt_keys, p_values)

        # Assert
        assert command_result == expected_response_pack

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
async def test_api_send_command_v2_success() -> None:
    """Test successful send_command for V2 encryption."""
    # Arrange
    api = GreeDeviceApi(
        host=MOCK_IP,
        port=MOCK_PORT,
        mac=MOCK_MAC,
        timeout=DEFAULT_TIMEOUT,
        encryption_version=2,
    )
    api._is_bound = True  # Assume already bound
    device_key = b"test_device_key2"
    api._encryption_key = device_key  # Set the device key

    opt_keys = ["Pow", "SetTem"]
    p_values = [0, 26]
    expected_response_pack = {
        "t": "cmdok",
        "opt": opt_keys,
        "p": p_values,
    }  # Example success response

    # Mock dependencies
    with (
        patch.object(api, "_fetch_result", new_callable=AsyncMock) as mock_fetch_result,
        patch.object(api, "_encrypt_gcm") as mock_encrypt_gcm,
        patch.object(api, "_get_gcm_cipher") as mock_get_gcm_cipher,
    ):

        # Configure mocks
        mock_request_pack = "mock_request_pack_b64_cmd"
        mock_request_tag = "mock_request_tag_b64_cmd"
        mock_encrypt_gcm.return_value = (mock_request_pack, mock_request_tag)
        mock_gcm_cipher = MagicMock(name="MockGcmCipherCmd")
        mock_get_gcm_cipher.return_value = mock_gcm_cipher
        mock_fetch_result.return_value = expected_response_pack

        command_payload_dict = {"opt": opt_keys, "p": p_values, "t": "cmd"}
        plaintext_payload = json.dumps(command_payload_dict, separators=(",", ":"))

        # Act
        command_result = await api.send_command(opt_keys, p_values)

        # Assert
        assert command_result == expected_response_pack

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
    "failure_mode, opt_keys, p_values, encryption_version",
    [
        ("not_bound", ["Pow"], [1], 1),  # API not bound V1
        ("mismatch", ["Pow", "SetTem"], [1], 2),  # Mismatched opt/p lengths V2
        (
            TypeError("JSON serialization error"),
            ["Pow"],
            [object()],
            1,
        ),  # JSON error V1
        (socket.timeout("Simulated timeout"), ["Pow"], [1], 2),  # Socket timeout V2
        (
            ConnectionError("Simulated connection error"),
            ["Pow"],
            [1],
            1,
        ),  # Connection error V1
        (
            ValueError("Simulated value error in fetch"),
            ["Pow"],
            [1],
            2,
        ),  # Value error V2
        (
            json.JSONDecodeError("Simulated JSON error", "", 0),
            ["Pow"],
            [1],
            1,
        ),  # JSON decode error V1
        (Exception("Generic simulated error"), ["Pow"], [1], 2),  # Generic error V2
    ],
)
async def test_api_send_command_failure(
    failure_mode, opt_keys, p_values, encryption_version
) -> None:
    """Test send_command failure scenarios."""
    # Arrange
    api = GreeDeviceApi(
        host=MOCK_IP,
        port=MOCK_PORT,
        mac=MOCK_MAC,
        timeout=DEFAULT_TIMEOUT,
        encryption_version=encryption_version,
    )

    if failure_mode == "not_bound":
        api._is_bound = False
    else:
        api._is_bound = True
        # Set up key/cipher as needed for the specific version
        if encryption_version == 1:
            api._cipher = MagicMock(name="MockEcbCipher")
            api._cipher.encrypt.return_value = b"dummy_encrypted"
        else:  # V2
            api._encryption_key = b"dummy_key"

    # Patch dependencies needed before the potential failure point
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

        should_fetch_be_called = True
        json_dumps_patch = None  # To hold the patch context manager if needed

        if failure_mode in ("not_bound", "mismatch"):
            should_fetch_be_called = False
        elif isinstance(failure_mode, TypeError) and "JSON serialization error" in str(failure_mode):
            # Patch json.dumps specifically for this case
            json_dumps_patch = patch("json.dumps", side_effect=failure_mode)
            json_dumps_patch.start()  # Manually start the patch
            should_fetch_be_called = False
        elif isinstance(failure_mode, Exception):
            # Simulate _fetch_result raising an exception
            mock_fetch_result.side_effect = failure_mode
        # else: _fetch_result will be called but might fail internally based on the exception type

        try:
            # Act & Assert
            if failure_mode in ("not_bound", "mismatch") or (isinstance(failure_mode, TypeError) and "JSON serialization error" in str(failure_mode)):
                # These setup/validation errors should result in None without calling fetch
                command_result = await api.send_command(opt_keys, p_values)
                assert command_result is None
                mock_fetch_result.assert_not_awaited()
            elif isinstance(failure_mode, (socket.timeout, ConnectionError, ValueError, json.JSONDecodeError, KeyError)):
                 # Specific exceptions caught within send_command should return None
                command_result = await api.send_command(opt_keys, p_values)
                assert command_result is None
                mock_fetch_result.assert_awaited_once()
            else:
                # Generic Exception should propagate
                with pytest.raises(Exception, match="Generic simulated error"):
                    await api.send_command(opt_keys, p_values)
                # Ensure fetch was still called
                mock_fetch_result.assert_awaited_once()

        finally:
            # Manually stop the patch if it was started
            if json_dumps_patch:
                json_dumps_patch.stop()
