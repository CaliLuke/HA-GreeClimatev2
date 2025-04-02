# Plan: Implement Home Assistant Options Flow for GreeV2 Integration (Revised)

1.  **Goal:** Allow users to modify specific configuration settings of an existing GreeV2 integration entry while displaying non-editable settings for context.

2.  **Editable Settings:**
    *   Device Name (Text Input)
    *   IP Address (Text Input)
    *   External Temperature Sensor (Entity Selector - `sensor` domain, `temperature` device class)
    *   Area (Area Selector)

3.  **Display-Only (Non-Editable) Settings:**
    *   Device Model (Disabled Text)
    *   Encryption Version (Disabled Text)

4.  **Implementation Steps:**

    *   **Modify `custom_components/greev2/const.py` (if needed):**
        *   Ensure constants like `CONF_DEVICE_MODEL` and `CONF_ENCRYPTION_VERSION` are defined if they aren't already, as they will be referenced in the flow.

    *   **Modify `custom_components/greev2/config_flow.py`:**
        *   Import necessary modules: `voluptuous as vol`, `homeassistant.helpers.selector as sel`, `homeassistant.core.callback`, `homeassistant.const`.
        *   Ensure `ConfigFlow` inherits from `config_entries.ConfigFlow` and add `config_entries.OptionsFlow`.
        *   Implement the `async_step_init` method within the `OptionsFlow` handler.
        *   Define a `vol.Schema` for the options form. Use `config_entry.options` (falling back to `config_entry.data`) for *editable* field defaults, and `config_entry.data` for *disabled* field defaults:
            *   `vol.Optional("name", default=self.config_entry.title)`: Text input for the device name.
            *   `vol.Required(CONF_IP_ADDRESS, default=options.get(CONF_IP_ADDRESS))`: Text input for IP.
            *   `vol.Optional(CONF_TEMP_SENSOR, default=options.get(CONF_TEMP_SENSOR))`: Entity selector for the temperature sensor.
            *   `vol.Optional("area_id", default=options.get("area_id"))`: Area selector.
            *   `vol.Disabled(CONF_DEVICE_MODEL, default=self.config_entry.data.get(CONF_DEVICE_MODEL, "Unknown"))`: Display-only field for the device model.
            *   `vol.Disabled(CONF_ENCRYPTION_VERSION, default=self.config_entry.data.get(CONF_ENCRYPTION_VERSION, "Unknown"))`: Display-only field for encryption version.
        *   In the submission handling part of `async_step_init`:
            *   Validate the IP address format.
            *   If the IP address has changed, attempt to re-validate the connection/binding to the device at the new IP. If validation fails, show the form again with an error (`errors["base"] = "cannot_connect"`).
            *   If validation passes (or IP didn't change), create a *new* dictionary (`data_to_save`) containing only the *editable* fields from `user_input` (Name, IP, Temp Sensor, Area ID).
            *   Return `self.async_create_entry(title=user_input.get("name", ""), data=data_to_save)` to save *only the editable options* into `config_entry.options`.

    *   **Modify `custom_components/greev2/__init__.py`:**
        *   In `async_setup_entry`, register the update listener: `entry.add_update_listener(async_update_options)`.
        *   Define `async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:`.
        *   Inside the listener, reload the config entry: `await hass.config_entries.async_reload(entry.entry_id)`.

    *   **Modify `custom_components/greev2/climate.py` (and potentially `climate_helpers.py`):**
        *   Verify that configuration values (IP, Temp Sensor ID, Area ID) are read primarily from `self.config_entry.options`, falling back to `self.config_entry.data` only if necessary (e.g., for initial setup before options are saved). The reload strategy should handle most of this.

    *   **Add/Update Tests:**
        *   In `tests/test_config_flow.py`, add tests for the Options Flow, including verifying that disabled fields are present but not saved, and that editable fields are saved correctly to `config_entry.options`.
        *   Test IP address change validation (success and failure).
        *   Test the update listener triggers a reload.

5.  **Visual Flow (Mermaid Diagram):**

    ```mermaid
    sequenceDiagram
        participant User
        participant HA Frontend
        participant OptionsFlowHandler
        participant Device API / Validation
        participant HomeAssistant Core
        participant GreeClimate Integration

        User->>HA Frontend: Clicks "Configure" on GreeV2 entry
        HA Frontend->>HomeAssistant Core: Request Options Flow
        HomeAssistant Core->>OptionsFlowHandler: Instantiate and call async_step_init
        OptionsFlowHandler->>HomeAssistant Core: Get current config/options
        OptionsFlowHandler->>HA Frontend: Show Options Form (pre-filled, some disabled)
        User->>HA Frontend: Modifies IP, Temp Sensor, Area, Name
        HA Frontend->>OptionsFlowHandler: Submit user_input
        OptionsFlowHandler->>OptionsFlowHandler: Validate input format
        alt IP Address Changed
            OptionsFlowHandler->>Device API / Validation: Validate connection to new IP
            alt Validation Fails
                Device API / Validation-->>OptionsFlowHandler: Error (e.g., timeout)
                OptionsFlowHandler->>HA Frontend: Show Form again with error message
            else Validation Succeeds
                Device API / Validation-->>OptionsFlowHandler: Success
                OptionsFlowHandler->>HomeAssistant Core: Save editable options (async_create_entry)
                HomeAssistant Core-->>HA Frontend: Confirmation message
            end
        else IP Address Not Changed
             OptionsFlowHandler->>HomeAssistant Core: Save editable options (async_create_entry)
             HomeAssistant Core-->>HA Frontend: Confirmation message
        end
        Note over HomeAssistant Core: Update listener registered in __init__.py triggers
        HomeAssistant Core->>HomeAssistant Core: Call async_update_options listener
        HomeAssistant Core->>HomeAssistant Core: Reload Config Entry (async_reload)
        HomeAssistant Core->>GreeClimate Integration: Call async_unload_entry
        HomeAssistant Core->>GreeClimate Integration: Call async_setup_entry (reads updated options)
        GreeClimate Integration->>GreeClimate Integration: Re-initialize with new settings