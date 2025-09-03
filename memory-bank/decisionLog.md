# Decision Log

This file records architectural and implementation decisions using a list format.
2025-04-01 17:54:50 - Log of updates made.

*

## Decision

*   [2025-04-01 17:54:50] Initialize Memory Bank for the project.

## Rationale

*   Maintain project context, track progress, log decisions, and facilitate collaboration between modes.

## Implementation Details

*   Created `memory-bank/` directory with `productContext.md`, `activeContext.md`, `progress.md`, `decisionLog.md`, `systemPatterns.md`.
*   Populated files with initial structure and relevant context based on the current task and project files.

---

## Decision

*   [2025-04-01 17:54:50] Prioritize updating `homeassistant` dependency before analyzing/fixing tests.

## Rationale

*   Outdated dependencies are a likely cause of test failures or incompatibilities. Updating first ensures tests are run against the target environment.

## Implementation Details

*   Plan to identify the latest `homeassistant` version.
*   Update `requirements_test.txt`.
*   Use `uv pip install -r requirements_test.txt` to update the environment.

---

## Decision

*   [2025-04-01 18:36:58] Fix `AttributeError: 'list' object has no attribute 'get'` in `climate.py`'s `SyncState` method.

## Rationale

*   The `GreeGetValues` method (called by `SyncState`) was returning a list of status values from the API, but the subsequent code in `SyncState` was attempting to access this list using dictionary methods (`.get()`), causing the error reported in the logs.

## Implementation Details

*   Modified the `try...else` block within `SyncState` (around lines 1229-1283) in `custom_components/greev2/climate.py`.
*   Added validation to check if `GreeGetValues` returns a list of the expected length.
*   If valid, the list of values (`received_data_list`) is now correctly passed along with the list of property names (`self._optionsToFetch`) to the `SetAcOptions` method, which handles updating the internal state (`self._acOptions`).
*   Improved error handling for connection issues and unexpected data formats.

---

## Decision

*   [2025-04-01 18:57:04] Add detailed diagnostic logging to temperature handling methods in `climate.py` before implementing a fix for incorrect temperature display.

## Rationale

*   The user reported the current temperature displaying as 132°F when the actual temperature is around 55°F. While a missing F-to-C conversion for the external sensor (`sensor.shed_temperature_temperature`) is suspected, adding logging first will confirm the exact values and units being processed.
*   This ensures the final fix addresses the root cause accurately.

## Implementation Details (Plan)

*   Modify `_async_update_current_temp` to log raw sensor state/unit and the final `self._current_temperature`.
*   Modify `UpdateHACurrentTemperature` to log raw `TemSen`, `TemUn`, and the final `self._current_temperature`.
*   Modify the `current_temperature` property to log the value being returned.
*   User will apply changes via Code mode, restart HA, and analyze logs.

---

## Decision

*   [2025-04-01 19:05:02] Implement Fahrenheit-to-Celsius conversion for external temperature sensor.

## Rationale

*   Diagnostic logs confirmed that the external sensor (`sensor.shed_temperature_temperature`) was providing temperature in °F, but the `_async_update_current_temp` method was storing this value directly into `self._current_temperature` without conversion.
*   Since the climate entity's internal unit is Celsius (`_attr_temperature_unit`), this caused Home Assistant to misinterpret the value and display a highly inflated temperature (e.g., 55.8°C converted to 132°F).

## Implementation Details

*   Modified `_async_update_current_temp` in `custom_components/greev2/climate.py`.
*   Added logic to check the `unit` attribute from the sensor's state.
*   If the unit is `UnitOfTemperature.FAHRENHEIT`, the code now converts the temperature value to Celsius using `(temp_value - 32.0) * 5.0 / 9.0` before storing it (rounded to 1 decimal place) in `self._current_temperature`.
*   If the unit is not Fahrenheit, the value is stored directly (assuming Celsius).
*   Removed the diagnostic logging added previously.

---

## Decision

*   [2025-04-01 19:09:26] Add unit tests for external temperature sensor conversion logic.

## Rationale

*   To ensure the recently added Fahrenheit-to-Celsius conversion in `_async_update_current_temp` works correctly and to prevent future regressions.
*   Tests should cover both Fahrenheit and Celsius inputs from the external sensor.

## Implementation Details

