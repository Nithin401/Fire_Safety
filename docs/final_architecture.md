# FireShield AI — Final System Architecture (v2.0 As-Built)

This document reflects the actual implemented and validated architecture of the FireShield AI platform across edge firmware, machine learning, cloud backend, and mobile applications.

---

## 1. System Topology & Data Flow

```text
                                  PHYSICAL / SIMULATED ENVIRONMENT
                       [ Flame IR (A0/GPIO35) ]  [ DHT22 Temp/Hum ]  [ MQ-2 Gas/Smoke ]
                                              │
                                              ▼
 ┌─────────────────────────────────────────────────────────────────────────────────────────┐
 │                            ESP1 DETECTION & TELEMETRY NODE                              │
 │  - Real-time Sampling & Normalization                                                   │
 │  - Moving Median Baseline Tracking & Persistence Confirmation                           │
 │  - Sweeping Search Servo (0°-180°) & Peak Angle Extraction (direction_engine.h)        │
 │  - Prominence Direction Confidence Scoring                                              │
 └────────────────────────────┬────────────────────────────────────────────┬───────────────┘
                              │                                            │
                        (ESP-NOW Mesh)                                (HTTPS POST)
                       2.4GHz Binary Pkt                              X-API-Key Auth
                              │                                            │
                              ▼                                            ▼
 ┌──────────────────────────────────────────┐    ┌───────────────────────────────────────────┐
 │         ESP2 RESPONSE NODE               │    │         CLOUD RUN BACKEND SERVER          │
 │  - Packet Header & Checksum Verification │    │  - Flask REST API (tools/backend_server.py)│
 │  - Aim Servo Offset & Limits Calibration │    │  - Multi-Sensor Feature Pipeline          │
 │  - Extinguisher Relay Switching          │    │  - Hybrid Risk Engine (Rule + ONNX Model) │
 │  - 3,000 ms Watchdog Failsafe Interlock  │    │  - Rate-Limited Alert Dispatcher          │
 │  - Local High-Decibel Buzzer & Alarm LED │    │  - Complete Alert Audit Trail             │
 └──────────────────────────────────────────┘    └─────────────────────┬─────────────────────┘
                                                                       │
                                                       (Firebase Admin / Firestore Sync)
                                                                       │
                                      ┌────────────────────────────────┴───────────────────┐
                                      ▼                                                    ▼
                       ┌────────────────────────────┐                       ┌────────────────────────────┐
                       │    CLOUD FIRESTORE DB      │                       │     ALERTS & DISPATCH      │
                       │  - devices/{id}            │                       │  - FCM Mobile Push (Topic) │
                       │  - devices/{id}/readings   │                       │  - Telegram Operations Bot │
                       │  - alerts/{id}             │                       │  - In-Memory Fallback      │
                       └──────────────┬─────────────┘                       └────────────────────────────┘
                                      │
                             (Real-time Streams)
                                      │
              ┌───────────────────────┴───────────────────────┐
              ▼                                               ▼
 ┌─────────────────────────────┐               ┌─────────────────────────────┐
 │  FIRESHIELD AI FLUTTER APP  │               │   INTERNAL WEB OPS MONITOR  │
 │  - Live Telemetry Dashboard │               │  - Single-Page Console      │
 │  - Multi-Sensor Time Series │               │  - Live Fleet Status Cards  │
 │  - Radial Fire Aim Compass  │               │  - Dynamic Risk Gauges      │
 │  - Alert Center & History   │               │  - 1-Click Demo Injectors   │
 └─────────────────────────────┘               └─────────────────────────────┘
```

---

## 2. Interface Contracts

### 2.1 Edge Binary Packet (`firmware/include/packet_contract.h`)
- **Transport**: ESP-NOW (2.4 GHz raw 802.11 vendor frame).
- **Structure**:
  `uint8_t header (0xAA) | uint8_t fire | uint8_t angle (0-180) | uint32_t packetID | uint8_t riskScore | uint16_t flameRaw | uint8_t checksum`

### 2.2 Cloud REST Telemetry Contract (`POST /api/telemetry`)
- **Headers**: `X-API-Key: fireshield_local_dev_key_2026`, `Content-Type: application/json`
- **Body**:
  ```json
  {
    "device_id": "dev_001",
    "room_id": "Kitchen",
    "flame_raw": 150,
    "fire_angle": 45,
    "is_fire": true,
    "temp_c": 72.0,
    "humidity": 35.0,
    "gas_raw": 620,
    "smoke_raw": 650,
    "esp_timestamp_ms": 128490
  }
  ```

---

## 3. Safety Hierarchy
1. **Physical Failsafe**: 3,000 ms communications timeout immediately closes suppression relay.
2. **Deterministic Safety Backstop**: Persistent threshold violations trigger emergency response regardless of ML output.
3. **ML Advisory Layer**: Suppresses false alarms from single-channel transient optical noise (e.g. camera flash, lighter glance).
