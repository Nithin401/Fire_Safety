# Comprehensive Audit Report: FireShield AI & Hardware System

**Date of Audit:** September 9, 2026  
**Audited Location:** `D:\FireShieldAI` (Flutter App) & `d:\StartUp\Fire_Safety` (Firmware, AI Layer & Hardware Docs)  
**Audit Methodology:** Line-by-line inspection of source code, data contracts, repository implementations, UI widgets, and hardware scripts. No assumptions made from documentation or UI labels.

---

## 1. Complete Project Audit Table

| Feature / Subsystem | Status | Evidence in Code | What is Missing |
| :--- | :--- | :--- | :--- |
| **Frontend Framework** | **IMPLEMENTED** | `pubspec.yaml`, `lib/main.dart` (Flutter 3.x, Material 3, Riverpod 3.3.2, GoRouter 17.3.0). | Fully functional UI framework. |
| **Backend Framework** | **NOT IMPLEMENTED** | `hardware/cloud_function_simulator.py` (standalone Python script). No active Express/FastAPI/Node server in workspace. | Operational REST / MQTT backend service. |
| **Database Integration** | **PLACEHOLDER** | `data/repositories/firestore_device_repository.dart` has all Firestore calls commented out (`// return _firestore...`). | Live Firestore or PostgreSQL instance & connection logic. |
| **Authentication** | **UI ONLY / PLACEHOLDER** | `LoginScreen` calls `context.go('/')` directly on click. `MockAuthRepository` returns fake ID `'mock_user_123'`. | Firebase Auth / JWT validation, token storage, auth state guards. |
| **Push Notifications** | **UI ONLY / PLACEHOLDER** | `PushNotificationService` shows local `AlertDialog`. `mockNotificationsProvider` holds 3 static notifications. FCM code commented out in Dart. | Real FCM token registration, background message listeners, server-side trigger. |
| **Hardware Communication** | **NOT IMPLEMENTED** | `MockHardwareProtocolRepository` returns simulated `Future.delayed` maps. Zero HTTP/MQTT/Serial/BLE listeners in Flutter code. | Wi-Fi/MQTT/HTTP client inside Flutter app to receive ESP1 data. |
| **Telemetry Data Engine** | **MOCK / HARDCODED** | `MockDeviceRepository` holds 3 static devices ('Kitchen Smoke Detector', 'Server Room Monitor', 'Lobby Fire Alarm'). | Real-time stream parsing & state synchronization. |
| **Interactive Charts** | **UI ONLY** | `DeviceDetailsScreen` uses `fl_chart` with hardcoded `FlSpot` arrays (`FlSpot(0, 21.0)...`). | Dynamic data binding to actual time-series readings. |
| **Live Map Tracking** | **PARTIALLY IMPLEMENTED**| `MapScreen` renders Google Maps widget with device GPS coordinates & hardcoded emergency markers. | Dynamic live position updates from hardware. |
| **Report Generation** | **UI ONLY / PLACEHOLDER** | `MockReportRepository` uses `Random()` for stats; `exportReportAsPdf` has empty `Future.delayed`. | Actual PDF/CSV rendering engines and cloud download links. |
| **ESP1 Physical Datalogger** | **IMPLEMENTED** | `firmware/esp1_detection/esp1_detection.ino` reads A0 analog flame signal and streams machine-readable CSV over Serial. | Wi-Fi payload transmitter. |
| **ESP1 $\rightarrow$ ESP2 Response** | **IMPLEMENTED** | `firmware/esp2_response/ESP2_Advanced.ino` receives ESP-NOW packets, aims servo, triggers relay/buzzer/LED. | Status feedback link back to server/app. |
| **AI / Risk Engine (Local)** | **IMPLEMENTED** | `ai/risk_engine.py`, `anomaly_detection.py` perform rolling variance, z-score, rate of change, & state classification on CSVs. | Integration into app/backend for live inference. |

---

