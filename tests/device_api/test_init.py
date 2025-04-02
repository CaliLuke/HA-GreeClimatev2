# pylint: disable=protected-access
"""Tests for the GreeDeviceApi __init__ method."""

import pytest  # pytest is implicitly used by the test runner

# Import the class to test
from custom_components.greev2.device_api import GreeDeviceApi
from custom_components.greev2.const import DEFAULT_TIMEOUT

# Import constants if needed for setup
from ..conftest import MOCK_IP, MOCK_MAC, MOCK_PORT  # Adjusted import path


async def test_api_init_v1() -> None:
    """Test GreeDeviceApi initialization for V1 encryption."""
    api = GreeDeviceApi(
        host=MOCK_IP,
        port=MOCK_PORT,
        mac=MOCK_MAC,
        timeout=DEFAULT_TIMEOUT,
        encryption_version=1,
    )
    assert api._host == MOCK_IP
    assert api._port == MOCK_PORT
    assert api._mac == MOCK_MAC
    assert api._timeout == DEFAULT_TIMEOUT
    assert api._encryption_version == 1
    assert api._encryption_key is None
    assert api._cipher is None
    assert api._is_bound is False


async def test_api_init_v2() -> None:
    """Test GreeDeviceApi initialization for V2 encryption."""
    api = GreeDeviceApi(
        host=MOCK_IP,
        port=MOCK_PORT,
        mac=MOCK_MAC,
        timeout=DEFAULT_TIMEOUT,
        encryption_version=2,
    )
    assert api._host == MOCK_IP
    assert api._port == MOCK_PORT
    assert api._mac == MOCK_MAC
    assert api._timeout == DEFAULT_TIMEOUT
    assert api._encryption_version == 2
    assert api._encryption_key is None
    assert api._cipher is None
    assert api._is_bound is False
