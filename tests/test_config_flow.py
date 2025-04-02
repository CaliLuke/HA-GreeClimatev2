"""Test the Gree Climate V2 config flow."""

from unittest.mock import patch

import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers import selector  # Import selector for schema check

# Import MockConfigEntry for testing already configured
from pytest_homeassistant_custom_component.common import MockConfigEntry # type: ignore[import-untyped]

# Import custom exceptions and constants
from custom_components.greev2.config_flow import CannotConnect, InvalidAuth
from custom_components.greev2.const import (
    DOMAIN,
    CONF_ENCRYPTION_VERSION,
    DEFAULT_NAME,
    CONF_TEMP_SENSOR,
)

# Enable pytest-homeassistant-custom-component fixtures
pytest_plugins = "pytest_homeassistant_custom_component"


# Mock user input
MOCK_USER_INPUT = {
    CONF_HOST: "192.168.1.100",
    CONF_MAC: "AA:BB:CC:DD:EE:FF",
    CONF_NAME: "Test AC",
    "area_id": "test_area",
    CONF_ENCRYPTION_VERSION: "2",
    CONF_TEMP_SENSOR: "sensor.mock_temp",  # Added temp sensor
}
MOCK_CLEANED_MAC = format_mac(MOCK_USER_INPUT[CONF_MAC])


async def test_form_show(hass: HomeAssistant) -> None:
    """Test that the user form shows up with fields."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # Check schema fields exist
    data_schema_maybe = result.get("data_schema")
    assert data_schema_maybe is not None
    schema = data_schema_maybe.schema
    assert CONF_HOST in schema
    assert CONF_MAC in schema
    assert CONF_NAME in schema
    assert "area_id" in schema
    assert CONF_ENCRYPTION_VERSION in schema
    assert CONF_TEMP_SENSOR in schema  # Check new field


async def test_user_step_success(hass: HomeAssistant) -> None:
    """Test successful setup."""
    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Mock validate_input to return success
    with patch(
        "custom_components.greev2.config_flow.validate_input",
        return_value={
            "title": MOCK_USER_INPUT[CONF_NAME],
            "cleaned_mac": MOCK_CLEANED_MAC,
        },
    ) as mock_validate:
        # Provide user input
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )
        await hass.async_block_till_done()

    # Check validation was called
    mock_validate.assert_called_once_with(hass, MOCK_USER_INPUT)

    # Check that config entry was created
    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == MOCK_USER_INPUT[CONF_NAME]
    assert result2["data"] == MOCK_USER_INPUT
    # Check unique ID was set correctly in the flow handler before entry creation
    # (The actual entry object isn't directly available in result2)


async def test_user_step_cannot_connect(
    hass: HomeAssistant,
) -> None:
    """Test handling connection errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Mock validate_input to raise CannotConnect
    with patch(
        "custom_components.greev2.config_flow.validate_input",
        side_effect=CannotConnect,
    ) as mock_validate:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )
        await hass.async_block_till_done()

    # Check validation was called
    mock_validate.assert_called_once_with(hass, MOCK_USER_INPUT)

    # Check that the form is shown again with error
    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_user_step_invalid_auth(hass: HomeAssistant) -> None:
    """Test handling invalid auth / binding errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Mock validate_input to raise InvalidAuth
    with patch(
        "custom_components.greev2.config_flow.validate_input",
        side_effect=InvalidAuth,
    ) as mock_validate:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )
        await hass.async_block_till_done()

    # Check validation was called
    mock_validate.assert_called_once_with(hass, MOCK_USER_INPUT)

    # Check that the form is shown again with error
    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "invalid_auth"}


# Removed skip marker
async def test_user_step_already_configured(
    hass: HomeAssistant,
) -> None:
    """Test handling when the device is already configured."""
    # Create a mock config entry with the same unique_id first
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_CLEANED_MAC,  # Use the cleaned MAC for unique ID
        data=MOCK_USER_INPUT,  # Provide some data
    )
    mock_entry.add_to_hass(hass)  # Add it to hass

    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Mock validate_input to return success (it should still abort before creating)
    with patch(
        "custom_components.greev2.config_flow.validate_input",
        return_value={
            "title": MOCK_USER_INPUT[CONF_NAME],
            "cleaned_mac": MOCK_CLEANED_MAC,
        },
    ) as mock_validate:
        # Removed the inner patch mocking _async_current_entries
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )
        await hass.async_block_till_done()

    # Check validation was called (abort happens after validation and unique ID check)
    mock_validate.assert_called_once_with(hass, MOCK_USER_INPUT)

    # Check that the flow aborted
    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
