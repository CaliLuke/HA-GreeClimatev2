# Product Context

This file provides a high-level overview of the project and the expected product that will be created. Initially it is based upon projectBrief.md (if provided) and all other available project-related information in the working directory. This file is intended to be updated as the project evolves, and should be used to inform all other modes of the project's goals and context.
2025-04-01 17:54:22 - Log of updates made will be appended as footnotes to the end of this file.

*

## Project Goal

*   Provide a Home Assistant integration for Gree Climate devices using the v2 protocol.

## Key Features

*   Control basic climate functions (On/Off, Temperature, HVAC Mode, Fan Mode, Swing Mode).
*   Support for optional features like Lights, XFan, Health, PowerSave, Sleep, 8-degree Heat, Air, Anti-Direct Blow.
*   Support for external sensors (temperature, lights).
*   Support for different encryption versions (v1 ECB, v2 GCM).
*   Refactored API communication into `device_api.py`.

## Overall Architecture

*   Home Assistant custom component (`custom_components/greev2`).
*   `climate.py`: Implements the `ClimateEntity` platform.
*   `device_api.py`: Handles direct communication (UDP sockets, encryption/decryption) with the Gree device.
*   Configuration via `configuration.yaml` or UI flow (TBD).
*   Testing via `pytest` using `requirements_test.txt`.