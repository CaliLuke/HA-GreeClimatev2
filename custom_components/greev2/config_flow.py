"""Config flow for Gree Climate V2 integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_MAC
# from homeassistant.core import HomeAssistant # Not needed yet

# Assuming DOMAIN is defined in const.py, otherwise define it here
# from .const import DOMAIN
DOMAIN = "greev2" # Define explicitly if not in const yet or to avoid import

_LOGGER = logging.getLogger(__name__)

# Log module import
_LOGGER.info("GreeV2 Config Flow module loading...")

# Define the schema for the user configuration step
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_MAC): str,
    }
)


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
            # Validation and API check will be added in Step 2.2
            # For now, just log and re-show form if needed (or proceed if valid)
            _LOGGER.info("GreeV2 Config Flow: User input received (Step 2.1 - no validation yet).")
            # Placeholder for Step 2.2/2.3: Assume success for now to test flow completion
            # return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)
            # In a real scenario without validation yet, we'd likely just re-show the form
            # or potentially error until validation is added. Let's re-show for now.
            _LOGGER.warning(
                "Config Flow: Input received but validation/creation not implemented yet."
            )
            # To prevent infinite loop in testing, let's just finish with placeholder
            return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)


        # Show the form to the user
        _LOGGER.info("GreeV2 Config Flow: Showing user form with IP/MAC fields.")
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

_LOGGER.info("GreeV2 Config Flow module loaded.")
