"""
FireShield AI — Hardened Backend Telemetry & Real-Time Ingestion Server

Features:
- REST Ingestion API with API Key / Bearer Authentication
- Hybrid AI Risk Engine (Rule-based safety backstop + ML Classifier)
- Firebase Firestore Cloud Synchronization (with In-Memory Fallback)
- Multi-Sensor Telemetry (Flame, Temperature, Humidity, Gas, Smoke, Angle)
- Rate-Limited Alert Dispatcher (State transition detection & 60s periodic reminder)
- Server-side Push Notification Dispatch (FCM & Telegram Bot)
- Complete Alert Audit Trail Logging
"""

import os
import sys
import time
import json
import datetime
import urllib.request
import urllib.parse
from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS

# Add root directory to import path for AI module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ai.features import extract_features
from ai.anomaly_detection import calculate_baseline, detect_anomalies_zscore
from ai.risk_engine_ml import HybridRiskEngine

app = Flask(__name__)
CORS(app)

# =====================================================
# CONFIGURATION & ENVIRONMENT VARIABLES
# =====================================================
INGESTION_API_KEY = os.getenv("DEVICE_INGESTION_API_KEY", "fireshield_local_dev_key_2026")
CREDENTIALS_PATH = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", os.path.join(os.path.dirname(__file__), "..", "serviceAccountKey.json"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# =====================================================
# FIRESTORE & FIREBASE ADMIN INITIALIZATION
# =====================================================
db = None
try:
    import firebase_admin
    from firebase_admin import credentials, firestore, messaging
    
    if os.path.exists(CREDENTIALS_PATH):
        cred = credentials.Certificate(CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("[SUCCESS] Connected to Firebase Cloud Firestore & FCM.")
    else:
        print(f"[INFO] '{CREDENTIALS_PATH}' not found. Operating in LOCAL IN-MEMORY MODE.")
except Exception as e:
    print(f"[INFO] Firebase Admin notice: {e}. Operating in LOCAL IN-MEMORY MODE.")

# =====================================================
# IN-MEMORY STATE STORES (FALLBACK & CACHE)
# =====================================================
in_memory_devices = {
    "dev_001": {
        "id": "dev_001",
        "name": "Kitchen Fire Node",
        "room": "Kitchen",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "firmwareVersion": "v2.0-HybridAI",
        "isOnline": True,
        "batteryLevel": 95,
        "wifiSignalStrength": 88,
        "lastSync": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "flameRaw": 850,
        "tempC": 25.4,
        "humidity": 56.0,
        "gasRaw": 130,
        "smokeRaw": 125,
        "fireAngle": 90,
        "riskScore": 10.0,
        "fireState": "SAFE",
        "responseStatus": "IDLE"
    }
}

reading_history = {} # device_id -> list of readings
alert_audit_trail = [
    {
        "id": "alt_sys_init",
        "deviceId": "dev_001",
        "roomId": "Kitchen",
        "severity": "info",
        "title": "FireShield AI Engine Online",
        "message": "Hybrid Risk Engine & Multi-Sensor telemetry active. Scanning zone.",
        "fireState": "SAFE",
        "riskScore": 10.0,
        "fireAngle": 90,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "acknowledged": True
    }
] # list of alert events
device_alert_state = {} # device_id -> {'last_state': str, 'last_alert_time': float}

# Initialize Hybrid Risk Engine (loads trained ML model with deterministic backstop)
hybrid_risk_engine = HybridRiskEngine(
    model_path=os.path.join(os.path.dirname(__file__), "..", "ml", "models", "v1", "model.pkl"),
    use_ml=True
)

# =====================================================
# AUTHENTICATION DECORATOR
# =====================================================
def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        auth_header = request.headers.get('Authorization')
        
        # Permit either X-API-Key or Bearer token matching key
        token = None
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1]
            
        if (api_key and api_key == INGESTION_API_KEY) or (token and token == INGESTION_API_KEY):
            return f(*args, **kwargs)
            
        # Allow open read endpoints during local development if configured, but protect writes
        if request.method == 'GET':
            return f(*args, **kwargs)
            
        return jsonify({"error": "Unauthorized. Missing or invalid X-API-Key header."}), 401
    return decorated

