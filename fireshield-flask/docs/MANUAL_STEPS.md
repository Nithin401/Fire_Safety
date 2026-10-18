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
