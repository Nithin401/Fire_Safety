# FireShield AI — Engineering Changelog

All notable changes, milestone progressions, and implementation notes are documented in this file.

## [2026-09-16] — Project Kickoff & Security Hardening
- **Security**:
  - Validated zero exposed active credentials across repository.
  - Added `.gitignore` ignoring `.env`, `serviceAccountKey.json`, and build caches.
  - Created `.env.example` defining template configuration for backend, Firestore, and alert dispatchers.
- **Tracking**:
  - Integrated `FireShieldAI_Milestone_Submission_Updated.xlsx` into version control.
  - Initialized `docs/OPEN_QUESTIONS.md` for assumption logging.

## [2026-09-16] — Milestone M1: Basic Fire Detection & Automated Response
- **Firmware & Networking**:
  - Formalized unified binary packet contract in `firmware/include/packet_contract.h` with XOR checksums and angle validation.
  - Modularized pure C/C++ detection algorithms (`firmware/include/detection_logic.h`) and response watchdog failsafe (`firmware/include/response_logic.h`).
  - Implemented unit tests in `tests/test_firmware_logic.py` passing 100% on desktop without physical hardware dependency.
  - Authored physical verification protocol and interim Wokwi simulation guide in `docs/test_protocol_m1.md`.
  - Updated `FireShieldAI_Milestone_Submission_Updated.xlsx` status for M1 to **Completed**.

## [2026-09-16] — Milestone M2: Multi-Sensor Integration
- **Hardware Architecture & Documentation**:
  - Published `docs/hardware_platform_recommendation.md` evaluating ESP8266 ADC limitations and recommending ESP32 migration for multi-sensor nodes.
- **Firmware Multi-Sensor Extension**:
  - Authored `firmware/esp1_detection/esp1_multi_sensor_esp32.ino` integrating DHT22 (temp/humidity), MQ-2 (gas/smoke), and dual analog/digital flame sensing.
  - Updated ESP8266 firmware `firmware/esp1_detection/esp1_wifi_telemetry.ino` telemetry payload with multi-sensor schema.
- **Backend & Feature Fusion**:
  - Updated `tools/backend_server.py` to ingest, validate, and store multi-sensor fields in RAM and Firestore.
  - Extended `ai/features.py` with multi-channel rolling statistics, thermal/gas derivatives, and sensor-fusion consistency checks (`flame_temp_correlation`, `fusion_confidence_score`, `false_alarm_suspect`).
  - Added unit tests in `tests/test_features.py` passing 100%.
  - Updated `FireShieldAI_Milestone_Submission_Updated.xlsx` status for M2 to **Completed**.

## [2026-09-16] — Milestone M3: Real-Time Data Collection & Data Processing
- **Dataset Schema v2.0**:
  - Finalized official multi-sensor schema in `docs/dataset_schema.md` covering all 13 core and metadata fields.
- **Validation Engine**:
  - Implemented `ai/data_validation.py` with strict schema, range, monotonic timestamp, and categorical checks.
- **Processed Dataset Pipeline**:
  - Built `ai/build_processed_dataset.py` compiling raw inputs into versioned master datasets (`data/processed/v1/dataset.parquet` and `.csv`).
  - Created `docs/data_summary_template.md` and automated generation of `data/processed/v1/data_summary.md` (4,800 rows across 40 sessions, 0 schema violations).
  - Added unit tests in `tests/test_data_pipeline.py` passing 100%.
  - Updated `FireShieldAI_Milestone_Submission_Updated.xlsx` status for M3 to **Completed**.

## [2026-09-16] — Milestone M4: Feature Engineering & Baseline Analysis
- **Dynamic Baseline Specification**:
  - Published `docs/baseline_definition.md` formalizing rolling median ($W=50$), local standard deviation, Z-score thresholds, and time-since-last-anomaly.
- **Feature Generation Pipeline**:
  - Built `ai/build_features.py` processing session time-series with zero intra-session leakage to generate `data/features/v1/features.parquet` (4,800 rows x 48 engineered features).
- **Engineering Visualizations**:
  - Updated `ai/visualize.py` and exported multi-panel engineering report to `docs/reports/baseline_analysis.png`.
  - Added unit tests in `tests/test_feature_pipeline.py` passing 100%.
  - Updated `FireShieldAI_Milestone_Submission_Updated.xlsx` status for M4 to **Completed**.