*   Added tests `test_async_update_current_temp_fahrenheit`, `test_async_update_current_temp_celsius`, and `test_async_update_current_temp_invalid_state` to `tests/test_update.py`.
*   Used a helper function `create_mock_state` to simulate sensor `State` objects with different values and units (`°F`, `°C`, `unavailable`).
*   Asserted that `device.current_temperature` contained the correctly converted Celsius value (or remained unchanged for invalid input).
*   Fixed related test failures in `test_update_success_full` and `test_update_sets_availability` by updating mocks to return lists instead of dicts, matching recent changes in `SyncState`.
*   Removed a stray assertion from `test_async_update_current_temp_invalid_state`.
*   Ran `pytest` and confirmed all tests passed (24 passed, 1 xfailed).

---

## Decision

*   [2025-04-01 19:15:42] Fix `PytestDeprecationWarning` related to `asyncio_default_fixture_loop_scope`.

## Rationale

*   Running `pytest` showed a deprecation warning indicating the `asyncio_default_fixture_loop_scope` option was unset and would change default behavior in future versions.
*   Setting this explicitly silences the warning and ensures consistent behavior.

## Implementation Details

*   Added `asyncio_default_fixture_loop_scope = function` to the `[pytest]` section of `pytest.ini`.
*   Initially added an inline comment which caused test errors (`KeyError`), so the comment was removed.
*   Ran `pytest` again and confirmed the warning was gone and all tests passed.

---

## Decision

*   [2025-04-01 19:17:01] Verify type hints using `mypy`.

## Rationale

*   Ensure type hints are accurate and up-to-date as a code quality measure after recent changes.

## Implementation Details

*   Ran `mypy custom_components/ tests/`.
*   `mypy` reported `Success: no issues found in 10 source files`.
*   No code changes were required.

---

## Decision

*   [2025-04-01 19:35:46] Pause `pylint` cleanup for `climate.py`.

## Rationale

*   After fixing several high-priority `pylint` issues (imports, unused code, `no-else-return`, some line lengths) in both `device_api.py` and `climate.py`, the user requested pausing further cleanup due to the number of changes made.
*   Remaining issues in `climate.py` (score 9.38/10) primarily involve extensive renaming (CamelCase to snake_case) and complexity warnings (too many lines/attributes/methods/etc.), which carry higher risk and are better addressed separately or deferred.

## Implementation Details

*   Partially addressed `pylint` issues as documented in previous steps.
*   Deferred remaining issues, particularly renaming and complexity refactoring for `climate.py`.
*   Updated Memory Bank (`progress.md`, `activeContext.md`) to reflect the paused status.

---

## Decision

*   [2025-04-01 19:50:12] Create a release automation script (`release.sh`).

## Rationale

*   Automate the process of tagging commits and creating GitHub releases to reduce manual effort and potential errors.
*   The script will handle version incrementing based on existing tags.

## Implementation Details (Plan)

*   **Script Name:** `release.sh` (Bash)
*   **Functionality:**
    *   Check prerequisites (`git`, `gh`, auth status).
    *   Verify clean working directory on `master` branch.
    *   Fetch latest tags.
    *   Find latest `X.Y.Z` tag.
    *   Calculate next patch version (e.g., `X.Y.Z` -> `X.Y.(Z+1)`).
    *   Confirm new tag with user.
    *   Create and push git tag.
    *   Create GitHub release using `gh release create <tag> --generate-notes --title "Release <tag>"`.
    *   Report success and release URL.
*   **Failure Handling:** If manual testing fails post-release, the user will fix the code and run the script again to create the *next* patch release (no automated rollback).
*   **Implementation:** Created `release.sh` in project root with the specified functionality. Added a `--dry-run` option to allow verification of commands before execution.

---

## Decision

*   [2025-04-01 20:22:10] Add integration tests for service calls before refactoring `climate.py`.

## Rationale

*   A bug (`TypeError` in `send_state_to_ac` call from `sync_state`) was missed by existing tests because they either mocked methods too high in the call stack or tested methods directly, bypassing the integration points.
*   Adding tests that call service methods (e.g., `set_hvac_mode`) and only mock the final API layer (`_api.send_command`) will provide better coverage of the internal call chain and help prevent regressions during the planned refactoring of `climate.py`.

## Implementation Details (Plan)

*   Add tests to `tests/test_command.py` (or a new file).
*   For each key service call (`set_hvac_mode`, `set_temperature`, etc.):
    *   Instantiate `GreeClimate`.
    *   Patch `device._api.send_command`.
    *   Call the service method.
    *   Assert `send_command` was called once with the correct `opt` and `p` arguments.
