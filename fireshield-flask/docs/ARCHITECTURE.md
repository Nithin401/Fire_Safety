# FireShield AI Architecture & Integration Specification

## 1. System Overview

FireShield AI is a decoupled, reliable IoT and edge fire detection architecture pairing local hardware response with cloud telemetry, a Python Flask operational portal, and an existing cross-platform Flutter application.

**Firebase is completely excluded.** The system relies on:
1. **ESP8266 Hardware Node (ESP1)**: Reads analog/digital sensors and broadcasts via ESP-NOW to the ESP2 response node every 200ms. Uploads telemetry to ThingSpeak every 16,000ms.
2. **ThingSpeak IoT Channel**: Serves as the cloud time-series data source of truth.
3. **Python Flask Backend (`fireshield-flask`)**: Ingests, normalizes, caches, analyzes baselines, and exposes a clean, authenticated JSON API to clients.
4. **FireShield AI Flutter App**: Connects via HTTP to the Flask backend without exposing private cloud credentials.

```
                      +-----------------------------+
                      |   ESP8266 Detection Node   |
                      |  - Flame AO: A0             |
                      |  - Smoke DO: GPIO12         |
                      |  - DHT11:    GPIO4          |
                      |  - Servo:    GPIO14         |
                      +--------------+--------------+
                                     |
               +---------------------+---------------------+
               | ESP-NOW (200ms)                           | Wi-Fi HTTP (16s)
               v                                           v
+-----------------------------+             +-----------------------------+
|    ESP2 Response Node       |             |   ThingSpeak IoT Channel    |
| - Servo scanner aiming      |             | - Stores 6 canonical fields |
| - Water pump / relay        |             +--------------+--------------+
| - Alarm buzzer & LEDs       |                            |
+-----------------------------+                            | HTTPS Feed Poll (15s TTL)
                                                           v
                                            +-----------------------------+
                                            | Python Flask Backend Server |
                                            | - ThingSpeak API & Cache    |
                                            | - 6-Field Schema Normalizer |
                                            | - Room Baseline Learning    |
                                            | - JSON API (/api/*)         |
                                            | - Export & ML Studio UI     |
                                            +--------------+--------------+
                                                           |
                                                           | JSON REST API (/api/readings/latest)
                                                           v
                                            +-----------------------------+
                                            | FireShield AI Flutter App   |
                                            | (Web, Android, iOS, Windows)|
                                            | - Real-time zone status     |
                                            | - 6-field sensor dashboard  |
                                            | - Local & push dispatch     |
                                            +-----------------------------+
```

---

## 2. Sensor & ThingSpeak Contract

The system strictly adheres to the 6-field ThingSpeak mapping sent every 16 seconds by the ESP8266:

| Field | Label | Meaning | Normalization & Units |
|---|---|---|---|
| `field1` | FLAME | Analog flame sensor | `flame_raw` (Threshold < 600 indicates flame) |
| `field2` | SMOKEVALUE | Smoke detector digital state | `smoke_status` (1 = Smoke active, 0 = Clean) |
| `field3` | TEMPERATURE | DHT11 ambient temperature | `temperature_c` (&deg;C) |
| `field4` | HUMIDITY | DHT11 ambient relative humidity | `humidity_pct` (%) |
| `field5` | SERVO ANGLE | Directional scanner azimuth | `servo_angle` (0&deg; to 180&deg;) |
| `field6` | FIRE STATUS | Hardware rule triggered state | `fire_status` (1 = Triggered, 0 = Not triggered) |

### Non-Negotiable Contract Rules:
- **Never substitute zero for missing data**: If a sensor fails or is disconnected, the value is recorded as `null` / `None`, preserving signal truth.
- **Hardware alarm independence**: The hardware rule (`field6`) is deterministic (`flameDetected || smokeDetected`). Experimental ML models never override or suppress this hardware response.
- **Staleness boundary**: Readings older than 60 seconds are explicitly flagged as stale, preventing old values from appearing live.

---

## 3. Python Flask Architecture

Located in `fireshield-flask/`:
- **`app.py`**: Application factory with blueprint registration, error handlers, and restricted CORS.
- **`config.py`**: Environment configuration loader with fallback resolution (`.env` in flask folder, repo root, and `secrets/.env`).
- **`services/thingspeak_service.py`**:
  - Handles ThingSpeak feed requests with 10-second timeout.
  - In-memory caching with 15-second TTL to avoid rate-limit exhaustion.
  - Normalizes raw feeds into the 6-field dictionary with freshness metadata.
- **`services/data_service.py`**:
  - Converts feeds to pandas DataFrame.
  - Exports separate raw CSV (preserving `field1..field6`) and processed CSV (`flame_raw`, `temperature_c`, etc.).
  - Deduplicates records and handles offline CSV inspection.
- **`services/baseline_service.py`**:
  - Computes room-temperature statistical baseline: mean, median, standard deviation, percentiles (P05, P25, P75, P95), and 2-sigma bands.
  - Detects environmental anomalies without conflating temperature swings with confirmed fire.
- **`services/ml_service.py`**:
  - Evaluates dataset readiness.
  - Strictly forbids using `field6` alone as ground truth fire labels.
  - Enforces minimum class sample requirements before training supervised classifiers (Logistic Regression, Random Forest).