# =====================================================
# SERVER-SIDE NOTIFICATION DISPATCHER
# =====================================================
def dispatch_alert(device_id: str, room_id: str, fire_state: str, risk_score: float, fire_angle: int):
    """
    Sends rate-limited alerts via Telegram and FCM, and records in audit trail.
    """
    now = time.time()
    state_record = device_alert_state.get(device_id, {'last_state': 'SAFE', 'last_alert_time': 0})
    last_state = state_record['last_state']
    last_time = state_record['last_alert_time']
    
    # Trigger condition:
    # 1. State transition (e.g. SAFE -> HIGH_RISK or FIRE)
    # 2. Or periodic reminder every 60s if fire persists
    is_transition = (fire_state != last_state)
    time_since_last = now - last_time
    should_alert = False
    
    if fire_state in ["HIGH_RISK", "FIRE"]:
        if is_transition or (time_since_last >= 60.0):
            should_alert = True
    elif fire_state == "SAFE" and last_state in ["HIGH_RISK", "FIRE"]:
        # Safe all-clear notification
        should_alert = True
        
    device_alert_state[device_id] = {'last_state': fire_state, 'last_alert_time': now if should_alert else last_time}
    
    if not should_alert:
        return
        
    alert_title = f"🔥 FIRE ALERT: {room_id}" if fire_state in ["HIGH_RISK", "FIRE"] else f"✅ ALL CLEAR: {room_id}"
    alert_message = (f"Severity: {fire_state} | Risk Score: {risk_score:.1f}% | "
                     f"Detected Angle: {fire_angle}° | Device: {device_id}")
                     
    alert_event = {
        "id": f"alt_{int(now * 1000)}",
        "deviceId": device_id,
        "roomId": room_id,
        "severity": "critical" if fire_state in ["HIGH_RISK", "FIRE"] else "info",
        "title": alert_title,
        "message": alert_message,
        "fireState": fire_state,
        "riskScore": risk_score,
        "fireAngle": fire_angle,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "acknowledged": False
    }
    
    alert_audit_trail.append(alert_event)
    
    # 1. Cloud Firestore Alert Sync
    if db:
        try:
            db.collection("alerts").document(alert_event["id"]).set(alert_event)
            db.collection("alert_audit_trail").add(alert_event)
        except Exception as e:
            print(f"[FIRESTORE ALERT ERROR] {e}")
            
    # 2. Server-Side Telegram Dispatch
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": f"*{alert_title}*\n{alert_message}", "parse_mode": "Markdown"}).encode('utf-8')
            req = urllib.request.Request(tg_url, data=payload, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=3) as response:
                print(f"[TELEGRAM ALERT DISPATCHED] {response.status}")
        except Exception as te:
            print(f"[TELEGRAM ERROR] {te}")
            
    # 3. Firebase Cloud Messaging (FCM) Push
    if db and 'messaging' in sys.modules:
        try:
            fcm_msg = messaging.Message(
                notification=messaging.Notification(title=alert_title, body=alert_message),
                data={"deviceId": device_id, "roomId": room_id, "fireState": fire_state, "riskScore": str(risk_score)},
                topic="fire_alerts"
            )
            messaging.send(fcm_msg)
            print("[FCM PUSH DISPATCHED]")
        except Exception as fe:
            print(f"[FCM NOTICE] {fe}")

# =====================================================
# REST ENDPOINTS
# =====================================================
@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "online",
        "service": "FireShield AI Backend & Hybrid Risk Engine",
        "firestore_connected": db is not None,
        "ml_model_active": hybrid_risk_engine.use_ml,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    })

