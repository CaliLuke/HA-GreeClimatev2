"""Config flow for Gree Climate V2 integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries
# from homeassistant.core import HomeAssistant # Not needed yet
# from homeassistant.const import CONF_HOST, CONF_MAC # Import from const later

# Assuming DOMAIN is defined in const.py, otherwise define it here
# from .const import DOMAIN
DOMAIN = "greev2" # Define explicitly if not in const yet or to avoid import

_LOGGER = logging.getLogger(__name__)

# Log module import
_LOGGER.info("GreeV2 Config Flow module loading...")

# Placeholder schema - will be refined in Step 2.1
STEP_USER_DATA_SCHEMA = vol.Schema({})


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
        # For Step 1.1 test, we just need the flow to be registered.
        # This will likely result in an empty form or an immediate "Success!"
        # message for now, which confirms registration.
        if user_input is not None:
            # Processing logic will be added in Step 2.2
            _LOGGER.info("GreeV2 Config Flow: User input received (placeholder processing).")
            # Create an empty entry to show the flow works end-to-end for now.
            # This will be replaced with actual logic later.
            # Using a placeholder title until we get host/IP.
            return self.async_create_entry(title="Gree V2 Device (Placeholder)", data={})

        # Show an empty form for now to confirm flow registration
        # Actual schema will be added in Step 2.1
        _LOGGER.info("GreeV2 Config Flow: Showing user form.")
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors={}
        )

_LOGGER.info("GreeV2 Config Flow module loaded.")
