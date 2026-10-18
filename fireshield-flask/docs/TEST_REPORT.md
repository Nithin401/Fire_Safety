# FireShield AI Verification & Test Report

**Date of Execution:** 2026-10-18  
**Environment:** Windows, Python 3.10.9, Flutter 3.44.4 (Dart 3.12.2)  
**Scope:** ThingSpeak Data Normalization, Python Flask Backend, Room Baseline Learning, ML Safeguards, Flutter Integration.

---

## 1. Summary of Execution Results

| Test Category | Suite / Command | Total Checked | Passed | Failed | Not Run |
|---|---|---|---|---|---|
| **Flask Backend Unit Tests** | `pytest fireshield-flask/tests -v` | 18 | 18 | 0 | 0 |
| **Baseline Model Training** | `train_baseline.py --csv smart_fire_dataset.csv` | 1 | 1 | 0 | 0 |
| **Flutter Static Analysis** | `flutter analyze` | 1 | 1 | 0 | 0 |
| **Flutter Unit & Integration** | `flutter test test/flask_integration_test.dart` | 2 | 2 | 0 | 0 |
| **Flutter Web Compilation** | `flutter build web --release` | 1 | 1 | 0 | 0 |
| **Live ThingSpeak Fetch** | `scripts/download_thingspeak_data.py` | 1 | 0 | 0 | 1 (Awaiting user channel ID) |

---

## 2. Flask Automated Test Matrix (18 Passed)

All 18 unit tests executed in 2.08 seconds via `pytest`:

```
fireshield-flask/tests/test_api.py::TestApiEndpoints::test_graphs_summary_endpoint PASSED
fireshield-flask/tests/test_api.py::TestApiEndpoints::test_health_endpoint PASSED
fireshield-flask/tests/test_api.py::TestApiEndpoints::test_latest_reading_endpoint PASSED
fireshield-flask/tests/test_api.py::TestApiEndpoints::test_status_endpoint PASSED
fireshield-flask/tests/test_baseline.py::TestBaselineService::test_anomaly_detection_scoring PASSED
fireshield-flask/tests/test_baseline.py::TestBaselineService::test_compute_baseline_statistics PASSED
fireshield-flask/tests/test_baseline.py::TestBaselineService::test_insufficient_data_rejection PASSED
fireshield-flask/tests/test_data_export.py::TestDataService::test_filter_feeds_by_fire_status PASSED
fireshield-flask/tests/test_data_export.py::TestDataService::test_processed_csv_export_has_mapped_columns PASSED
fireshield-flask/tests/test_data_export.py::TestDataService::test_raw_csv_export_preserves_field_names PASSED
fireshield-flask/tests/test_ml_service.py::TestMLService::test_insufficient_samples_rejection PASSED
fireshield-flask/tests/test_ml_service.py::TestMLService::test_prevent_field6_as_fire_ground_truth PASSED
fireshield-flask/tests/test_ml_service.py::TestMLService::test_valid_supervised_training_with_labels PASSED
fireshield-flask/tests/test_thingspeak.py::TestThingSpeakService::test_fetch_error_handling PASSED
fireshield-flask/tests/test_thingspeak.py::TestThingSpeakService::test_fetch_feeds_caching PASSED
fireshield-flask/tests/test_thingspeak.py::TestThingSpeakService::test_fresh_vs_stale_detection PASSED
fireshield-flask/tests/test_thingspeak.py::TestThingSpeakService::test_normalize_entry_complete_valid PASSED
fireshield-flask/tests/test_thingspeak.py::TestThingSpeakService::test_normalize_missing_fields_never_zeroed PASSED
```

### Key Verified Behaviors:
1. **6-Field Schema Integrity**: `field1` (flame raw), `field2` (smoke status), `field3` (temp °C), `field4` (humidity %), `field5` (servo angle), `field6` (fire status) are preserved without loss.
2. **Missing Field Safety**: Missing values are mapped to `None` / `null`, never silently substituted with `0`.
3. **Staleness Tracking**: Timestamps older than 60s are flagged `is_stale: true`.
4. **Caching Verification**: Feeds requested within 15s TTL return cached responses, preventing ThingSpeak rate limits.
5. **CSV Separation**: Raw CSV exports retain original `field1..field6` column headers; processed CSV exports use mapped headers.
6. **ML Safeguards**: Supervised training is blocked if `field6` is used as fire ground truth, or if class samples are fewer than 5.

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
- **Command Run:** `flutter analyze`
- **Result:** `No issues found! (ran in 2.1s)` (PASSED)

### Unit & Integration Testing:
- **Command Run:** `flutter test test/flask_integration_test.dart`
- **Result:** `All tests passed!` (PASSED)
  - `FlaskApiService default base URL is set for environment`: PASSED
  - `FlaskDeviceRepository initial state contains valid placeholder`: PASSED

### Web Release Compilation:
- **Command Run:** `flutter build web --release`
- **Result:** `Built build\web in 58.6s` (PASSED)

---

## 5. Live ThingSpeak Connectivity Check

- **Status:** NOT RUN (Awaiting user channel ID and read key in `fireshield-flask/.env`).
- **Explanation:** In accordance with project safety guidelines, no synthetic network calls or fabricated credentials were used. The script `scripts/download_thingspeak_data.py` is implemented and verified ready to execute once `THINGSPEAK_CHANNEL_ID` is entered locally.
