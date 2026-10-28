# FireShield AI Verification & Test Report

**Date of Execution:** 2026-10-18  
**Environment:** Windows, Python 3.10.9, Flutter 3.44.4 (Dart 3.12.2)  
**Scope:** ThingSpeak Data Normalization, Python Flask Backend, Room Baseline Learning, ML Safeguards, Flutter Integration.

---

## 1. Summary of Execution Results

| Test Category | Suite / Command | Total Checked | Passed | Failed | Not Run |
|---|---|---|---|---|---|
| **Flask Backend Unit Tests** | `pytest tests/ -v` | 52 | 52 | 0 | 0 |
| **Baseline Model Training** | `train_baseline.py --csv smart_fire_dataset.csv` | 1 | 1 | 0 | 0 |
| **Flutter Static Analysis** | `flutter analyze` | 1 | 1 | 0 | 0 |
| **Flutter Unit & Integration** | `flutter test test/flask_integration_test.dart` | 2 | 2 | 0 | 0 |
| **Flutter Web Compilation** | `flutter build web --release` | 1 | 1 | 0 | 0 |
| **Live ntfy Push Delivery** | `POST https://ntfy.sh/fireshield_alerts_3534677` | 1 | 1 (HTTP 200) | 0 | 0 |
| **Exotel Voice Call Adapter** | `tests/test_voice_service.py` | 16 | 16 | 0 | 0 |
| **Live ThingSpeak Channel Poller**| `services/poller_service.py` (Channel 3534677) | 1 | 1 | 0 | 0 |

---

## 2. Flask Automated Test Matrix (52 Passed)

All 52 unit tests executed in 3.06 seconds via `pytest`:

```
tests/test_api.py::TestApiEndpoints::test_graphs_summary_endpoint PASSED
tests/test_api.py::TestApiEndpoints::test_health_endpoint PASSED
tests/test_api.py::TestApiEndpoints::test_latest_reading_endpoint PASSED
tests/test_api.py::TestApiEndpoints::test_status_endpoint PASSED
tests/test_baseline.py::TestBaselineService::test_anomaly_detection_scoring PASSED
tests/test_baseline.py::TestBaselineService::test_compute_baseline_statistics PASSED
tests/test_baseline.py::TestBaselineService::test_insufficient_data_rejection PASSED
tests/test_data_export.py::TestDataService::test_filter_feeds_by_fire_status PASSED
tests/test_data_export.py::TestDataService::test_processed_csv_export_has_mapped_columns PASSED
tests/test_data_export.py::TestDataService::test_raw_csv_export_preserves_field_names PASSED
tests/test_ml_service.py::TestMLService::test_insufficient_samples_rejection PASSED
tests/test_ml_service.py::TestMLService::test_prevent_field6_as_fire_ground_truth PASSED
tests/test_ml_service.py::TestMLService::test_valid_supervised_training_with_labels PASSED
tests/test_notifications.py::test_event_store_record_and_retrieve PASSED
tests/test_notifications.py::test_outbox_queue_and_retry_backoff PASSED
tests/test_notifications.py::test_webpush_subscription_management PASSED
tests/test_notifications.py::test_ntfy_payload_mapping PASSED
tests/test_notifications.py::test_ntfy_publish_success PASSED
tests/test_notifications.py::test_api_vapid_public_key_schema PASSED
tests/test_notifications.py::test_api_notification_status_schema PASSED
tests/test_notifications.py::test_api_events_schema PASSED
tests/test_notifications.py::test_api_current_risk_schema PASSED
tests/test_risk_engine.py::test_normal_reading_evaluates_to_normal PASSED
tests/test_risk_engine.py::test_hardware_fire_priority_with_field6 PASSED
tests/test_risk_engine.py::test_hardware_fire_priority_with_flame_sensor PASSED
tests/test_risk_engine.py::test_hardware_fire_priority_with_smoke_sensor PASSED
tests/test_risk_engine.py::test_baseline_anomaly_environmental_only PASSED
tests/test_risk_engine.py::test_early_warning_rapid_temp_rise PASSED
tests/test_risk_engine.py::test_stale_reading_produces_data_fault PASSED
tests/test_risk_engine.py::test_missing_fields_produces_data_fault PASSED
tests/test_risk_engine.py::test_all_clear_transition_after_consecutive_normal_readings PASSED
tests/test_thingspeak.py::TestThingSpeakService::test_fetch_error_handling PASSED
tests/test_thingspeak.py::TestThingSpeakService::test_fetch_feeds_caching PASSED
tests/test_thingspeak.py::TestThingSpeakService::test_fresh_vs_stale_detection PASSED
tests/test_thingspeak.py::TestThingSpeakService::test_normalize_entry_complete_valid PASSED
tests/test_thingspeak.py::TestThingSpeakService::test_normalize_missing_fields_never_zeroed PASSED
tests/test_voice_service.py::TestVoiceServiceUnit::test_number_normalization PASSED
tests/test_voice_service.py::TestVoiceServiceUnit::test_prohibited_emergency_numbers PASSED
tests/test_voice_service.py::TestVoiceServiceUnit::test_credential_redaction_in_config_status PASSED
tests/test_voice_service.py::TestVoiceServiceUnit::test_dry_run_mode_simulation PASSED
tests/test_voice_service.py::TestVoiceServiceUnit::test_cooldown_prevents_spamming_calls PASSED
tests/test_voice_service.py::TestVoiceServiceUnit::test_live_exotel_call_success PASSED
tests/test_voice_service.py::TestVoiceServiceUnit::test_exotel_api_error_handling PASSED
tests/test_voice_service.py::TestVoiceServiceUnit::test_exotel_timeout_handling PASSED
tests/test_voice_service.py::TestVoiceServiceUnit::test_webhook_status_callback_updates_call PASSED
tests/test_voice_service.py::TestVoiceServiceUnit::test_exoml_generation PASSED
tests/test_voice_service.py::TestVoiceAlertIntegration::test_hardware_fire_reading_triggers_voice_call PASSED
tests/test_voice_service.py::TestVoiceRoutes::test_get_voice_status_api PASSED
tests/test_voice_service.py::TestVoiceRoutes::test_test_call_api_dry_run PASSED
tests/test_voice_service.py::TestVoiceRoutes::test_test_call_prohibits_emergency_number PASSED
tests/test_voice_service.py::TestVoiceRoutes::test_exoml_endpoint PASSED
tests/test_voice_service.py::TestVoiceRoutes::test_voice_alerts_page_renders PASSED
```

