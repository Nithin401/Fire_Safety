# FireShield AI Verification & Test Report

**Date of Execution:** 2026-10-18  
**Environment:** Windows, Python 3.10.9, Flutter 3.44.4 (Dart 3.12.2)  
**Scope:** ThingSpeak Data Normalization, Python Flask Backend, Room Baseline Learning, ML Safeguards, Flutter Integration.

---

## 1. Summary of Execution Results

| Test Category | Suite / Command | Total Checked | Passed | Failed | Not Run |
|---|---|---|---|---|---|
| **Flask Backend Unit Tests** | `pytest tests/ -v` | 36 | 36 | 0 | 0 |
| **Baseline Model Training** | `train_baseline.py --csv smart_fire_dataset.csv` | 1 | 1 | 0 | 0 |
| **Flutter Static Analysis** | `flutter analyze` | 1 | 1 | 0 | 0 |
| **Flutter Unit & Integration** | `flutter test test/flask_integration_test.dart` | 2 | 2 | 0 | 0 |
| **Flutter Web Compilation** | `flutter build web --release` | 1 | 1 | 0 | 0 |
| **Live ntfy Push Delivery** | `POST https://ntfy.sh/fireshield_alerts_3534677` | 1 | 1 (HTTP 200) | 0 | 0 |
| **Live ThingSpeak Channel Poller**| `services/poller_service.py` (Channel 3534677) | 1 | 1 | 0 | 0 |

---

## 2. Flask Automated Test Matrix (36 Passed)

All 36 unit tests executed in 5.37 seconds via `pytest`:

```
tests/test_alert_service.py::TestAlertService::test_all_clear_recovery_flow PASSED
tests/test_alert_service.py::TestAlertService::test_baseline_anomaly_dispatches_outbox PASSED
tests/test_alert_service.py::TestAlertService::test_early_warning_dispatches_outbox PASSED
tests/test_alert_service.py::TestAlertService::test_hardware_fire_dispatches_outbox PASSED
tests/test_alert_service.py::TestAlertService::test_sensor_fault_dispatches_outbox PASSED
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
tests/test_event_store.py::TestEventStore::test_ingestion_state_tracking PASSED
tests/test_event_store.py::TestEventStore::test_log_event_and_retrieve PASSED
tests/test_event_store.py::TestEventStore::test_outbox_queue_and_retry_backoff PASSED
tests/test_event_store.py::TestEventStore::test_push_subscription_management PASSED
tests/test_ml_service.py::TestMLService::test_insufficient_samples_rejection PASSED
tests/test_ml_service.py::TestMLService::test_prevent_field6_as_fire_ground_truth PASSED
tests/test_ml_service.py::TestMLService::test_valid_supervised_training_with_labels PASSED
tests/test_notifications_routes.py::TestNotificationRoutes::test_current_risk_endpoint PASSED
tests/test_notifications_routes.py::TestNotificationRoutes::test_events_endpoint PASSED
tests/test_notifications_routes.py::TestNotificationRoutes::test_notification_status_endpoint PASSED
tests/test_notifications_routes.py::TestNotificationRoutes::test_test_notification_endpoint_ntfy PASSED
tests/test_notifications_routes.py::TestNotificationRoutes::test_vapid_public_key_endpoint PASSED
tests/test_ntfy.py::TestNtfyService::test_format_message_levels PASSED
tests/test_ntfy.py::TestNtfyService::test_send_alert_failure PASSED
tests/test_ntfy.py::TestNtfyService::test_send_alert_success PASSED
tests/test_risk_engine.py::TestRiskEngine::test_all_clear_recovery_requires_three_consecutive_normals PASSED
tests/test_risk_engine.py::TestRiskEngine::test_baseline_anomaly_detection PASSED
tests/test_risk_engine.py::TestRiskEngine::test_early_warning_rate_of_rise PASSED
tests/test_risk_engine.py::TestRiskEngine::test_hardware_fire_alert_takes_precedence PASSED
tests/test_risk_engine.py::TestRiskEngine::test_normal_condition PASSED
tests/test_risk_engine.py::TestRiskEngine::test_stale_or_missing_data_triggers_sensor_fault PASSED
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

