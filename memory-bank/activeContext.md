# Active Context

  This file tracks the project's current status, including recent changes, current goals, and open questions.
  2025-04-01 17:54:35 - Log of updates made.

*

## Current Focus

*   Manual testing of release 2.14.22.
*   Paused `pylint` cleanup; focus on test suite improvement / dependency updates.
*   Update `homeassistant` dependency to the latest version.

## Recent Changes

*   Memory Bank initialized.
*   `productContext.md` created.
*   [2025-04-01 18:36:45] Fixed `AttributeError` in `climate.py`'s `SyncState` method by correctly handling list data from the API.
*   [2025-04-01 18:57:19] Decided to add diagnostic logging to `climate.py` temperature methods before fixing display issue.

*   [2025-04-01 19:04:39] Implemented F-to-C conversion in `_async_update_current_temp` for external temp sensor.
*   [2025-04-01 19:09:04] Decided to add tests for external sensor temperature conversion logic.
*   [2025-04-01 19:13:05] Added unit tests for external sensor temperature conversion (F-to-C, C) to `tests/test_update.py` and verified they pass.
## Open Questions/Issues
*   [2025-04-01 19:15:21] Fixed `PytestDeprecationWarning` by setting `asyncio_default_fixture_loop_scope = function` in `pytest.ini`.
*   [2025-04-01 19:16:46] Verified type hints using `mypy`; no issues found.
*   [2025-04-01 19:50:40] Planned release automation script (`release.sh`).
*   [2025-04-01 19:35:22] Partially addressed `pylint` issues in `device_api.py` (score 9.51) and `climate.py` (score 9.38); paused further cleanup.
*   [2025-04-01 19:52:23] Created release automation script (`release.sh`).
*   [2025-04-01 20:22:43] Decided to add integration tests for service calls before refactoring `climate.py`.
*   [2025-04-01 20:43:55] Added integration tests for service calls (`set_hvac_mode`, `set_temperature`, `set_fan_mode`, `turn_on`, `turn_off`) to `tests/test_command.py`. Fixed initial failures by mocking `gree_get_values` and setting `_first_time_run=False`.
*   [2025-04-01 20:48:57] Ran `black` formatting and `mypy` type checking; no issues found.
*   [2025-04-01 20:53:54] Fixed `TypeError` bug in `climate.py` found during release testing.
*   [2025-04-01 20:54:13] Created release 2.14.22 using `release.sh`.

*   [2025-04-01 22:05:36] Fixed 5 failing tests in `tests/test_update.py` by patching `_api._is_bound` and correcting `device_api.get_status` return type.
*   [2025-04-01 22:08:57] Fixed `mypy` error in `climate.py` related to `update_encryption_key` call.
*   [2025-04-01 22:10:29] Fixed `pylint` warning (misplaced docstring) in `device_api.py`.
*   [2025-04-01 22:13:12] Created release 2.14.23 including test fixes, static analysis fixes, and new `const.py`/`refactor_plan_incremental.md` files.
*   What is the exact latest stable version of the `homeassistant` library on PyPI?
*   What specific tests are failing or need improvement?
*   What is the preferred method for updating the virtual environment (`uv pip install --upgrade` directly vs. updating `requirements_test.txt` first)?