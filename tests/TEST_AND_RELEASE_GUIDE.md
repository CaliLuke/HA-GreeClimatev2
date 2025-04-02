# Gree Climate V2 - Testing and Release Guide

This document provides instructions for setting up the test environment, running tests, and performing releases for the Gree Climate V2 custom component, following recommended `uv` practices.

## Testing

### Setup

Follow these steps to set up your development environment using `uv`.

1.  **Python Version:** Ensure you have Python 3.13 or later installed, matching the requirement in `pyproject.toml`.

2.  **Create Virtual Environment:** Use `uv` to create and activate a virtual environment:
    ```bash
    # Create the virtual environment (e.g., named .venv)
    uv venv .venv
    # Activate the environment (syntax may vary based on your shell)
    source .venv/bin/activate
    ```

3.  **Install Project & Dependencies:**
    *   First, make the current project available in editable mode within the environment:
        ```bash
        # Add the current directory (.) as an editable package
        uv add --editable .
        ```
    *   Then, install the testing dependencies defined in the `[test]` extra section of `pyproject.toml`:
        ```bash
        # Install only the dependencies listed under the 'test' extra
        uv pip install --extra test
        ```
    *Your virtual environment now contains the necessary external test packages and a link to your local project code.*

4.  **Adding New Dependencies (if necessary):** Use `uv add` to add new dependencies. This command modifies `pyproject.toml` and installs the package.
    *   **Core Dependency** (required for the component itself):
        ```bash
        # Adds to [project.dependencies] in pyproject.toml
        uv add <package_name>
        ```
    *   **Testing Dependency** (only needed for running tests):
        ```bash
        # Adds to [project.optional-dependencies.test] in pyproject.toml
        uv add --optional test <package_name>
        ```
    *After adding dependencies, you might need to run `uv pip install --extra test` again if you added a new *testing* dependency, or just ensure your environment is generally synced.*


5.  **Compatibility Note (Python 3.13+):**
    *   Newer Python versions (like 3.13+) may introduce changes that require updated versions of testing tools (`pytest`, `pytest-homeassistant-custom-component`, `pytest-timeout`, etc.) to function correctly.
    *   If you encounter errors during test execution (especially `TypeError` related to `lineno` or `ModuleNotFoundError: No module named 'distutils'`), ensure your testing dependencies are up-to-date by running:
        ```bash
        # Update specific test dependencies if needed
        uv add --optional test pytest pytest-homeassistant-custom-component pytest-timeout
        # Or, attempt to update all test dependencies (use with caution)
        # uv pip install --upgrade --extra test
        ```
    *   Keeping dependencies reasonably current, as defined in `pyproject.toml`, is recommended.

### Running Tests

Once the environment is activated and dependencies are installed, you can run the tests using `pytest`.

*   **Run all tests:**
    ```bash
    pytest -v
    ```
    *(The `-v` flag provides verbose output, showing individual test results.)*

*   **Run tests in a specific file:**
    ```bash
    pytest -v tests/test_climate.py # Example
    ```

*   **Run tests in a specific directory:**
    ```bash
    pytest -v tests/device_api/
    ```

*   **Run a specific test by name (using `-k`):**
    ```bash
    pytest -v -k test_async_turn_on # Example
    ```

*   **Run tests with coverage:**
    ```bash
    pytest --cov=custom_components.greev2 --cov-report=term-missing tests/
    ```

### Test Structure

The tests are organized within the `tests/` directory:

*   `tests/conftest.py`: Contains shared fixtures, constants, and helper functions used across multiple test files.
*   `tests/test_*.py` (Root level): Tests for core functionality like initialization (`test_init.py`), properties (`test_properties.py`), updates (`test_update.py`), config flow (`test_config_flow.py`), and helpers (`test_climate_helpers.py`).
*   `tests/commands/`: Contains tests specifically for service calls and command logic (`test_commands.py`).
*   `tests/device_api/`: Contains unit tests specifically for the `GreeDeviceApi` class, broken down by functionality (e.g., `test_init.py`, `test_bind.py`, `test_get_status.py`, `test_send_command.py`).

## Release Process

**Note on RooFlow Workflow:** The `prerelease.sh` script includes a step to stash the `memory-bank/` directory. This is specific to a development workflow involving RooFlow ([https://github.com/GreatScottyMac/RooFlow](https://github.com/GreatScottyMac/RooFlow)) where the memory bank contains AI context. This step might fail or be unnecessary if you are not using this specific workflow.

A standard workflow using helper scripts is defined for creating releases. This ensures consistency and automates several steps.

**Workflow:**

1.  **Preparation (`prerelease.sh`):**
    *   Ensure your local `master` (or main) branch is up-to-date and clean.
    *   Run the script: `./prerelease.sh`
    *   The script will:
        *   Calculate the next patch version based on existing Git tags.
        *   Update the `version` field in `custom_components/greev2/manifest.json`.
        *   Temporarily stash the `memory-bank/` directory (to avoid including it in the release commit).
        *   List all changed/staged files that will be part of the release commit.
        *   Provide instructions for the next step (formulating the commit message).
    *   Use the `--dry-run` flag (`./prerelease.sh --dry-run`) to see the calculated version and file list without modifying `manifest.json` or stashing.

2.  **Formulate Commit Message (Developer/AI):**
    *   Review the list of changed files provided by `prerelease.sh`.
    *   Consult Git history (`git log`) if needed.
    *   Create a concise and informative commit message (title and body) summarizing the changes included in this release.

3.  **Save Commit Message:**
    *   Save the formulated commit message to a file named `commit_msg.txt` in the project root directory.

4.  **Execution (`release.sh`):**
    *   Run the script, providing the path to the commit message file:
        ```bash
        ./release.sh --commit-message-file commit_msg.txt
        ```
    *   The script will:
        *   Stage all current changes (`git add .`).
        *   Commit the changes using the message from `commit_msg.txt` (`git commit --file=commit_msg.txt`).
        *   Push the commit to the remote repository (`git push`).
        *   Clean up by removing `commit_msg.txt`.
        *   Prompt for confirmation before creating and pushing the Git tag (e.g., `2.14.36`).
        *   Prompt for confirmation before creating the corresponding GitHub release using `gh release create`, automatically generating release notes based on commits since the last tag.
    *   Use the `--dry-run` flag (`./release.sh --commit-message-file commit_msg.txt --dry-run`) to see the commands that *would* be executed (including commit, push, tag, release) without actually performing them.

**Important Notes:**

*   Ensure you have the GitHub CLI (`gh`) installed and authenticated for the GitHub release creation step.
*   The `memory-bank/` directory is automatically stashed by `prerelease.sh` and should be restored manually (`git stash pop`) after the release process is complete if needed.
*   If manual testing after a release reveals critical bugs, fix the code, commit the fixes, and run the *entire* release process again (`prerelease.sh` followed by `release.sh`) to create the *next* patch release (e.g., `2.14.37`). There is no automated rollback.