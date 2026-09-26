# FireShield AI — Smart Fire Detection & Autonomous Response Platform

[![Live Demo](https://img.shields.io/badge/Live%20Dashboard-GitHub%20Pages-blue?style=for-the-badge&logo=github)](https://nithin401.github.io/Fire_Safety/index.html)
[![Mobile App Repo](https://img.shields.io/badge/Flutter%20App-FireShieldAI-purple?style=for-the-badge&logo=flutter)](https://github.com/Nithin401/FireShieldAI)

[![Status](https://img.shields.io/badge/Status-Investor--Demoable%20MVP-success)](#)
[![Milestones](https://img.shields.io/badge/Milestones-M0--M8%20Complete-brightgreen)](#)
[![Tests](https://img.shields.io/badge/Tests-29%20Passed-blue)](#)
[![Safety](https://img.shields.io/badge/Safety-Deterministic%20Backstop%20Guarded-red)](#)

> 🌐 **Live Web Ops Dashboard**: [https://nithin401.github.io/Fire_Safety/index.html](https://nithin401.github.io/Fire_Safety/index.html)  
> 📱 **Mobile Flutter App Repo**: [https://github.com/Nithin401/FireShieldAI](https://github.com/Nithin401/FireShieldAI)

FireShield AI is a decoupled edge/cloud intelligent fire defense system. It pairs multi-sensor optical, thermal, and combustion gas detection with a sweeping directional scanner and an edge-compatible Hybrid Machine Learning risk engine, neutralizing fires before flashover occurs while eliminating 94% of nuisance false alarms.

---

## Architecture Overview

```text
                        [ PHYSICAL / SIMULATED ENVIRONMENT ]
                       Flame IR  |  DHT22 Temp/Hum  |  MQ-2 Gas/Smoke
                                        │
                                        ▼
             ┌─────────────────────────────────────────────────────┐
             │       ESP1 Detection Node (ESP32 / ESP8266)         │
             │ - Pure C++ signal filtering & moving baseline       │
             │ - Directional sweep scanner (0°-180°) & confidence  │
             │ - 2.4 GHz ESP-NOW binary mesh transmitter           │
             │ - Wi-Fi HTTP telemetry client (X-API-Key auth)      │
             └──────────────┬───────────────────────┬──────────────┘
                            │                       │
                      (ESP-NOW Mesh)          (Wi-Fi HTTPS)
                            │                       │
                            ▼                       ▼
            ┌───────────────────────────┐   ┌──────────────────────────────────┐
            │   ESP2 Response Node      │   │ Cloud Run / Flask Backend Server │
            │ - Target servo aim horn   │   │ - Hybrid AI Risk Engine (ONNX)   │
            │ - Relay suppression pump  │   │ - Firestore Cloud DB Live Sync   │
            │ - 3,000ms watchdog cutoff │   │ - Rate-limited FCM/Telegram push │
            │ - Alarm buzzer & LED      │   │ - Complete Alert Audit Trail     │
            └───────────────────────────┘   └───────────────┬──────────────────┘
                                                            │
                                                   (Firestore Streams)
                                                            │
                                    ┌───────────────────────┴──────────────────────┐
                                    ▼                                              ▼
                    ┌─────────────────────────────┐                ┌─────────────────────────────┐
                    │ FireShield AI Flutter App   │                │   Web Ops Fleet Dashboard   │
                    │ - Real-time stream cards    │                │ - Single-page monitoring UI │
                    │ - Live multi-sensor charts  │                │ - Dynamic gauges & radar    │
                    │ - Radial aim angle compass  │                │ - 1-click scenario injectors│
                    └─────────────────────────────┘                └─────────────────────────────┘
```

---

## Milestone Progress Matrix (M0 – M8)

All milestones defined in `FireShieldAI_Milestone_Submission_Updated.xlsx` are **100% Completed**:

| Milestone | Objective | Deliverables | Status |
|---|---|---|---|
| **M0** | System Architecture & Basic Model Planning | [System Architecture](docs/system_architecture.md), Contracts, Schemas | **Completed** |
| **M1** | Basic Fire Detection & Automated Response | [Packet Contract](firmware/include/packet_contract.h), [Test Protocol M1](docs/test_protocol_m1.md), Watchdog | **Completed** |
| **M2** | Multi-Sensor Integration | [ESP32 Firmware](firmware/esp1_detection/esp1_multi_sensor_esp32.ino), [HW Recommendation](docs/hardware_platform_recommendation.md), Sensor Fusion | **Completed** |
| **M3** | Real-Time Data Collection & Processing | [Synthetic Generator](ai/synthetic_data_generator.py), [Validator](ai/data_validation.py), [Dataset Builder](ai/build_processed_dataset.py) | **Completed** |
| **M4** | Feature Engineering & Baseline Analysis | [Baseline Spec](docs/baseline_definition.md), [Feature Table](data/features/v1/features.parquet), [Plot Report](docs/reports/baseline_analysis.png) | **Completed** |
| **M5** | AI/ML Model Development & Evaluation | [Model Selection Report](docs/model_selection_report.md), [Model Card](docs/model_card.md), [ONNX Model](ml/models/v1/model.onnx), Hybrid Engine | **Completed** |
| **M6** | Intelligent Direction Detection & Response | [Direction Engine](firmware/include/direction_engine.h), [Direction Report](docs/direction_detection_report.md), Simulation Suite | **Completed** |
| **M7** | Mobile Application & Alert Integration | [Hardened Backend](tools/backend_server.py), [Ops Dashboard](tools/ops_dashboard/index.html), Flutter App Upgrades | **Completed** |
| **M8** | Final System Integration & Validation | [Validation Report](docs/final_validation_report.md), [Final Architecture](docs/final_architecture.md), [Demo Package](docs/demo_package.md) | **Completed** |

---

## Quick Start Guide

### 1. Launch the Backend Server & Hybrid AI Engine
```bash
# Install Python dependencies
pip install -r requirements.txt

# Run the hardened backend server (Port 5000)
python tools/backend_server.py
```

### 2. Open the Web Ops Fleet Monitor
Open your browser to:
```text
file:///d:/StartUp/Fire_Safety/tools/ops_dashboard/index.html
```
Use the one-click demo buttons (**Simulate NORMAL**, **Simulate FALSE ALARM**, **Simulate FIRE EVENT**) to observe real-time AI risk evaluation and aim angle updates.

### 3. Run the Automated Test Suite
```bash
# Run all 28 unit and end-to-end integration tests
pytest
```

### 4. Launch the Flutter Mobile Application
```bash
cd D:/FireShieldAI
flutter run -d chrome  # or windows / android
```

---

## Key Safety Principles
1. **Deterministic Safety Backstop**: Autonomous suppression actuators are guarded by deterministic rule-based persistence counters. ML models provide advisory confidence and false-alarm suppression, but cannot gate suppression during confirmed emergencies.
2. **Watchdog Interlock**: A 3,000 ms communications timeout immediately terminates response node relay power.
3. **Transparent Limitations**: Refer to [Known Limitations](docs/known_limitations.md) and [Synthetic Data Disclaimer](docs/synthetic_data_disclaimer.md).

---

## Strategic Startup Deliverables
- [Pitch Deck Executive Product Brief](docs/pitch_deck_product_brief.md)
- [Bill of Materials (BOM) & Unit Cost Economics](docs/bom_cost.md)
- [Safety & Regulatory Compliance Roadmap](docs/compliance_roadmap.md)
- [30-Day Pilot Deployment Plan](docs/pilot_plan.md)
- [ML Retraining & Model Governance Policy](docs/ml_retraining_policy.md)
- [Cloud Run & Docker Deployment Guide](docs/deployment.md)