## 2. Screen-by-Screen Functional Audit

### 1. Login Screen (`/login`)
- **Can it open?** Yes (Initial route).
- **Data loading:** Static layout.
- **Form submission & Buttons:** Clicking **"Sign In"** executes `context.go('/')` immediately. Input text fields are ignored.
- **Errors & Persistence:** No validation, no error handling, no persistent auth session.

### 2. Signup Screen (`/signup`)
- **Can it open?** Yes.
- **Form submission:** Clicking **"Sign Up"** executes `context.go('/')`. Inputs are unparsed.

### 3. Forgot Password Screen (`/forgot-password`)
- **Can it open?** Yes.
- **Form submission:** Displays a SnackBar (`"Reset link sent!"`). No API call made.

### 4. Dashboard Screen (`/`)
- **Can it open?** Yes.
- **Data source:** Reads `devicesStreamProvider` (backed by `MockDeviceRepository`).
- **Data status:** Displays 3 mock devices. System Alert banner is triggered purely by checking `offlineCount > 0`.
- **Buttons:** Sync button triggers a SnackBar (`"Syncing hardware via MQTT/BLE..."`); notification and profile icons navigate correctly.

### 5. Device List Screen (`/devices`)
- **Can it open?** Yes.
- **Navigation:** Tapping a tile opens `/devices/:id`. Floating Action Button (+) opens `/devices/add`.

### 6. Add Device Screen (`/devices/add`)
- **Can it open?** Yes.
- **Form submission:** Text inputs do not have controllers attached. Clicking **"Add Device"** shows a SnackBar and pops the screen (`context.pop()`). **No device is added to RAM or database.** Data is discarded.

### 7. Device Details Screen (`/devices/:id`)
- **Can it open?** Yes.
- **Data status:** Displays mock metadata (`firmwareVersion`, `batteryLevel`, `wifiSignalStrength`). Temperature and CO line charts render hardcoded static coordinates.
- **Buttons:** Edit and Delete icons contain empty `// TODO:` stubs.

### 8. Live Map Screen (`/map`)
- **Can it open?** Yes.
- **Data status:** Requests location via `geolocator` and centers map. Plots device markers (green for online, red for offline) plus 3 hardcoded markers for Fire Station, Police Station, and Hospital.

### 9. Safety Reports Screen (`/reports`)
- **Can it open?** Yes.
- **Data status:** Period filter chips ('Daily', 'Weekly', 'Monthly', 'Yearly') trigger `MockReportRepository.getReportForPeriod()` which returns numbers generated via `Random()`.
- **Buttons:** **"Export PDF"** and **"Export CSV"** trigger SnackBars and complete an empty `Future.delayed`. No files are created.

### 10. Notifications Screen (`/notifications`)
- **Can it open?** Yes.
- **Data status:** Displays 3 hardcoded notifications from `MockNotifications` provider.
- **Buttons:** **"Mark All Read"** updates Riverpod in-memory state. Refreshing/restarting app resets notifications to default hardcoded list.

### 11. Settings & Profile Screens (`/settings`, `/settings/profile`)
- **Can it open?** Yes.
- **Toggles:** Dark Mode and Push Notification switches update local widget state, but contain `// TODO:` comments with no global effect.
- **Profile inputs:** Pre-filled with `"John Doe"`. Clicking **"Save Changes"** shows SnackBar without persisting.

---

## 3. Hardware Connection & Ingestion

1. **Can ESP1 currently send data to the app?**  
   **NO.** ESP1 firmware (`esp1_detection.ino`) outputs CSV via USB Serial. The Flutter app has no Serial listener, no HTTP server, no MQTT subscriber, and no active Firebase listener.
2. **Where does ESP1 data go?**  
   It prints to the serial terminal or goes into CSV files created by `tools/flame_data_logger.py`.
3. **Is it stored?**  
   Stored on the local PC disk via Python logger scripts, but **NOT** in any app database.
4. **Can the app display it?**  
   **NO.**