*   **Implementation:** Added 5 integration tests (`test_set_hvac_mode_integration`, etc.) to `tests/test_command.py`. These tests call service methods and mock only `_api.send_command`. Fixed initial failures by also mocking `gree_get_values` and setting `_first_time_run = False` in test setup. Confirmed tests pass via `pytest`. Ran `black` and `mypy` checks successfully.

---

## Decision

*   [2025-04-01 20:53:54] Fix `TypeError` in `sync_state` calling `send_state_to_ac`.

## Rationale

*   Manual testing of release 2.14.21 revealed a `TypeError` when calling services like `set_hvac_mode`.
*   The `timeout` argument was removed from the `send_state_to_ac` definition, but the call site within `sync_state` was not updated, causing the error.

## Implementation Details

*   Removed the `self._timeout` argument from the `self.send_state_to_ac()` call within the `sync_state` method in `custom_components/greev2/climate.py`.
*   Ran `pytest` to confirm tests still passed.

---

## Decision

*   [2025-04-01 20:54:13] Create release 2.14.22.

## Rationale

*   A bug was found after creating release 2.14.21. Following the 'New Patch Release' strategy, the fix was committed and a new release was created.

## Implementation Details

*   Committed the `TypeError` fix.
*   Ran `./release.sh` script.
*   Script successfully identified `2.14.21` as latest, calculated `2.14.22` as next.
*   User confirmed.
*   Script created and pushed tag `2.14.22`.
*   Script created GitHub release for `2.14.22` with auto-generated notes.

---

---

## Decision

*   [2025-04-01 22:13:12] Create release 2.14.23.

## Rationale

*   Test suite fixes and minor static analysis fixes completed. Codebase is stable for a new patch release.

## Implementation Details

*   Committed changes including test fixes (`test_update.py`), `mypy` fix (`climate.py`), `pylint` fix (`device_api.py`), and added untracked files (`const.py`, `refactor_plan_incremental.md`).
*   Ran `./release.sh` script.
*   Script successfully identified `2.14.22` as latest, calculated `2.14.23` as next.

---

## Decision

*   [2025-04-01 22:17:45] Fix bug in `device_api.get_status` response handling.

## Rationale

*   User testing of release 2.14.23 revealed logs showing the `dat` field in the status response was a list, not a dictionary as previously assumed based on test mocks.
*   The `get_status` method was incorrectly trying to process this list as a dictionary, causing it to return `None` and the device to appear offline.

## Implementation Details

*   Modified `get_status` in `custom_components/greev2/device_api.py`.
*   The code now checks if `received_json_pack['dat']` is a list.
*   If it's a list and its length matches the requested `property_names`, the list is returned directly.
*   Error handling added for missing `dat` field or if `dat` is not a list.
*   Improved the related test `test_update_gcm_key_retrieval_and_update` in `tests/test_update.py` to mock the correct list-based response structure and add assertions for state validation.

---

## Decision

*   [2025-04-01 22:21:07] Create release 2.14.24.

## Rationale

*   A bug was found and fixed after creating release 2.14.23. A new release is needed for user testing.

## Implementation Details

*   Committed the API fix and test improvement.
*   Ran `./release.sh` script.
*   Script successfully identified `2.14.23` as latest, calculated `2.14.24` as next.
*   User confirmed.
*   Script created and pushed tag `2.14.24`.
*   Script created GitHub release for `2.14.24` with auto-generated notes.
*   User confirmed.
*   Script created and pushed tag `2.14.23`.
*   Script created GitHub release for `2.14.23` with auto-generated notes.
---

## Decision

*   [2025-04-02 00:11] Refactor `climate.py` (`__init__`, `async_setup_entry`) for ConfigEntry integration (Phase 3).

## Rationale

*   Required step to complete the transition from YAML configuration to UI-based config flow.

## Implementation Details

*   Modified `GreeClimate.__init__` to accept `ConfigEntry`.
*   Extracted configuration from `entry.data` using defaults from `const.py`.
*   Removed optional entity ID parameters and state change listener setup from `__init__`.
*   Updated `climate.async_setup_entry` to instantiate `GreeClimate` using the entry and call `async_add_entities`.

---

## Decision

