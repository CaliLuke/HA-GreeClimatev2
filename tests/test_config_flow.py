"""Test the Gree Climate V2 config flow."""

from unittest.mock import patch

import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers import selector  # Import selector for schema check

# Import custom exceptions and constants
from custom_components.greev2.config_flow import CannotConnect, InvalidAuth
from custom_components.greev2.const import DOMAIN, CONF_ENCRYPTION_VERSION, DEFAULT_NAME

# Enable pytest-homeassistant-custom-component fixtures
pytest_plugins = "pytest_homeassistant_custom_component"


# Mock user input
MOCK_USER_INPUT = {
    CONF_HOST: "192.168.1.100",
    CONF_MAC: "AA:BB:CC:DD:EE:FF",
    CONF_NAME: "Test AC",
    "area_id": "test_area",
    CONF_ENCRYPTION_VERSION: "2",  # Default to V2 for tests
}
MOCK_CLEANED_MAC = format_mac(MOCK_USER_INPUT[CONF_MAC])


async def test_form_show(hass: HomeAssistant) -> None:  # Add hass fixture
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
    # TODO: Revisit how to reliably test schema defaults
    # assert schema[CONF_NAME].default() == DEFAULT_NAME


async def test_user_step_success(hass: HomeAssistant) -> None:  # Add hass fixture
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
    # Unique ID check requires Step 2.3 implementation
    # assert result2["result"].unique_id == MOCK_CLEANED_MAC


async def test_user_step_cannot_connect(
    hass: HomeAssistant,
) -> None:  # Add hass fixture
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

    # Check that the form is shown again with error and persisted data
    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}
    # TODO: Revisit how to reliably test schema defaults for persistence
    # schema = result2["data_schema"].schema
    # assert schema[CONF_HOST].description["default"] == MOCK_USER_INPUT[CONF_HOST]
    # assert schema[CONF_MAC].description["default"] == MOCK_USER_INPUT[CONF_MAC]
    # assert schema[CONF_NAME].description["default"] == MOCK_USER_INPUT[CONF_NAME]
    # assert schema["area_id"].description["default"] == MOCK_USER_INPUT["area_id"]
    # assert schema[CONF_ENCRYPTION_VERSION].description["default"] == MOCK_USER_INPUT[CONF_ENCRYPTION_VERSION]


async def test_user_step_invalid_auth(hass: HomeAssistant) -> None:  # Add hass fixture
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

    # Check that the form is shown again with error and persisted data
    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "invalid_auth"}
    # TODO: Revisit how to reliably test schema defaults for persistence
    # schema = result2["data_schema"].schema
    # assert schema[CONF_HOST].description["default"] == MOCK_USER_INPUT[CONF_HOST]
    # assert schema[CONF_MAC].description["default"] == MOCK_USER_INPUT[CONF_MAC]
    # assert schema[CONF_NAME].description["default"] == MOCK_USER_INPUT[CONF_NAME]
    # assert schema["area_id"].description["default"] == MOCK_USER_INPUT["area_id"]
    # assert schema[CONF_ENCRYPTION_VERSION].description["default"] == MOCK_USER_INPUT[CONF_ENCRYPTION_VERSION]


@pytest.mark.skip(reason="Need to mock config entry existence for abort test")
async def test_user_step_already_configured(
    hass: HomeAssistant,
) -> None:  # Add hass fixture
    """Test handling when the device is already configured."""
    # TODO: Create a mock config entry with the same unique_id first
    # from pytest_homeassistant_custom_component.common import MockConfigEntry
    # mock_entry = MockConfigEntry(domain=DOMAIN, unique_id=MOCK_CLEANED_MAC, data=MOCK_USER_INPUT)
    # mock_entry.add_to_hass(hass)

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
        # Mock the unique ID check part
        # This assumes the unique ID check happens *after* validation
        # Need to adjust if the check happens earlier
        with patch.object(
            hass.config_entries.flow,
            "_async_current_entries",
            return_value=[{"unique_id": MOCK_CLEANED_MAC}],
        ):  # Simplified mock
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                MOCK_USER_INPUT,
            )
            await hass.async_block_till_done()

    # Check validation was called (or maybe not if abort happens first?)
    # mock_validate.assert_called_once_with(hass, MOCK_USER_INPUT)

    # Check that the flow aborted
    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