5. **Is the displayed value real sensor data or mock data?**  
   **100% MOCK DATA.**

---

## 4. End-to-End Fire Alert Workflow Tracing

```text
Flame Sensor ──► ESP1 Analog ──► ESP1 Decision ──► ESP-NOW ──► ESP2 Servo/Relay
  (WORKING)        (WORKING)       (WORKING)      (WORKING)      (WORKING)
                                       │
                                       ▼ (DISCONNECTED / NOT IMPLEMENTED)
                                Network / Backend
                                       │
                                       ▼ (DISCONNECTED / NOT IMPLEMENTED)
                                Flutter Application
                                       │
                                       ▼ (SIMULATED UI ONLY)
                                User Mobile Alert
```

- **Working:** Hardware detection, local threshold decision, ESP-NOW broadcast, and physical response on ESP2.
- **Disconnected:** Hardware-to-Cloud link, Cloud-to-App link, Real Mobile Notifications.

---

## 5. Location, Room & Direction Tracking

- **Room:** Displayed in app as static mock text (`"Kitchen"`, `"Server Room"`).
- **Sensor ID:** Displayed as static mock text (`"dev_001"`).
- **Fire Angle / Servo Angle:** **NOT IMPLEMENTED IN APP.** (Field missing from `DeviceModel`).
- **Fire Location / Direction:** **NOT IMPLEMENTED IN APP.**
- **Required Additions:**
  1. Add `flameRaw`, `fireAngle`, `isFlameDetected`, and `directionDegrees` to `DeviceModel`.
  2. Implement backend telemetry endpoint to ingest ESP1 angle payload.
  3. Build directional UI indicator widget in `DeviceDetailsScreen`.

---

## 6. ESP2 Response Status

- **App Awareness of ESP2:** **NONE.**
- **Existing States in App:** None (`DeviceModel` only tracks `isOnline`, `batteryLevel`, `wifiSignal`).
- **Missing Protocol States:** `IDLE`, `AIMING`, `RESPONSE_ACTIVE`, `PUMP_ON`, `FIRE_CLEARED`, `TIMEOUT_FAULT`.
- **Required Additions:** Expand API schema to include `responseStatus` enum and payload fields sent from ESP2 or relayed by ESP1.

---

## 7. Sensor Dashboard Value Breakdown

| Dashboard Metric | Implementation Type | Current Value Origin |
| :--- | :--- | :--- |
| **Temperature** | **HARDCODED / MOCK** | `25.0°C` in `DeviceModel`; random numbers in charts. |
| **Humidity** | **HARDCODED / MOCK** | `50.0%` in `DeviceModel`. |
| **Gas / Smoke (CO)** | **HARDCODED / MOCK** | Static `FlSpot(0, 0.5)` to `FlSpot(10, 1.1)` ppm. |
| **Flame Presence** | **NOT AVAILABLE** | Not in schema or UI. |
| **Flame Raw Value** | **NOT AVAILABLE** | Not in schema or UI. |
| **Fire Status** | **CALCULATED (MOCK)**| Computed from `offlineCount > 0`. |
| **Risk Level / Score** | **NOT AVAILABLE** | Not displayed in app. |
| **Sensor Timestamp** | **MOCK** | `DateTime.now().subtract(...)`. |
| **Device ID** | **HARDCODED MOCK** | `"dev_001"`, `"dev_002"`, `"dev_003"`. |
| **Room ID** | **HARDCODED MOCK** | `"Kitchen"`, `"Server Room"`, `"Lobby"`. |
| **Servo / Fire Angle** | **NOT AVAILABLE** | Not in schema or UI. |

---

## 8. Fire-Risk Engine Audit

