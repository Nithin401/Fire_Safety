# Manual Setup and Operations Guide

This guide describes how to configure credentials, start the Flask backend, download ThingSpeak historical data, and run the Flutter application.

---

## 1. Local Configuration (.env)

Create your local configuration file by copying `.env.example`:

```bash
# In the fireshield-flask directory:
copy .env.example .env
```

Populate the following variables:

```ini
# ThingSpeak Channel Settings
THINGSPEAK_CHANNEL_ID=your_thingspeak_channel_id_here
THINGSPEAK_READ_API_KEY=your_read_api_key_if_channel_is_private
THINGSPEAK_BASE_URL=https://api.thingspeak.com

# Flask Settings
FLASK_SECRET_KEY=generate_a_random_32_char_secret_string
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=false

# Polling & Refresh
POLL_INTERVAL_SECONDS=15
MAX_HISTORY_RESULTS=500
CACHE_TTL_SECONDS=15
STALE_THRESHOLD_SECONDS=60

# Allowed CORS Origins (Include your Flutter web host)
CORS_ALLOWED_ORIGINS=http://localhost:5000,http://127.0.0.1:5000,http://localhost:3000,http://127.0.0.1:3000,http://localhost:8080,http://127.0.0.1:8080
```

> **Security Note:** Never commit `fireshield-flask/.env` or `secrets/.env`. If any credential was previously committed to GitHub, rotate it immediately in the ThingSpeak console.

---

## 2. Running the Python Flask Backend

### Prerequisites
- Python 3.10+ installed.

### Setup and Start:
```bash
cd d:\StartUp\Fire_Safety\fireshield-flask

# Install dependencies
pip install -r requirements.txt

# Run automated tests to verify environment
pytest tests/ -v

# Start the Flask server
python app.py
```

The operational dashboard will be accessible at:
- Overview: `http://localhost:5000/overview`
- Sensor Graphs: `http://localhost:5000/graphs`
- History & CSV Export: `http://localhost:5000/history`
- Room Baseline: `http://localhost:5000/baseline`
- ML Studio: `http://localhost:5000/ml-studio`
- API Health: `http://localhost:5000/api/health`

---

## 3. Downloading Historical ThingSpeak Data

To fetch and persist historical feeds from your ThingSpeak channel to local raw and processed CSVs:

```bash
cd d:\StartUp\Fire_Safety\fireshield-flask

# Download using channel ID and key in .env:
python scripts/download_thingspeak_data.py --limit 500

# Or supply arguments directly:
python scripts/download_thingspeak_data.py --channel-id <CHANNEL_ID> --api-key <READ_KEY> --limit 1000
```

Outputs are automatically saved with deduplication and metadata:
- Raw schema (`field1`..`field6`): `data/raw/thingspeak_<channel>_<date>_raw.csv`
- Processed schema (`flame_raw`, `temperature_c`, etc.): `data/processed/thingspeak_<channel>_<date>_processed.csv`
- Retrieval metadata: `data/raw/thingspeak_<channel>_<date>.json`

---

## 4. Training Room Environmental Baseline

To calculate the learned statistical baseline from recorded telemetry:

```bash
cd d:\StartUp\Fire_Safety\fireshield-flask

# Train using live ThingSpeak channel data:
python scripts/train_baseline.py --room "Living Room" --limit 500

# Or train using a local dataset (e.g. smart_fire_dataset.csv):
python scripts/train_baseline.py --csv ../smart_fire_dataset.csv --room "Living Room Sunny"
```

The resulting model parameters and 2-sigma variation bands are saved to:
`data/models/room_baseline.json`

---

## 5. Running the Flutter Application

The Flutter application connects directly to the Flask backend without requiring Firebase.

```bash
cd d:\StartUp\Fire_Safety\_external_FireShieldAI

# Get packages
flutter pub get

# Run code analysis
flutter analyze

# Run unit and integration tests
flutter test

# Run Flutter Web locally
flutter run -d chrome

# Or build production Web bundle
flutter build web --release
```

### Network URL Configuration for Flutter:
- **Chrome / Web / Windows desktop**: Connects automatically to `http://127.0.0.1:5000`.
- **Android Emulator**: Uses `http://10.0.2.2:5000` (built into `FlaskApiService.defaultBaseUrl`).
- **Physical Mobile Device**: Change the URL in `FlaskApiService` to your machine's local Wi-Fi IP (e.g., `http://192.168.1.100:5000`).

---

## 6. Production Deployment