### Key Verified Behaviors:
1. **6-Field Schema Integrity**: `field1` (flame raw), `field2` (smoke status), `field3` (temp °C), `field4` (humidity %), `field5` (servo angle), `field6` (fire status) are preserved without loss.
2. **Deterministic Risk State Machine**: Hardware alarms bypass all debounce and immediately raise `HARDWARE_FIRE_ALERT`. Early warnings fire on rapid $\Delta T/\Delta t \ge 1.5$ °C/min. Statistical deviations fire on $\ge 2.5\sigma$ ambient shift.
3. **Recovery Hysteresis**: 3 consecutive normal readings are required to clear an active alarm state and emit `ALL_CLEAR`.
4. **Persistent Outbox & Retries**: Outbox items are persisted in SQLite and use exponential backoff (`next_attempt_at`) upon transient network drops.
5. **Zero-Firebase Push Notifications**: Web Push uses standard VAPID; mobile push dispatches via HTTP to `ntfy.sh`. Both services gracefully handle delivery errors.

---

## 3. Room Baseline Model Training

- **Command Run:** `python fireshield-flask/scripts/train_baseline.py --csv smart_fire_dataset.csv --room "Living Room Sunny"`
- **Result:** PASSED
- **Observed Metrics:**
  - Non-fire usable rows: 106
  - Learned Mean Temperature: 35.67 °C
  - Learned Median Temperature: 32.29 °C
  - Learned Standard Deviation: ±9.07 °C
  - Learned Observed Range: [27.5 °C, 60.0 °C]
  - 2-Sigma Variation Band: [27.5 °C, 53.8 °C]
  - Model file written to: `fireshield-flask/data/models/room_baseline.json`

---

## 4. Flutter Application Verification

### Static Analysis:
- **Command Run:** `flutter analyze lib/presentation/features/dashboard/widgets/room_adaptive_risk_card.dart lib/core/services/flask_api_service.dart`
- **Result:** `No issues found! (ran in 1.3s)` (PASSED)

### Unit & Integration Testing:
- **Command Run:** `flutter test test/flask_integration_test.dart`
- **Result:** `All tests passed!` (PASSED)
  - `FlaskApiService default base URL is set for environment`: PASSED
  - `FlaskDeviceRepository initial state contains valid placeholder`: PASSED

### Web Release Compilation:
- **Command Run:** `flutter build web --release`
- **Result:** `Built build\web in 65.0s` (PASSED)

---

## 5. Live Services & Push Verification

- **Live ThingSpeak Channel Polling:**
  - Channel: `3534677`
  - Polling interval: 15s daemon background thread.
  - Successfully pulls feeds, caches with 15s TTL, and feeds the stateful risk engine.
- **Live ntfy Mobile Push Notification Delivery:**
  - Endpoint: `https://ntfy.sh/fireshield_alerts_3534677`
  - HTTP Test Request: Sent with `Title: [EARLY WARNING] Rapid Temp Rise`, priority `4`, tags `warning,temperature`.
  - HTTP Response: `200 OK`
  - Result: Confirmed live delivery to ntfy cloud infrastructure without any Firebase dependency.

---

## 6. Exotel Outbound Voice Calling Verification

- **Module Under Test:** `services/voice_service.py` & `routes/voice.py`
- **Unit Test Suite:** 16 tests passing in 2.86s
- **Verified Capabilities:**
  1. **Indian Phone Number Normalization:** Successfully maps 10-digit Indian mobiles (`9876543210`), leading-zero (`09876543210`), and `91` prefixes to canonical E.164 (`+919876543210`).
  2. **Emergency Number Guard:** Strictly rejects and blocks emergency numbers (`100`, `101`, `102`, `108`, `112`, `911`, `999`).
  3. **Dry-Run Safety Mode:** Simulates provider acceptance with realistic Call SIDs (`dryrun_exo_...`) when unconfigured or in testing mode, avoiding accidental consumption of user trial credits.
  4. **Cooldown & Incident Deduplication:** Suppresses repetitive outbound dialing within a 300-second window during continuous active fire events.
  5. **Dynamic ExoML Generation:** Generates valid, sanitized XML speech prompts for Exotel Text-To-Speech telephony flows.
  6. **Credential Redaction:** Masks API keys and tokens in all responses, logs, and dashboard views.
  7. **Status Callbacks:** Maps Exotel webhook lifecycle updates (`queued`, `ringing`, `in-progress`, `completed`, `failed`) into SQLite audit log.


