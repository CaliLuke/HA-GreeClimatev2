# Test Suite Improvement Plan (2025-04-01)

This document outlines the plan to improve the test suite for the `HA-GreeClimatev2` project.

**Goal:** Update dependencies and improve test coverage/reliability without modifying the core component code (`climate.py`, `device_api.py`).

**Phase 1: Dependency Update (Requires Code/Default Mode with Terminal Access)**

1.  **Update `homeassistant`:** Execute `uv pip install --upgrade homeassistant` in the project's virtual environment to get the absolute latest version.
2.  **Install/Update Other Test Dependencies:** Execute `uv pip install -r requirements_test.txt` to ensure all other test dependencies are installed and compatible.

**Phase 2: Test Suite Analysis (Architect Mode)**

3.  **Read Test Files:** Read the contents of:
    *   `tests/conftest.py`
    *   `tests/test_command.py`
    *   `tests/test_init.py`
    *   `tests/test_properties.py`
    *   `tests/test_update.py`
4.  **Analyze Test Structure:** Review the test files for:
    *   Use of `pytest` fixtures (especially `hass` fixture).
    *   Asynchronous test patterns (`pytest-asyncio`).
    *   Mocking strategies (e.g., `unittest.mock.patch`, custom mocks) for `socket`, `Crypto.Cipher`, and potentially `homeassistant` helpers.
    *   Coverage of different component functionalities (setup, state updates, service calls like `set_temperature`, `turn_on`, `turn_off`, etc.).
    *   Assertions used.
    *   Any obvious errors, commented-out tests, or `TODO` comments.
    *   Potential issues arising from the `homeassistant` update (e.g., changed APIs, state representations).

**Phase 3: Test Improvement Plan (Architect Mode)**

5.  **Identify Issues & Propose Solutions:** Based on the analysis, pinpoint specific tests that are failing or inadequate. Outline specific changes needed:
    *   Updating mocks to match new `homeassistant` APIs.
    *   Adjusting assertions based on expected state changes.
    *   Adding new tests for features not currently covered.
    *   Refactoring tests for clarity or efficiency.
    *   Ensuring proper async handling.
    *   Conceptual Flow:
        ```mermaid
        graph TD
            A[Update homeassistant] --> B(Analyze Tests);
            B --> C{Identify Issues};
            C -- Failing Test --> D[Plan Fixes];
            C -- Inadequate Test --> E[Plan Improvements/Additions];
            C -- No Issues --> F[Ready for Test Execution];
            D --> F;
            E --> F;
        ```

**Phase 4: Implementation & Verification (Requires Code & Test Modes)**

6.  **Handoff to Code Mode:** Provide the detailed plan for test modifications to the Code mode for implementation.
7.  **Handoff to Test Mode:** Request execution of the test suite using `pytest tests/`. Analyze results and iterate with Code mode if failures persist until all tests pass.

---