*   [2025-04-02 00:15] Fix resulting test failures iteratively after Config Flow refactoring. [Summarized 2025-04-02 03:12]

## Rationale

*   Address errors systematically after major code changes related to Config Flow.

## Implementation Details

*   Addressed various `mypy` errors, `TypeError`s, `InvalidSpecError`, `AssertionError`s, and `AttributeError`s across test files (`test_update.py`, `conftest.py`, `config_flow.py`, `test_init.py`) and `device_api.py` by updating fixtures, mocks, test calls, and fixing async mismatches.

---

## Decision

*   [2025-04-02 00:37] Create release 2.14.34 (Config Flow implementation).

## Rationale

*   Completed Config Flow implementation (Phases 1-3) and fixed resulting test failures. Ready for release.

## Implementation Details

*   Committed changes related to Config Flow implementation and test fixes.
*   Ran `./release.sh` script.
*   Script successfully identified `2.14.24` as latest, calculated `2.14.34` as next.
*   User confirmed.
*   Script created and pushed tag `2.14.34`.
*   Script created GitHub release for `2.14.34` with auto-generated notes.

---

## Decision

*   [2025-04-02 00:44] Fix Area/Zone not persisting from config flow.

## Rationale

*   User feedback indicated the selected Area was not being applied to the device.

## Implementation Details

*   Updated `climate.py.__init__` to extract `area_id` from `entry.data`.
*   Added `DeviceInfo` import and set `_attr_device_info` with `suggested_area=area_id`.

---

## Decision

*   [2025-04-02 00:59] Add optional external temperature sensor selector to config flow UI.

## Rationale

*   User request to allow specifying an external sensor during setup.

## Implementation Details

*   Added `CONF_TEMP_SENSOR` constant.
*   Added `EntitySelector` for temperature sensors to `config_flow.py` schema.
*   Updated `climate.py` to extract the sensor ID, re-add state listener setup in `async_added_to_hass`, and re-implement sensor update callbacks.

---

## Decision

*   [2025-04-02 01:05] Create release 2.14.35 (Config Flow fixes/enhancements).

## Rationale

*   Implemented fixes for Area persistence and added the external temperature sensor selector to the Config Flow. Ready for release.

## Implementation Details

*   Committed changes related to Area fix and temp sensor selector.
*   Ran `./release.sh` script.
*   Script successfully identified `2.14.34` as latest, calculated `2.14.35` as next.
*   User confirmed.
*   Script created and pushed tag `2.14.35`.
*   Script created GitHub release for `2.14.35` with auto-generated notes.

---

## Decision

*   [2025-04-02 01:07] Create dedicated unit tests for `GreeDeviceApi`.

## Rationale

*   Improve test suite robustness by directly testing the API communication layer, reducing reliance on mocking within higher-level tests.

## Implementation Details

*   Created `tests/test_device_api.py`.
*   Implemented initial tests for `__init__` (V1/V2) and `bind_and_get_key` (V1/V2 success, failure scenarios).

---

## Decision

*   [2025-04-02 02:27] Refactor `device_api.py` methods to async and update tests.

## Rationale

*   Align API communication with Home Assistant's async architecture.
*   Address `RuntimeWarning`s related to unawaited coroutines in tests.
*   Improve test structure and maintainability.

## Implementation Details

*   Converted `bind_and_get_key`, `_bind_and_get_key_v1`, `_bind_and_get_key_v2`, `_fetch_result`, `send_command`, `get_status` in `device_api.py` to `async def`.
*   Updated calls within `device_api.py` and `climate.py` (`_async_sync_state`, `_async_update_internal`) to use `await`.
*   Refactored `tests/test_device_api.py` into separate files (`test_init.py`, `test_bind.py`, `test_get_status.py`, `test_send_command.py`) within a new `tests/device_api/` directory.
*   Updated all API tests to use `async def` and `await`, replacing `MagicMock` with `AsyncMock` where appropriate for patched async methods.
*   Fixed `RuntimeWarning`s by ensuring `AsyncMock` side effects were awaited or handled correctly.
*   Ran `pytest` and confirmed all tests passed.

---

## Decision

*   [2025-04-02 02:53] Refactor `climate.py` state management and feature detection into `climate_helpers.py`.

## Rationale

*   Reduce complexity and size of `GreeClimate` class in `climate.py`.
*   Improve maintainability and testability by separating concerns.
*   Followed the plan outlined in `memory-bank/climate_refactor_plan.md`.

