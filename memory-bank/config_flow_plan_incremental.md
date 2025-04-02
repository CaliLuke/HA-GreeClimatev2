# Config Flow Implementation Plan (Incremental)

**Goal:** Implement a minimal Home Assistant config flow for the `greev2` custom component, allowing users to add devices via the UI by manually entering the IP address and MAC address, with a focus on incremental implementation and testing.

**Key Decisions:**

*   **Manual Entry:** No automatic discovery initially. Users must provide IP and MAC.
*   **Automatic Binding:** Rely on the existing `device_api.py` logic to automatically bind and retrieve the encryption key. No manual key entry option for now.
*   **Single Step:** The config flow will consist of a single `user` step.
*   **Options Flow Deferred:** Configuration of optional parameters (temperature sensors, feature switches, etc.) will be handled later via an options flow.
*   **Test Focus:** Each step includes specific testing actions. Existing tests and the behavior of release `2.14.24` will be referenced.

**Revised Incremental Plan:**

**Phase 1: Foundational Setup**
*   **Step 1.1:** Update `manifest.json`, create `__init__.py` stubs, create empty `config_flow.py`.
    *   *Implementation:* Modify `manifest.json` (add `config_flow`, `iot_class`, increment `version`), modify `__init__.py` (add `async_setup`, `async_setup_entry` stub, `async_unload_entry` stub, `PLATFORMS`), create empty `config_flow.py`.
    *   *Test:* Run `pytest tests/`, static analysis (`mypy`, `ruff`/`pylint`), manual HA load check (verify no setup errors).

**Phase 2: Config Flow UI and Validation**
*   **Step 2.1:** Implement basic form display in `config_flow.py` and add basic translations.
    *   *Implementation:* Define `STEP_USER_DATA_SCHEMA`, implement `GreeV2ConfigFlow` class, implement `async_step_user` to show form, create basic `translations/en.json`.
    *   *Test:* Run tests, static analysis, manual HA form display check.
*   **Step 2.2:** Implement input validation and API binding test in `config_flow.py`. Add error translations.
    *   *Implementation:* Add submit logic to `async_step_user` (validate MAC, instantiate API, call `bind_and_get_key` via executor), show form errors on failure, add error keys to translations.
    *   *Test:* Run tests, static analysis, manual HA error condition testing (offline, bad MAC, success), **add config flow unit tests** (`tests/test_config_flow.py`) mocking API binding results.
*   **Step 2.3:** Implement config entry creation on successful bind in `config_flow.py`. Add abort translation.
    *   *Implementation:* Add `async_set_unique_id`, `_abort_if_unique_id_configured`, `async_create_entry` calls on success, add abort key to translations.
    *   *Test:* Run tests (incl. unit tests), static analysis, manual HA entry creation/duplicate check, **update config flow unit tests** for entry creation and abort paths.

**Phase 3: Climate Platform Integration**
*   **Step 3.1:** Link config entry forwarding from `__init__.py` to `climate.py` (add `async_setup_entry` stub in `climate.py`). Remove YAML platform setup.
    *   *Implementation:* Remove `PLATFORM_SCHEMA` and `async_setup_platform` from `climate.py`, add `async_setup_entry` stub to `climate.py`, update `__init__.py` `async_setup_entry`/`async_unload_entry` to use platform forwarding.
    *   *Test:* Run tests (expect failures, fix setup/imports, adapt fixtures), static analysis, manual HA log check for entry forwarding.
*   **Step 3.2:** Fully refactor `GreeClimate.__init__` for `ConfigEntry`, instantiate entity in `climate.async_setup_entry`.
    *   *Implementation:* Modify `GreeClimate.__init__` to accept `ConfigEntry`, extract data, use defaults, init API. Instantiate `GreeClimate` in `climate.async_setup_entry` and call `async_add_entities`.
    *   *Test:* Run tests (adapt fixtures/tests for `ConfigEntry`, **reference 2.14.24 behavior**), static analysis, manual HA entity creation and basic control check.

**Phase 4: Final Review**
*   **Step 4.1:** Code review, logging cleanup, final translations check.
    *   *Implementation:* Review all changes.
    *   *Test:* Run all tests, static analysis, full end-to-end manual testing (add, control, remove, multiple devices, errors).