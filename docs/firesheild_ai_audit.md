# FireShield AI Audit

**Audit date:** 2026-09-07  
**Audited source (read-only):** `C:\Users\Nithinvarma\Documents\Codex\2026-07-06\i\work\fireshield-ai`

## Result

FireShield AI exists locally and is a production-shaped, multi-service Fire Safety platform. The separately found `outputs\FireShield-AI-v1\fireshield-ai` directory is an output copy with the same top-level structure; `work\fireshield-ai` is treated as the active source project.

No FireShield AI files were modified during this audit.

## Verified components

| Area | Finding |
|---|---|
| Platform structure | Monorepo-style project containing API, mobile application, risk engine, simulator, infrastructure, and documentation |
| Backend | Node.js, TypeScript, Express, Zod validation, Helmet, Pino logging |
| Database | PostgreSQL; `buildings`, `devices`, `readings`, and `alerts` tables |
| Live-state cache | Redis, with recent per-device telemetry cached for five minutes |
| Device transport | MQTT topic `fireshield/v1/devices/{deviceId}/telemetry` and authenticated REST ingestion |
| REST API | `POST /v1/telemetry`, device latest/history endpoints, and alerts endpoint |
| Device authentication | API key via `x-api-key` for REST ingestion; MQTT development broker is configured locally |
| Risk engine | Python/FastAPI explainable rule engine, called by the API before persistence |
| Mobile/dashboard | Flutter/Riverpod operations dashboard polling the latest device state |
| Notifications | Alerts are persisted; actual mobile push delivery is planned but not implemented |
| Simulator | Python/Paho MQTT simulator creates normal and correlated fire-like scenarios; it is explicitly synthetic |
| Containerization | Docker Compose for PostgreSQL, Redis, Mosquitto, API, risk engine, and simulator |

## Existing telemetry model

The API validates and accepts these fields:

```text
deviceId, recordedAt, temperature, humidity, smoke, co, co2,
battery, signalStrength, temperatureRate
```

The API calculates and persists an explainable risk assessment with score, level, confidence, explanations, and a three-level alert. It also computes a temperature rate from the previous cached reading when ingesting data.

## Reusable assets

- MQTT device-ingestion pathway and REST fallback.
- Strict telemetry validation and API-key authentication for HTTP ingestion.
- PostgreSQL readings and alert storage.
- Isolated risk-engine service and automated tests.
- Flutter dashboard with risk, temperature, humidity, smoke, CO, CO2, and battery indicators.
- Docker Compose development environment and simulator to test end-to-end platform flow.

## Gap between current platform and planned ESP32 prototype

| Planned prototype signal | Current platform equivalent | Required future change |
|---|---|---|
| MQ-2 gas reading | `smoke` | Map calibrated MQ-2 signal to `smoke` initially; retain raw value and calibration metadata when the data model evolves |
| Flame sensor | None | Add optional `flameDetected` field and risk-engine evidence rule |
| BME280 | `temperature`, `humidity` | Directly compatible |
| DHT22 simulation | `temperature`, `humidity` | Directly compatible, but label source as simulation |
| ESP32 power/connectivity | `battery`, `signalStrength` | Populate only when hardware measurements are available |
| Local status/risk | Server assessment | Add optional edge-assessment fields; backend should retain an independent assessment for comparison |
| Room ID | Device table `room` | Register each ESP32 device with its room before use |

## Integration recommendation

Use the existing MQTT contract first, as it already supports ESP32-compatible telemetry:

```text
ESP32 local detector
  -> local OLED / LED / buzzer decision even offline
  -> MQTT: fireshield/v1/devices/{deviceId}/telemetry
  -> FireShield API validation and risk assessment
  -> PostgreSQL + Redis
  -> Flutter dashboard and persisted alerts
```

Keep firmware separate from FireShield AI. Implement a small firmware transport adapter that emits the platform's existing telemetry fields. Add fields such as `flameDetected`, `gasRaw`, `firmwareVersion`, and edge-risk metadata through a backward-compatible schema update after the temperature-only prototype works.

## Verified limitations and risks

- The current risk engine is an interpretable rules engine, not a trained ML model. No ML accuracy should be claimed.
- The simulator is synthetic and cannot validate physical detection performance.
- The dashboard uses a fixed demo device ID and room label.
- MQTT in the local Compose setup is development-grade; device certificates, tenant authorization, and managed-broker hardening remain planned work.
- Firebase Auth, role-based access control, FCM, encrypted secret management, audit logging, and signed OTA firmware are documented future hardening, not currently operational features.
- Platform alerts are database records today; tested user/mobile push delivery is not present.

## Recommended next milestone

Build only the local temperature prototype in the Fire_Safety workspace: ESP32 + DHT22 simulation + serial logs + configurable temperature trend/persistence states. When that works, publish compatible telemetry to this existing FireShield AI platform without changing its current project structure.
