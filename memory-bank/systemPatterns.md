# System Patterns *Optional*

This file documents recurring patterns and standards used in the project.
It is optional, but recommended to be updated as the project evolves.
2025-04-01 17:54:57 - Log of updates made.

*

## Coding Patterns

*   **API Abstraction:** Communication logic with the Gree device is encapsulated in `device_api.py`. `climate.py` interacts with this API layer rather than directly handling sockets/encryption.
*   **Home Assistant Entity:** `climate.py` implements the `ClimateEntity` class from Home Assistant.
*   **State Tracking:** Internal state (`_acOptions`) is maintained and synchronized with the device and Home Assistant state.
*   **Configuration:** Uses `PLATFORM_SCHEMA` for YAML configuration validation.
*   **Logging:** Uses Python's `logging` module.
*   **Dependency Management:** `requirements_test.txt` for test dependencies, managed by `uv`.

## Architectural Patterns

*   **Custom Component:** Standard Home Assistant custom component structure.
*   **Separation of Concerns:** `climate.py` handles HA integration logic, `device_api.py` handles device communication details.

## Testing Patterns

*   **Pytest:** Uses `pytest` framework for running tests.
*   **Fixtures:** Likely uses `conftest.py` for test fixtures (needs confirmation).
*   **Mocking:** Tests likely need to mock network communication (`socket`) and potentially encryption (`Crypto.Cipher`).