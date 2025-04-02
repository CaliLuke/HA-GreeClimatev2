"""The Gree Climate V2 integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

# Import const is needed if used, but not for stubs
# from . import const

_LOGGER = logging.getLogger(__name__)

# List of platforms to support. There should be a matching
# platform.async_setup_entry function for each platform.
PLATFORMS = ["climate"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Gree Climate V2 component."""
    # This component does not support configuration via configuration.yaml
    # Setup happens via config flow instead.
    _LOGGER.debug("Async_setup called, returning True as setup is via config entry.")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Gree Climate V2 from a config entry."""
    _LOGGER.debug("Setting up Gree Climate V2 entry: %s", entry.entry_id)
    # Store the config entry data/options in hass.data for the platform to access?
    # hass.data.setdefault(const.DOMAIN, {})[entry.entry_id] = entry.data

    # Forward the setup to the climate platform.
    # The climate platform will then call async_setup_entry within its code.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # TODO: Add update listener for options flow if/when implemented
    # entry.async_on_unload(entry.add_update_listener(update_listener))

    _LOGGER.debug("Finished setting up Gree Climate V2 entry: %s", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Gree Climate V2 entry: %s", entry.entry_id)
    # Forward the unload to the climate platform.
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Clean up hass.data if used
    # if unload_ok:
    #     hass.data[const.DOMAIN].pop(entry.entry_id)
    #     if not hass.data[const.DOMAIN]:
    #         hass.data.pop(const.DOMAIN)

    _LOGGER.debug("Finished unloading Gree Climate V2 entry: %s", entry.entry_id)
    return unload_ok
# Optional: If options flow is implemented later
# async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
#     """Handle options update."""
#     _LOGGER.debug("Handling options update for %s", entry.entry_id)
#     # Reload the entry to apply changes.
#     await hass.config_entries.async_reload(entry.entry_id)