- **`services/risk_engine.py`**:
  - Implements stateful risk evaluation without suppressing hardware fire alarms.
  - Distinguishes `HARDWARE_FIRE_ALERT`, `EARLY_WARNING` (temperature rise rate >= 1.5°C/min), `BASELINE_ANOMALY` (deviation >= 2.5 sigma from learned baseline), `SENSOR_OR_DATA_FAULT` (stale > 60s or missing), and `NORMAL`.
  - Hysteresis: requires 3 consecutive normal readings to clear alert state.
- **`services/event_store.py`**:
  - SQLite persistent storage (`data/events.db`) for hazard event audit log, push subscriptions, and notification outbox with exponential retry backoff.
- **`services/webpush_service.py`**:
  - Standard Web Push using VAPID (via `pywebpush`). Key pair auto-generated in `data/vapid_keys.json`. Handles HTTP 410/404 subscription expiration.
- **`services/ntfy_service.py`**:
  - Zero-Firebase mobile push notifications published via HTTP to `https://ntfy.sh/<topic>`. Configured with priority, tags, and dashboard click actions.
- **`services/alert_service.py`**:
  - Coordinates risk evaluation with event persistence and outbox delivery dispatch.
- **`services/poller_service.py`**:
  - Autonomous daemon thread that polls ThingSpeak channel every 15 seconds, evaluates risk, logs transitions, and dispatches alerts without blocking HTTP requests.
- **`services/voice_service.py`**:
  - Telephony voice alert engine interfacing with Exotel's outbound call connect API.
  - Normalizes Indian mobile numbers (+91), strictly prohibits emergency dispatch numbers, enforces incident deduplication and a 300-second cooldown window, redacts credentials, generates dynamic ExoML TTS voice prompts, and provides zero-cost dry-run simulation.
- **`routes/`**:
  - `api.py`: JSON endpoints for Flutter and clients (`/api/health`, `/api/status`, `/api/readings/latest`, `/api/readings`, `/api/baseline`, `/api/graphs/summary`).
  - `notifications.py`: Push notification and risk endpoints (`/api/risk/current`, `/api/events`, `/api/notifications/vapid-public-key`, `/api/notifications/subscribe`, `/api/notifications/status`, `/api/notifications/test`).
  - `voice.py`: Telephony endpoints (`/voice-alerts`, `/api/voice/status`, `/api/voice/test-call`, `/api/voice/callback`, `/api/voice/exoml`, `/api/voice/calls`).
  - `dashboard.py`: Renders Overview, Graphs, Baseline, and Alert notification controls.
  - `export.py`: Handles CSV downloads and offline file uploads.
  - `models.py`: Machine Learning studio.

---

## 4. Flutter Integration

Located in `_external_FireShieldAI/`:
- **`FlaskApiService`** (`lib/core/services/flask_api_service.dart`):
  - Configurable base URL: defaults to `http://127.0.0.1:5000` on Web/Desktop and `http://10.0.2.2:5000` on Android emulator.
  - Communicates directly with Flask endpoints for sensor feeds, risk states, event histories, and notification dispatch.
- **`RoomAdaptiveRiskCard`** (`lib/presentation/features/dashboard/widgets/room_adaptive_risk_card.dart`):
  - Displays real-time risk level badge (Hardware Fire, Early Warning, Baseline Anomaly, Normal).
  - Shows baseline temperature deviation, rate-of-rise metrics, and modal dialog to setup mobile alerts via ntfy.
- **`FlaskDeviceRepository`** (`lib/data/repositories/flask_device_repository.dart`):
  - Continuously streams latest readings into Riverpod state without requiring Firebase configuration.

---

## 5. Risk Engine & Notification Architecture (Zero-Firebase)

```
       +---------------------------------------------+
       |   ThingSpeak Poller Daemon (every 15s)      |
       +----------------------+----------------------+
                              |
                              v
       +---------------------------------------------+
       |   Risk Engine (services/risk_engine.py)     |
       |  - HARDWARE_FIRE_ALERT (flame/smoke DO/AO)  |
       |  - EARLY_WARNING (rate-of-rise >= 1.5°C/min)|
       |  - BASELINE_ANOMALY (deviation >= 2.5 sigma)|
       |  - SENSOR_OR_DATA_FAULT (stale / NaN)       |
       |  - NORMAL (3x consecutive recovery check)   |
       +----------------------+----------------------+
                              | Hazard Detected
                              v
       +---------------------------------------------+
       |   SQLite Event Store (data/events.db)       |
       |  - Immutable audit log table (`events`)     |
       |  - Outbox table (`notification_outbox`)     |
       +----------------------+----------------------+
                              | Dispatch
               +--------------+--------------+
               |              |              |
               v              v              v
+-----------------------+ +--------------------+ +------------------------+
|   Standard Web Push   | | ntfy Mobile Alerts | |  Exotel Voice Alerts   |
| - VAPID Web Push      | | - Android & iOS    | | - Automated phone call |
| - Service Worker      | | - Topic subscriber | | - Spoken safety TTS    |
| - Chrome/Edge/Firefox | | - Zero Firebase    | | - Verified Indian Num  |
+-----------------------+ +--------------------+ +------------------------+
```