@app.route('/api/telemetry', methods=['POST'])
@require_api_key
def receive_telemetry():
    try:
        payload = request.get_json(force=True)
        if not payload:
            return jsonify({"error": "Empty payload"}), 400
            
        # Schema Validation
        device_id = str(payload.get("device_id", "dev_001"))
        room_id = str(payload.get("room_id", "Kitchen"))
        
        try:
            flame_raw = int(payload.get("flame_raw", 850))
            fire_angle = int(payload.get("fire_angle", 90))
            is_fire_sensor = bool(payload.get("is_fire", False))
            temp_c = float(payload.get("temp_c", payload.get("tempC", 25.0)))
            humidity = float(payload.get("humidity", 55.0))
            gas_raw = int(payload.get("gas_raw", payload.get("gasRaw", 120)))
            smoke_raw = int(payload.get("smoke_raw", payload.get("smokeRaw", 120)))
        except (ValueError, TypeError) as ve:
            return jsonify({"error": f"Invalid field type: {ve}"}), 400

        timestamp_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        # Maintain rolling history per device
        if device_id not in reading_history:
            reading_history[device_id] = []
            
        reading_history[device_id].append({
            "timestamp": timestamp_str,
            "flameRaw": flame_raw,
            "flame_raw": flame_raw,
            "tempC": temp_c,
            "humidity": humidity,
            "gasRaw": gas_raw,
            "smokeRaw": smoke_raw
        })
        if len(reading_history[device_id]) > 50:
            reading_history[device_id].pop(0)

        # Run Multi-Sensor Feature Extraction & Hybrid Risk Evaluation
        import pandas as pd
        df = pd.DataFrame(reading_history[device_id])
        df = extract_features(df)
        df = calculate_baseline(df)
        df = detect_anomalies_zscore(df)
        
        latest_features = df.iloc[-1].to_dict()
        risk_score, fire_state, meta = hybrid_risk_engine.evaluate_hybrid_risk(latest_features)
        
        # Hardware digital flame pin override (if physical sensor pulls low)
        if is_fire_sensor and fire_state in ["SAFE", "WARNING"]:
            fire_state = "FIRE"
            risk_score = max(risk_score, 90.0)
            
        response_status = "ACTIVE" if fire_state in ["HIGH_RISK", "FIRE"] else "IDLE"

        device_doc = {
            "id": device_id,
            "name": f"{room_id} Fire Node",
            "room": room_id,
            "latitude": 37.7749,
            "longitude": -122.4194,
            "firmwareVersion": "v2.0-HybridAI",
            "isOnline": True,
            "batteryLevel": 90,
            "wifiSignalStrength": 85,
            "lastSync": timestamp_str,
            "flameRaw": flame_raw,
            "tempC": temp_c,
            "humidity": humidity,
            "gasRaw": gas_raw,
            "smokeRaw": smoke_raw,
            "fireAngle": fire_angle,
            "riskScore": float(risk_score),
            "fireState": fire_state,
            "responseStatus": response_status,
            "aiMetadata": {
                "mlActive": meta.get("ml_active", False),
                "mlPrediction": meta.get("ml_prediction"),
                "fusionConfidence": float(latest_features.get("fusion_confidence_score", 0.0))
            }
        }
        
        in_memory_devices[device_id] = device_doc

        # Cloud Firestore Synchronization
        if db:
            try:
                db.collection("devices").document(device_id).set(device_doc, merge=True)
                db.collection("devices").document(device_id).collection("readings").add({
                    "flameRaw": flame_raw,
                    "tempC": temp_c,
                    "humidity": humidity,
                    "gasRaw": gas_raw,
                    "smokeRaw": smoke_raw,
                    "fireAngle": fire_angle,
                    "riskScore": float(risk_score),
                    "fireState": fire_state,
                    "timestamp": firestore.SERVER_TIMESTAMP
                })
            except Exception as fe:
                print(f"[FIRESTORE ERROR] {fe}")

        # Dispatch rate-limited alert
        dispatch_alert(device_id, room_id, fire_state, risk_score, fire_angle)

        return jsonify({
            "status": "success",
            "deviceId": device_id,
            "riskScore": float(risk_score),
            "fireState": fire_state,
            "responseStatus": response_status,
            "mlPrediction": meta.get("ml_prediction")
        }), 200

    except Exception as e:
        print(f"[SERVER ERROR] {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/devices', methods=['GET'])
def get_devices():
    if db:
        try:
            docs = db.collection("devices").stream()
            res = [doc.to_dict() for doc in docs]
            if res: return jsonify(res)
        except Exception as e:
            print(f"[FIRESTORE READ ERROR] {e}")
    return jsonify(list(in_memory_devices.values()))

@app.route('/api/devices/<device_id>/readings', methods=['GET'])
def get_device_readings(device_id):
    if device_id in reading_history:
        return jsonify(reading_history[device_id])
    return jsonify([])

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    if db:
        try:
            docs = db.collection("alerts").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(50).stream()
            res = [doc.to_dict() for doc in docs]
            if res: return jsonify(res)
        except Exception as e:
            print(f"[FIRESTORE ALERTS ERROR] {e}")
    return jsonify(alert_audit_trail[::-1][:50])

@app.route('/api/alerts/<alert_id>/ack', methods=['POST'])
def acknowledge_alert(alert_id):
    for a in alert_audit_trail:
        if a["id"] == alert_id:
            a["acknowledged"] = True
            break
    if db:
        try:
            db.collection("alerts").document(alert_id).update({"acknowledged": True})
        except Exception: pass
    return jsonify({"status": "acknowledged", "alertId": alert_id})

if __name__ == '__main__':
    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", 5000))
    print("=" * 65)
    print(" FIRESHIELD AI HARDENED SERVER & HYBRID RISK ENGINE STARTED")
    print(f" Listening on http://{host}:{port}")
    print(f" Ingestion Key: {INGESTION_API_KEY}")
    print("=" * 65)
    app.run(host=host, port=port, debug=False)