- **App-side Analysis:** **NONE.** The app does zero calculation.
- **Backend-side Analysis:** `hardware/cloud_function_simulator.py` contains basic threshold logic (`ir > ambient + 10.0`).
- **Python AI Engine (`Fire_Safety/ai`):** Contains statistical baseline estimation, Z-Score, Isolation Forest, and a multi-factor risk engine (`risk_engine.py`).
- **AI/ML Claim Verification:** **No AI/ML model is running in the Flutter application.** The current UI uses static mock banners.

---

## 9. Database Audit

- **Active Database:** **NONE.**
- **Code Status:** `FirestoreDeviceRepository.dart` contains commented-out methods (`// return _firestore...`).
- **Persistence:** All data lives strictly in RAM within Riverpod providers (`MockDeviceRepository`, `MockNotifications`). **Restarting the app wipes all user changes.**

---

## 10. Notifications Audit

- **Status:** **SIMULATED UI ONLY.**
- **Implementation:** `PushNotificationService.simulateIncomingFireAlert()` renders a Flutter `AlertDialog`.
- **FCM Integration:** Package imported in `pubspec.yaml`, but initialization is commented out in `main.dart`.
- **Notification List:** Static array in `notification_providers.dart`.

---

## 11. Security Audit

> [!CAUTION]
> **Exposed Credentials Discovered in Firmware Backup:**
> - `firmware/esp1_detection/original_esp1.ino` contains plaintext credentials:
>   - Telegram Bot Token: `8960471860:AAGpkwj1...`
>   - Telegram Chat ID: `6202108591`
>   - Wi-Fi SSID & Password: `"rpm"` / `"12345678"`

### Recommended Security Remediation:
1. Revoke and regenerate the Telegram Bot token immediately.
2. Remove hardcoded Wi-Fi SSIDs/Passwords and Bot Tokens from C++ source code. Use a secure `secrets.h` file added to `.gitignore`, or inject them via environment variables at compile time.
3. Remove bypasses in `LoginScreen` and enforce real authentication token verification.

---

## 12. System Reliability & Fault Tolerance

- **ESP1 / ESP2 Disconnect:** App does not detect offline status dynamically. It displays a static `isOnline: false` flag for one mock device.
- **Wi-Fi / Internet Loss:** App has no offline caching (Hive / Shared Preferences are in `pubspec.yaml` but unused).
- **Corrupted Packets:** No validation logic exists in the Flutter presentation layer.

---

## 13. Current MVP Assessment

| Workflow | Status | Reason |
| :--- | :--- | :--- |
| **WORKFLOW 1:** Sensors $\rightarrow$ ESP1 $\rightarrow$ Readings $\rightarrow$ App | **NOT WORKING** | ESP1 streams to Serial/ESP-NOW; App displays mock RAM data. |
| **WORKFLOW 2:** Sensor Data $\rightarrow$ Risk Decision $\rightarrow$ Mobile Alert | **PARTIALLY WORKING** | Local physical detection works; Mobile alert in app is a simulated UI dialog. |
| **WORKFLOW 3:** Fire Detection $\rightarrow$ Direction $\rightarrow$ ESP2 Response $\rightarrow$ App Status | **PARTIALLY WORKING** | Physical ESP1 $\rightarrow$ ESP2 aiming & pump trigger works; App has zero awareness of direction or ESP2. |

---

## 14. Summary of Capabilities Today

### CURRENTLY WORKING
1. **Physical ESP1 Hardware Datalogger:** Reads A0 analog flame values and outputs machine-readable CSV via Serial (`esp1_detection.ino`).
2. **Python Data Collection & AI Engine:** `flame_data_logger.py` logs sessions; `ai/analyze_dataset.py` extracts features, calculates dynamic baseline, detects z-score anomalies, and computes risk scores (0-100).
3. **Physical ESP1 $\rightarrow$ ESP2 Response Node:** ESP-NOW communication, servo aiming, relay actuation, buzzer/LED activation (`ESP2_Advanced.ino`).
4. **Flutter UI Shell:** Responsive Material 3 design, Riverpod state management, GoRouter navigation, Map visualization layout, Chart components.

