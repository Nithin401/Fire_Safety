# Milestone 2 Test Plan

## Firmware checks

| Scenario | Expected result |
|---|---|
| DHT22 at stable room temperature | `SAFE`; green LED; no buzzer |
| Gradual sustained warming | `WARNING` after evidence is confirmed |
| Sustained high temperature/rise | `HIGH_RISK` or `FIRE`; red LED and buzzer |
| Brief noisy high spike | Must not immediately become `FIRE` because persistence is required |
| DHT22 read failure | Serial reports a sensor error and does not issue a fabricated risk assessment |
| Wi-Fi unavailable | Local OLED/LED/buzzer behavior remains available; this first firmware slice has no Wi-Fi dependency |

## Platform checks after transport is enabled

1. Publish a valid reading on `fireshield/v1/devices/{deviceId}/telemetry`.
2. Verify the reading is persisted and visible through `GET /v1/devices/{id}/latest`.
3. Verify a high-risk assessment creates a FireShield alert record.
4. Verify the selected notification provider reports delivery separately from alert creation.
5. Test duplicate telemetry, offline device, broker outage, failed delivery, and alert resolution.

## Build status

PlatformIO CLI was not installed or available in this environment at implementation time, so an ESP32 compile and Wokwi run could not be executed here. Source structure and serial/data formats were reviewed, but hardware behavior remains to be built and tested in VS Code/Wokwi.
