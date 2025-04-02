"""Config flow for Gree Climate V2 integration."""
import logging
import socket  # For exception handling

import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac # For cleaning MAC

# Assuming DOMAIN is defined in const.py, otherwise define it here
from .const import DOMAIN, DEFAULT_NAME, DEFAULT_PORT, DEFAULT_TIMEOUT
from .device_api import GreeDeviceApi # Import the API

_LOGGER = logging.getLogger(__name__)

# Log module import
_LOGGER.info("GreeV2 Config Flow module loading...")

# Define the schema for the user configuration step
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_MAC): str,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
    }
)

async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, str]:
    """Validate the user input allows us to connect and bind."""
    _LOGGER.debug("Attempting to validate input: %s", data)
    host = data[CONF_HOST]
    mac = data[CONF_MAC]
    # Clean MAC address (remove separators, lowercase)
    cleaned_mac = format_mac(mac)

    # Basic MAC format check (already done by format_mac, but explicit check is fine)
    # if not re.match(r"^[0-9a-f]{12}$", cleaned_mac):
    #     _LOGGER.error("Invalid MAC address format: %s", mac)
    #     raise InvalidMacFormat # Custom exception or map to error key

    try:
        # Instantiate API - use defaults for port/timeout for now
        api = GreeDeviceApi(
            host=host,
            port=DEFAULT_PORT,
            mac=cleaned_mac,
            timeout=DEFAULT_TIMEOUT,
            # encryption_key=None, # Default
            # encryption_version=1, # Default - API tries both V1 and V2 if key not provided
        )

        # Run the blocking bind operation in executor
        _LOGGER.debug("Attempting to bind to device %s (%s)", host, cleaned_mac)
        is_bound = await hass.async_add_executor_job(api.bind_and_get_key)

        if not is_bound:
            _LOGGER.error("Bind failed for %s (%s) - invalid MAC/unsupported?", host, cleaned_mac)
            # Use "invalid_auth" as it implies connection worked but binding failed
            raise InvalidAuth
        # If binding is successful, return validated info (including cleaned MAC)
        _LOGGER.info("Successfully bound to device %s (%s)", host, cleaned_mac)
        return {"title": data.get(CONF_NAME, host), "cleaned_mac": cleaned_mac}

    except (socket.timeout, socket.error, ConnectionRefusedError, OSError) as conn_ex:
        _LOGGER.error("Failed to connect to device %s: %s", host, conn_ex)
        raise CannotConnect from conn_ex
    except Exception as ex:
        # Catch any other unexpected errors during API init or bind
        _LOGGER.exception("Unexpected error during validation: %s", ex)
        raise CannotConnect from ex # Map unexpected errors to cannot_connect for simplicity


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

        if user_input is not None:
            try:
                # Validate the input by trying to connect and bind
                info = await validate_input(self.hass, user_input)

                # --- Step 2.3 Placeholder ---
                # Set unique ID and check if already configured
                # await self.async_set_unique_id(info["cleaned_mac"])
                # self._abort_if_unique_id_configured()
                # --- End Step 2.3 Placeholder ---

                # If validation succeeds, create the entry
                _LOGGER.info("Validation successful, creating config entry.")
                # Pass original user_input (including name) to data
                return self.async_create_entry(title=info["title"], data=user_input)

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except exceptions.HomeAssistantError as e: # Catch other HA errors like unique ID abort
                _LOGGER.error("Config flow error: %s", e)
                 # Decide how to handle specific HA errors, maybe re-raise or map to 'base'
                errors["base"] = "unknown" # Default for now
            except Exception as e: # Catch unexpected errors from validation
                _LOGGER.exception("Unexpected exception in config flow: %s", e)
                errors["base"] = "unknown"

        # Show the form to the user (again if errors occurred)
        _LOGGER.info("GreeV2 Config Flow: Showing user form (IP/MAC/Name). Errors: %s", errors)
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

_LOGGER.info("GreeV2 Config Flow module loaded.")

# Define custom exceptions for mapping to error keys
class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""

class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate invalid auth."""

# class InvalidMacFormat(exceptions.HomeAssistantError):
#     """Error for invalid MAC format.""" # Optional if needed