### Flask Backend Deployment (Render, Railway, DigitalOcean, or AWS):
1. Configure environment variables in the host dashboard (`THINGSPEAK_CHANNEL_ID`, `THINGSPEAK_READ_API_KEY`, `FLASK_SECRET_KEY`, `CORS_ALLOWED_ORIGINS`).
2. Run using a production WSGI server:
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
   ```
3. Set `CORS_ALLOWED_ORIGINS` to the public domain hosting your Flutter web app.
4. Ensure HTTPS is enabled.

### Flutter Web Deployment:
1. Build the release bundle:
   ```bash
   flutter build web --release
   ```
2. Copy `build/web/` to your static hosting provider (GitHub Pages, Netlify, or Vercel).
3. If hosting publicly, ensure `FlaskApiService` points to your public HTTPS Flask API endpoint.

---

## 7. Zero-Firebase Real-Time Alert Setup

### A. Mobile Notifications via ntfy (Recommended for Android / iOS)
No Firebase SDKs or accounts are needed.

1. Install the official **ntfy** app on your phone:
   - Android: Search `ntfy` on [Google Play Store](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
   - iOS: Search `ntfy` on [Apple App Store](https://apps.apple.com/app/ntfy/id1625396347)
2. Open the ntfy app and tap the **+** (Subscribe to topic) button.
3. Enter your topic name: `fireshield_alerts_3534677` (configured in `fireshield-flask/.env` as `NTFY_TOPIC`).
4. Tap **Subscribe**.
5. Test delivery immediately:
   - Open `http://localhost:5000/overview` on your computer or tap **Send Test Alert** in the Flutter app.
   - You will hear an audible alert with `[FIRE ALERT]` or `[EARLY WARNING]` on your phone.

### B. In-Browser Web Push Notifications (Desktop / PWA)
1. Open the Flask dashboard at `http://localhost:5000/overview` (or your Flutter web app).
2. Click **Enable Browser Push Notifications**.
3. When prompted by Chrome / Edge / Firefox, click **Allow**.
4. Standard VAPID keys are auto-generated in `fireshield-flask/data/vapid_keys.json`.
5. Background alerts will appear on your desktop tray even when the tab is backgrounded.

---

## 8. Automated Outbound Voice Calls Setup (Exotel India)

When a critical fire incident occurs (`field6 == 1` or raw flame/smoke active), FireShield AI can automatically place a spoken phone call to your verified Indian mobile number.

### A. Setting Up Exotel Trial Account
1. Create a free trial account at [Exotel Trial Signup](https://docs.exotel.com/business-phone-system/create-a-trial-account).
2. Exotel grants **₹1,000 worth of trial credits** for prototype testing.
3. Complete mobile verification for your personal Android phone number. During trial, Exotel outbound calls are restricted strictly to your verified account numbers.
4. From the Exotel Dashboard:
   - Copy **Account SID**
   - Copy **API Key**
   - Copy **API Token**
   - Note your assigned Exotel **Virtual Number** (Caller ID, e.g. `0804710XXXX` or `011XXXXXXX`)

### B. Configuring `fireshield-flask/.env`
In `fireshield-flask/.env`, add:
```ini
# Exotel Configuration
EXOTEL_ACCOUNT_SID=your_exotel_account_sid_here
EXOTEL_API_KEY=your_exotel_api_key_here
EXOTEL_API_TOKEN=your_exotel_api_token_here
EXOTEL_CALLER_ID=your_assigned_exotel_virtual_number
EXOTEL_API_BASE_URL=https://api.exotel.com

# Recipient phone in E.164 (+91XXXXXXXXXX)
FIRESHIELD_ALERT_PHONE=+919876543210

# Activation Controls
VOICE_ALERT_ENABLED=true
VOICE_ALERT_DRY_RUN=true       # Keep 'true' to verify without consuming trial credits
VOICE_ALERT_COOLDOWN_SECONDS=300
PUBLIC_BASE_URL=http://localhost:5000
```

### C. Testing Steps
1. Navigate to `http://localhost:5000/voice-alerts` in your browser.
2. Verify the **Exotel Credentials Checklist** shows all checkmarks.
3. Click **📞 Place Test Call Now** to test in safe Dry-Run mode.
4. Once verified, set `VOICE_ALERT_DRY_RUN=false` in `.env` and restart Flask to place a real trial call to your verified Android phone.
5. Answer the call to hear the automated voice alert:
   > *"FireShield AI critical alert. A possible fire condition has been detected. Please check the affected area safely. This is an automated safety alert."*

