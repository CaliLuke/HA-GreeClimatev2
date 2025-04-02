"""Config flow for Gree Climate V2 integration."""

import logging
import socket  # For exception handling

import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
from homeassistant.helpers.device_registry import format_mac  # For cleaning MAC

# Assuming DOMAIN is defined in const.py, otherwise define it here
from .const import (
    DOMAIN,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    CONF_ENCRYPTION_VERSION,  # Import constant
)
from .device_api import GreeDeviceApi  # Import the API

_LOGGER = logging.getLogger(__name__)

# Log module import
_LOGGER.info("GreeV2 Config Flow module loading...")

# Define encryption version options
ENCRYPTION_OPTIONS = [
    selector.SelectOptionDict(value="1", label="V1 (ECB)"),
    selector.SelectOptionDict(value="2", label="V2 (GCM)"),
]


# Define the base schema for the user configuration step
# We make it dynamic later to preserve input on errors
def get_user_schema(user_input: dict | None = None) -> vol.Schema:
    """Return the user step schema, pre-filled with user input if available."""
    user_input = user_input or {}
    # Default to V2 based on user's previous config, but allow selection
    default_enc_version = user_input.get(CONF_ENCRYPTION_VERSION, "2")
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
            vol.Required(CONF_MAC, default=user_input.get(CONF_MAC, "")): str,
            vol.Optional(
                CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)
            ): str,
            # Add Area selector with default persistence
            vol.Optional(
                "area_id", default=user_input.get("area_id")
            ): selector.AreaSelector(),
            # Add Encryption Version selector
            vol.Optional(
                CONF_ENCRYPTION_VERSION, default=default_enc_version
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=ENCRYPTION_OPTIONS,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                ),
            ),
        }
    )


async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, str]:
    """Validate the user input allows us to connect and bind."""
    _LOGGER.debug("Validating input data: %s", data)  # Log received data
    host = data[CONF_HOST]
    mac = data[CONF_MAC]
    # Get selected encryption version, default to 1 if somehow missing (shouldn't happen with default)
    enc_version_str = data.get(CONF_ENCRYPTION_VERSION, "1")
    try:
        enc_version = int(enc_version_str)
    except (ValueError, TypeError):
        _LOGGER.warning(
            "Invalid encryption version '%s', defaulting to 1", enc_version_str
        )
        enc_version = 1

    # Clean MAC address (remove separators, lowercase)
    cleaned_mac = format_mac(mac)
    _LOGGER.debug(
        "Extracted Host: %s, Cleaned MAC: %s, Enc Ver: %d",
        host,
        cleaned_mac,
        enc_version,
    )  # Log extracted values

    try:
        # Instantiate API - use defaults for port/timeout
        _LOGGER.debug("Instantiating API with encryption_version=%d", enc_version)
        api = GreeDeviceApi(
            host=host,
            port=DEFAULT_PORT,
            mac=cleaned_mac,
            timeout=DEFAULT_TIMEOUT,
            encryption_version=enc_version,  # Use selected version
        )

        # Run the blocking bind operation in executor
        _LOGGER.debug(
            "Attempting to bind to device %s (%s) using V%d",
            host,
            cleaned_mac,
            enc_version,
        )
        is_bound = await hass.async_add_executor_job(api.bind_and_get_key)

        if not is_bound:
            _LOGGER.error(
                "Bind failed for %s (%s) - invalid MAC/unsupported?", host, cleaned_mac
            )
            # Use "invalid_auth" as it implies connection worked but binding failed
            raise InvalidAuth
        # If binding is successful, return validated info (including cleaned MAC)
        _LOGGER.info("Successfully bound to device %s (%s)", host, cleaned_mac)
        # We don't strictly need area_id in the return here, it's in the user_input passed to create_entry
        return {"title": data.get(CONF_NAME, host), "cleaned_mac": cleaned_mac}

    except (socket.timeout, socket.error, ConnectionRefusedError, OSError) as conn_ex:
        _LOGGER.error("Failed to connect to device %s: %s", host, conn_ex)
        raise CannotConnect from conn_ex
    except InvalidAuth:  # Re-raise InvalidAuth if it came from above
        raise
    except Exception as ex:  # Catch any other unexpected errors during API init or bind
        # This might still incorrectly map binding errors if bind_and_get_key raises something unexpected
        _LOGGER.exception("Unexpected error during validation: %s", ex)
        # Let's map unexpected errors during validation to invalid_auth for now,
        # as connection errors are caught above. This might need refinement if other errors occur.
        raise InvalidAuth from ex


@config_entries.HANDLERS.register(DOMAIN)
class GreeV2ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gree Climate V2."""

    # Log class definition
    _LOGGER.info("GreeV2ConfigFlow class defining...")

    VERSION = 1
    # CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL # Add later if needed

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        _LOGGER.info("GreeV2 Config Flow: async_step_user started.")
        errors = {}
        # Pass user_input to pre-fill schema only if it exists (i.e., on error)
        data_schema = get_user_schema(user_input)

        if user_input is not None:
            try:
                # Validate the input by trying to connect and bind
                info = await validate_input(self.hass, user_input)

                # Set unique ID to prevent duplicate entries
                await self.async_set_unique_id(info["cleaned_mac"])
                self._abort_if_unique_id_configured()

                # If validation succeeds, create the entry
                _LOGGER.info("Validation successful, creating config entry.")
                # Pass original user_input (including name, area_id, enc version) to data
                return self.async_create_entry(title=info["title"], data=user_input)

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except config_entries.AbortFlow as af:  # Catch abort flow specifically
                _LOGGER.info("Config flow aborted: %s", af.reason)
                # Re-raise AbortFlow to let HA handle it (shows the abort message)
                raise af
            except exceptions.HomeAssistantError as e:  # Catch other HA errors
                _LOGGER.error("Config flow error: %s", e)
                errors["base"] = "unknown"  # Default for now
            except Exception as e:  # Catch unexpected errors from validation
                _LOGGER.exception("Unexpected exception in config flow: %s", e)
                errors["base"] = "unknown"

            # If errors occurred, schema is already pre-filled by get_user_schema(user_input) above

        # Show the form to the user (again if errors occurred, pre-filled)
        _LOGGER.info("GreeV2 Config Flow: Showing user form. Errors: %s", errors)
        # Pass the potentially pre-filled schema
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )


_LOGGER.info("GreeV2 Config Flow module loaded.")


# Define custom exceptions for mapping to error keys
class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate invalid auth."""


# class InvalidMacFormat(exceptions.HomeAssistantError):
#     """Error for invalid MAC format.""" # Optional if needed
