# pylint: disable=protected-access
"""Tests for the GreeDeviceApi bind_and_get_key method."""

import json
import socket  # Import socket for timeout exception
from unittest.mock import patch, MagicMock, AsyncMock, ANY

import pytest

# Import the class to test
from custom_components.greev2.device_api import GreeDeviceApi
from custom_components.greev2.const import DEFAULT_TIMEOUT, GCM_DEFAULT_KEY

# Import constants if needed for setup
from ..conftest import MOCK_IP, MOCK_MAC, MOCK_PORT  # Adjusted import path


async def test_api_bind_and_get_key_v1_success() -> None:
    """Test successful V1 binding and key retrieval."""
    api = GreeDeviceApi(
        host=MOCK_IP,
        port=MOCK_PORT,
        mac=MOCK_MAC,
        timeout=DEFAULT_TIMEOUT,
        encryption_version=1,
    )
    expected_key = "test_v1_key_1234"
    with patch.object(
        api, "_fetch_result", new_callable=AsyncMock
    ) as mock_fetch_result:
        mock_fetch_result.return_value = {"key": expected_key}
        result = await api.bind_and_get_key()
        assert result is True
        assert api._is_bound is True
        assert api._encryption_key == expected_key.encode("utf8")
        assert api._cipher is not None
        mock_fetch_result.assert_awaited_once()
        call_args, _ = mock_fetch_result.call_args
        expected_payload_dict = {
            "cid": "app",
            "i": 1,
            "pack": ANY,
            "t": "pack",
            "tcid": MOCK_MAC,
            "uid": 0,
        }
        assert json.loads(call_args[1]) == expected_payload_dict


async def test_api_bind_and_get_key_v2_success() -> None:
    """Test successful V2 binding and key retrieval."""
    api = GreeDeviceApi(
        host=MOCK_IP,
        port=MOCK_PORT,
        mac=MOCK_MAC,
        timeout=DEFAULT_TIMEOUT,
        encryption_version=2,
    )
    expected_key = "test_v2_key_5678"
    mock_pack = "mock_pack_b64"
    mock_tag = "mock_tag_b64"
    generic_gcm_key_bytes = GCM_DEFAULT_KEY.encode("utf8")
    with (
        patch.object(api, "_fetch_result", new_callable=AsyncMock) as mock_fetch_result,
        patch.object(api, "_encrypt_gcm") as mock_encrypt_gcm,
        patch.object(api, "_get_gcm_cipher") as mock_get_gcm_cipher,
    ):

        mock_encrypt_gcm.return_value = (mock_pack, mock_tag)
        mock_fetch_result.return_value = {"key": expected_key}
        mock_generic_cipher = MagicMock(name="GenericGcmCipher")
        mock_get_gcm_cipher.return_value = mock_generic_cipher

        result = await api.bind_and_get_key()

        assert result is True
        assert api._is_bound is True
        assert api._encryption_key == expected_key.encode("utf8")
        assert api._cipher is None

        expected_bind_plaintext = (
            f'{{"cid":"{MOCK_MAC}", "mac":"{MOCK_MAC}","t":"bind","uid":0}}'
        )
        mock_encrypt_gcm.assert_called_once_with(
            generic_gcm_key_bytes, expected_bind_plaintext
        )
        mock_get_gcm_cipher.assert_called_once_with(generic_gcm_key_bytes)

        mock_fetch_result.assert_awaited_once()
        call_args, _ = mock_fetch_result.call_args
        expected_payload_dict = {
            "cid": "app",
            "i": 1,
            "pack": mock_pack,
            "t": "pack",
            "tcid": MOCK_MAC,
            "uid": 0,
            "tag": mock_tag,
        }
        assert call_args[0] is mock_generic_cipher
        assert json.loads(call_args[1]) == expected_payload_dict


@pytest.mark.parametrize(
    "failure_mode",
    [
        socket.timeout("Simulated timeout"),
        ConnectionError("Simulated connection error"),
        ValueError("Simulated value error in fetch"),
        KeyError("Simulated missing key in response"),
        Exception("Generic simulated error"),
    ],
)
async def test_api_bind_and_get_key_failure(failure_mode: Exception) -> None:
    """Test binding failure scenarios (e.g., timeout, invalid response)."""
    # Arrange (Using V1 for simplicity, failure path is similar)
    api = GreeDeviceApi(
        host=MOCK_IP,
        port=MOCK_PORT,
        mac=MOCK_MAC,
        timeout=DEFAULT_TIMEOUT,
        encryption_version=1,
    )

    # Patch _fetch_result to simulate different failures
    with patch.object(
        api, "_fetch_result", new_callable=AsyncMock
    ) as mock_fetch_result:
        if isinstance(failure_mode, KeyError):
            # Simulate response missing the 'key'
            mock_fetch_result.return_value = {"other_data": "value"}
        else:
            # Simulate exceptions being raised
            mock_fetch_result.side_effect = failure_mode

        # Act & Assert
        if isinstance(failure_mode, (socket.timeout, ConnectionError, ValueError, KeyError, TypeError, json.JSONDecodeError)):
            # These specific exceptions should be caught and return False
            result = await api.bind_and_get_key()
            assert not result
            assert not api._is_bound
            assert api._encryption_key is None # Ensure key not set on failure
            assert api._cipher is None # Ensure cipher not set on failure
            mock_fetch_result.assert_awaited_once()
        else:
            # Generic Exception should propagate
            with pytest.raises(Exception, match="Generic simulated error"):
                await api.bind_and_get_key()
            # Ensure fetch was still called
            mock_fetch_result.assert_awaited_once()
            # State should remain unbound
            assert not api._is_bound
            assert api._encryption_key is None
            assert api._cipher is None
