# Smart Fire Detection & Response — Proposed System Architecture

**Status:** proposed architecture; no production or safety validation has been performed.

## Architectural decision

Keep the ESP32 edge system and FireShield AI platform as separate projects connected by a versioned device-data contract. The ESP32 makes local safety decisions first; FireShield AI receives telemetry for visualization, alerts, history, analytics, and device management when connectivity is available.

```text
Physical sensors                 ESP32 edge device                         FireShield AI platform
BME280 / MQ-2 / flame     ->    sensor adapters                   ->      device connector
                                filtering + validity checks               normalized ingestion API / MQTT
                                temperature risk engine                   persistence + analytics
                                local state machine                       dashboard + notifications
                                OLED / buzzer / LEDs                      multi-device location estimate
                                         |                                         |
                                         +-- works when offline --+                 |
                                                                              cloud connectivity optional
```

For simulation only, a DHT22 substitutes for BME280 temperature/humidity sensing. It is not electrically or functionally identical to the physical BME280; both must be represented behind a sensor abstraction.

## Responsibility boundaries

| Component | Responsibility | Must not depend on |
|---|---|---|
| Sensor adapters | Read and validate BME280/DHT22, MQ-2, and flame inputs | Dashboard or cloud availability |
| Edge detection | Filtering, baseline/trend calculations, persistence, risk and status | Internet access |
| Local interface | OLED, buzzer, status LEDs | Backend acknowledgement |
| Device transport | Publish telemetry and receive safely constrained configuration | Sensor-specific internals |
| FireShield AI connector | Authenticate, validate, normalize, and persist device telemetry | A particular ESP32 sensor model |
| Platform | Dashboard, alerts, historical views, analytics, fleet management | Direct GPIO access |
| Future response controller | Explicit safety interlocks and manual override only | Automatic claims of safe suppression |

## Initial device-data contract

Use a transport-neutral JSON envelope for REST or MQTT. The same fields can be serialized as CSV on serial/SD storage.

```json
{
  "schemaVersion": "1.0",
  "deviceId": "esp32-room-1",
  "roomId": "ROOM_1",
  "timestamp": "2026-09-07T12:00:00Z",
  "readings": {
    "temperatureC": 28.4,
    "humidityPercent": 61.2,
    "gasRaw": 0,
    "flameDetected": false,
    "temperatureRateCPerMin": 0.1
  },
  "assessment": {
    "riskScore": 5,
    "status": "SAFE",
    "algorithmVersion": "prototype-temperature-v1"
  },
  "connectivity": { "wifi": true },
  "location": { "label": "Room 1" }
}
```

Permitted initial `status` values are `SAFE`, `WARNING`, `HIGH_RISK`, and `FIRE`. Risk scores, thresholds, and state transitions are prototype values requiring controlled experimental validation; they are not fire-safety certifications.

## Proposed interfaces

### Edge-to-platform telemetry

- Existing MQTT topic: `fireshield/v1/devices/{deviceId}/telemetry`, or
- Existing HTTPS endpoint: `POST /v1/telemetry` with an `x-api-key`.

The audit verified that the existing platform supports both transports. The backend already validates readings and records MQTT ingestion failures separately; production authentication and broker controls still require hardening.

### Platform-to-edge configuration

The platform may later send non-emergency configuration (sampling interval, device label, approved threshold profile) through a separate versioned channel. The edge device must retain a known-good local configuration and must never require cloud approval to signal a locally detected dangerous condition.

### Alerts

The platform converts a normalized `HIGH_RISK` or `FIRE` assessment into an alert event. Until a notification provider is built and tested, alerts are an interface design—not an operational mobile-alert claim.

## Multi-room location estimate

Each device owns one declared `roomId`. The backend compares current risk assessments from valid, recently connected nodes and can report the highest-risk room as an *estimated affected location*. This is not precise fire localization.

## Hardware constraints recorded for implementation

| Device | Planned ESP32 connection | Note |
|---|---|---|
| DHT22 (simulation) | GPIO 4 | Simulation substitute only |
| MQ-2 analog output | GPIO 34 | GPIO 34 is input-only; physical module output must be kept within 3.3 V using appropriate protection/level shifting |
| Flame sensor digital output | GPIO 27 | Confirm active logic and module voltage during integration |
| OLED I2C SDA / SCL | GPIO 21 / GPIO 22 | Keep all pin assignments centralized |

Do not connect experimental response hardware to 230 V mains. Water-based response must not be assumed safe around energized electrical equipment.

## Planned repository boundaries

```text
Fire_Safety/
├── firmware/                 # ESP32 project and local-risk logic
├── data/                     # explicitly separated synthetic and future real data
├── ml/                       # pipeline only; training requires labeled experimental data
├── docs/                     # engineering decisions and test evidence
└── tests/                    # deterministic logic and contract tests

FireShield-AI/                # separate existing platform; preserved pending audit
```

## What can be decided now

1. The first working prototype should be local-only: ESP32 + simulated DHT22 + serial output + temperature trend/persistence risk engine.
2. Firmware pin definitions and sensor interfaces should be centralized before hardware-specific logic is added.
3. Synthetic data may test file formats, dashboards, and pipelines, but must remain labelled `SYNTHETIC / SIMULATION DATA — NOT REAL EXPERIMENTAL DATA`.
4. ML evaluation and any reported accuracy wait for sufficiently large, labeled real experimental data.

## Pending FireShield AI audit decisions

- Exact ESP32 firmware transport adapter implementation.
- Backward-compatible addition of raw MQ-2 and flame-sensor data.
- Device registration and room provisioning workflow.
- Production MQTT authentication and notification delivery design.

## Current milestone outcome

Milestone 1 is complete for the accessible workspace: FireShield AI was not found, the absence was documented, and a non-destructive integration architecture was proposed. Implementation should wait until FireShield AI is added for audit and this architecture is approved.