## Implementation Details

*   Created `custom_components/greev2/climate_helpers.py`.
*   Implemented `GreeClimateState` class to manage `_ac_options` and provide state properties.
*   Implemented async `detect_features` function to handle feature discovery.
*   Refactored `GreeClimate.__init__` to initialize and use `GreeClimateState`.
*   Refactored `GreeClimate._async_sync_state` to use `detect_features` and `GreeClimateState.update_options`.
*   Refactored `GreeClimate` properties (`hvac_mode`, `target_temperature`, etc.) to delegate to `GreeClimateState`.
*   Removed obsolete methods (`set_ac_options`, `update_ha_*`) from `GreeClimate`.
*   Created `tests/test_climate_helpers.py` with unit tests for the new helper module.
*   Adapted existing tests (`test_properties.py`, `test_update.py`, `tests/commands/test_commands.py`) to the refactored structure.
*   Fixed test failures related to the refactoring.

---

## Decision

*   [2025-04-02 03:38] Refactor config flow to be dynamic based on device model selection using JSON configuration files.

## Rationale

*   Simplify user setup by guiding model selection first.
*   Reduce binding errors by using known-correct parameters (especially encryption version) from model-specific JSON files.
*   Handle device variations more robustly and enable features based on device capabilities defined in JSON.
*   Address user reports of binding timeouts and inflexible configuration.

## Implementation Details

*   Detailed plan saved in `memory-bank/dynamic_config_flow_plan.md`.
*   Involves creating `devices/` directory with JSON configs, modifying `config_flow.py` for multi-step flow, updating `climate.py` to load/use configs, and updating tests/docs.
---

## Decision

*   [2025-04-02 11:42] Define standard release workflow using `prerelease.sh` and `release.sh`.

## Rationale

*   To establish a clear, consistent, and semi-automated process for preparing and executing releases, separating preparation from the final tagging/release action and allowing for manual review and commit message crafting.

## Implementation Details

*   **Workflow:**
    1.  **Run `./prerelease.sh`:** Calculates next version, updates `manifest.json`, stashes `memory-bank/`, lists changed files. Provides instructions for Roo.
    2.  **Roo (AI): Formulate Commit Message:** Reviews file list, formulates commit message (title & body). Presents message to User.
    3.  **User: Approve Commit Message:** Reviews message presented by Roo.
    4.  **Roo (AI): Save Commit Message:** Saves approved message to `commit_msg.txt` in project root.
    5.  **Run `./release.sh --commit-message-file commit_msg.txt`:** Script automatically handles `git add .`, `git commit --file=commit_msg.txt`, `git push`, cleanup of `commit_msg.txt`, tagging, and GitHub release creation (prompting user only before tagging/releasing).


---

## Decision

*   [2025-04-04 14:08:44] Refine strategy for selecting elements using Puppeteer MCP server after troubleshooting failures.

## Rationale

*   Initial attempts to interact with the Home Assistant community forum using Puppeteer failed due to incorrect CSS selectors for dynamic elements (category dropdown).
*   Relying solely on common patterns and guessing selectors proved inefficient and unreliable.
*   Obtaining the actual HTML structure (either via user input or potentially `puppeteer_evaluate`) was necessary to identify the correct selector.

## Implementation Details (Learnings/Strategy)

*   **Initial Approach:** Try common/standard selectors first for efficiency.
*   **On Failure:** Do *not* continue guessing blindly.
*   **Gather Context:** Use `puppeteer_evaluate` to retrieve the HTML structure (`innerHTML`) of the relevant parent container or the specific element if possible.
*   **Analyze HTML:** Identify robust selectors (e.g., `data-*` attributes, IDs) from the retrieved HTML.
*   **Retry Action:** Use the refined selector.
*   **User Fallback:** If retrieving/analyzing HTML via `evaluate` fails or is impractical, ask the user to provide the relevant HTML snippet or perform the action manually.
*   **Acknowledge Tool Limits:** Understand that Puppeteer cannot passively monitor user actions; interaction relies on specific command execution.
*   `prerelease.sh`: Handles preparation (version, manifest, stash, list files). Requires manual execution. Dry run available (`--dry-run`).
*   `release.sh`: Handles commit, push, tag, GitHub release. Requires `--commit-message-file` argument pointing to the message file created by Roo after approval. Dry run available (`--dry-run`).