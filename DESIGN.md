# Gree Climate V2 - Technical Design Overview

This document provides a high-level technical overview of the Home Assistant Gree Climate V2 custom component (`custom_components/greev2`), intended to help developers understand the current architecture and key design patterns.

## Core Modules and Responsibilities

The component is structured into several key Python modules:

*   **`climate.py`**:
    *   Implements the Home Assistant `ClimateEntity`.
    *   Handles integration with the HA climate platform (service calls, state updates).
    *   Manages entity lifecycle (`async_added_to_hass`, `async_update`).
    *   Delegates internal state management and property calculations to `climate_helpers.GreeClimateState`.
    *   Initiates communication via the `device_api.py` module.
    *   Handles logic specific to using an external temperature sensor.

*   **`climate_helpers.py`**:
    *   Contains the `GreeClimateState` class:
        *   Manages the internal dictionary (`_ac_options`) representing the device's raw state (e.g., `Pow`, `SetTem`, `WdSpd`).
        *   Provides properties that translate the raw state into HA-compatible formats (e.g., `hvac_mode`, `target_temperature`, `fan_mode`).
    *   Contains the `detect_features` async function:
        *   Probes the device on initial connection to detect optional features like the internal temperature sensor (`TemSen`), Anti-Direct Blow (`AntiDirectBlow`), and Light Sensor (`LigSen`).
        *   Updates the list of properties to fetch based on detected features.

*   **`device_api.py`**:
    *   Acts as the abstraction layer for all direct device communication.
    *   Handles UDP socket communication (sending/receiving).
    *   Manages device binding (`bind_and_get_key`) to retrieve the device-specific encryption key.
    *   Implements encryption/decryption for both V1 (ECB) and V2 (GCM) protocols using `pycryptodome`.
    *   Provides async methods for sending commands (`send_command`) and fetching status (`get_status`).

*   **`config_flow.py`**:
    *   Implements the Home Assistant Config Flow (`GreeV2ConfigFlow`) for UI-based setup.
        *   Guides the user through entering IP Address, MAC Address, Name, Area, Encryption Version, and optional Temperature Sensor.
        *   Validates input by attempting to bind to the device using `device_api.bind_and_get_key`.
        *   Creates the `ConfigEntry` upon successful validation.
    *   Implements the Home Assistant Options Flow (`GreeV2OptionsFlowHandler`) for modifying settings after setup.
        *   Allows updating Host IP, Name, Area, and Temperature Sensor.
        *   Re-validates connectivity if the Host IP is changed.

*   **`const.py`**:
    *   Centralizes all constants used throughout the component (e.g., default values, configuration keys (`CONF_*`), HVAC/Fan/Swing mode lists, support flags, GCM cryptographic constants).

## Key Design Concepts

*   **Separation of Concerns:** Logic is divided: HA integration (`climate.py`), state representation (`climate_helpers.py`), and low-level communication/crypto (`device_api.py`).
*   **Configuration via UI:** Setup and configuration are handled through Home Assistant's Config Flow and Options Flow, minimizing reliance on YAML (though legacy YAML files are kept for reference).
*   **Async Communication:** All device interactions in `device_api.py` and subsequent handling in `climate.py` are asynchronous (`async`/`await`).
*   **State Management:** The `GreeClimateState` class provides a single source of truth for the device's state, derived from the raw data fetched by `device_api.py`. `climate.py` reads from this state object for its properties.
*   **Feature Detection:** Optional device features are detected dynamically rather than relying solely on user configuration, making the integration more adaptable.
*   **Encryption Handling:** Supports both major Gree protocol encryption versions (V1/ECB and V2/GCM), selected during setup.

## Testing Strategy

*   Uses the `pytest` framework.
*   Leverages `pytest-asyncio` for async tests and `pytest-homeassistant-custom-component` for HA-specific testing utilities and fixtures (`hass`).
*   Dependencies are managed via `pyproject.toml` and installed using `uv`.
*   Tests are organized by functionality (`tests/commands`, `tests/device_api`, `tests/test_climate_helpers.py`, etc.).
*   Focuses on mocking the `device_api.py` layer (`AsyncMock`) for unit/integration tests of higher-level components (`climate.py`, `config_flow.py`) and mocking socket/crypto for tests of `device_api.py` itself.

## Release Process

*   A semi-automated workflow is defined using two shell scripts:
    *   `prerelease.sh`: Calculates the next version, updates `manifest.json`, stashes the memory bank, lists changed files, and prompts for commit message formulation.
    *   `release.sh`: Takes a commit message file, performs `git add`, `git commit`, `git push`, creates and pushes a version tag, and creates a GitHub release with generated notes.
*   Detailed steps are documented in `tests/TESTING_INSTRUCTIONS.md`.