### PARTIALLY IMPLEMENTED
1. **Reports Screen:** UI chips switch mock states; PDF/CSV export buttons show SnackBars without generating files.
2. **Add Device Screen:** UI form exists; submit button pops screen without saving data to RAM or DB.
3. **Map Screen:** Renders Google Map with real location centering and mock markers.

### NOT YET IMPLEMENTED
1. Wi-Fi / MQTT telemetry transmitter on ESP1.
2. Live Backend API server / MQTT Broker.
3. Cloud Database persistence (Firestore / PostgreSQL).
4. Real Firebase Authentication & Auth Guards.
5. Real FCM Push Notification dispatch.
6. Schema support for `flameRaw`, `fireAngle`, and `responseStatus` in Flutter app.

---

## 15. Prioritized Development Roadmap

### Priority 1: Hardware-to-Cloud Telemetry Bridge
- **Task:** Update ESP1 firmware to send HTTP POST or MQTT JSON payload over Wi-Fi when connected.
- **Fields:** `deviceId`, `timestamp`, `flameRaw`, `fireAngle`, `isFire`.
- **Files:** `firmware/esp1_detection/esp1_detection.ino`.

### Priority 2: Ingestion API & Database Integration
- **Task:** Build lightweight Node.js/Express or Python/FastAPI ingestion endpoint; write incoming payload to Firestore/PostgreSQL.
- **Files:** `hardware/` or `backend/` server scripts; uncomment `FirestoreDeviceRepository.dart`.

### Priority 3: Data Schema & App Binding
- **Task:** Add `flameRaw`, `fireAngle`, `riskScore`, and `responseStatus` to `DeviceModel`. Swap `MockDeviceRepository` for `FirestoreDeviceRepository` in `repository_providers.dart`.
- **Files:** `lib/domain/models/device_model.dart`, `lib/presentation/providers/repository_providers.dart`.

### Priority 4: Real FCM Push Notifications
- **Task:** Initialize `FirebaseMessaging` in `main.dart`; attach device FCM tokens in backend; trigger alerts when risk score > threshold.
- **Files:** `lib/core/services/push_notification_service.dart`, `lib/main.dart`.

### Priority 5: End-to-End AI Edge/Cloud Inference
- **Task:** Deploy `ai/risk_engine.py` logic to cloud backend or compile to C++ for ESP1 edge inference.

---

## 16. Final Architecture Gap Analysis

```text
CURRENT ARCHITECTURE TODAY:
[ Physical ESP1 Sensor ] ──(Serial CSV)──► [ Python Data Logger & AI Scripts ]
[ Physical ESP1 Sensor ] ──(ESP-NOW)─────► [ Physical ESP2 Servo/Relay Response ]
[ Standalone Flutter App ] ──────────────► [ Hardcoded Mock RAM Data (No Hardware Link) ]

                                  ↓

MISSING BRIDGES:
1. ESP1 Wi-Fi Telemetry Transmitter (HTTP / MQTT)
2. Live Ingestion API Server & Database (PostgreSQL / Firestore)
3. Real FCM Push Notification Trigger
4. Flutter Data Layer Connection to Database Stream
5. Expanded Schema (Flame Raw, Angle, ESP2 Status)

                                  ↓

TARGET MVP ARCHITECTURE:
[ ESP1 Detection Node ] ───► [ Local Wi-Fi / MQTT ] ───► [ Ingestion API + Risk Engine ]
         │                                                            │
     (ESP-NOW)                                                (Firestore / FCM)
         │                                                            │
         ▼                                                            ▼
[ ESP2 Response Node ]                                   [ Flutter App Live Dashboard ]
 (Servo/Relay/Buzzer)                                    (Real-time Data & Alerts)

                                  ↓

FUTURE COMMERCIAL PRODUCT:
Multi-room Sensor Mesh (Temp + Gas + Flame) ──► Edge ML Classifier ──► FireShield AI Cloud ──► Automated Dispatch
```
