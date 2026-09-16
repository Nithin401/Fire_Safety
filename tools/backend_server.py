import os
import sys
import time
import json
import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

# Add root directory to import path for AI module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ai.features import extract_features
from ai.anomaly_detection import calculate_baseline, detect_anomalies_zscore
from ai.risk_engine import RiskEngine

app = Flask(__name__)
CORS(app)

# =====================================================
# FIRESTORE & BACKEND INITIALIZATION
# =====================================================
CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "..", "serviceAccountKey.json")

db = None
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    
    if os.path.exists(CREDENTIALS_PATH):
        cred = credentials.Certificate(CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("[SUCCESS] Connected to Firebase Cloud Firestore.")
    else:
        print(f"[INFO] '{CREDENTIALS_PATH}' not found. Operating in LOCAL IN-MEMORY MODE.")
except Exception as e:
    print(f"[INFO] Firebase Admin SDK notice: {e}. Operating in LOCAL IN-MEMORY MODE.")

# Local in-memory state store fallback
in_memory_devices = {
    "dev_001": {
        "id": "dev_001",
        "name": "Kitchen Fire Node",
        "room": "Kitchen",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "firmwareVersion": "v2.0-AI",
        "isOnline": True,
        "batteryLevel": 95,
        "wifiSignalStrength": 88,
        "lastSync": datetime.datetime.now().isoformat(),
        "flameRaw": 850,
        "fireAngle": 90,
        "riskScore": 10.0,
        "fireState": "SAFE",
        "responseStatus": "IDLE"
    }
}

# AI Engine instance
risk_engine = RiskEngine()
reading_history = []

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "online",
        "firestore_connected": db is not None,
        "timestamp": datetime.datetime.now().isoformat()
    })

@app.route('/api/telemetry', methods=['POST'])
def receive_telemetry():
    try:
        payload = request.get_json(force=True)
        device_id = payload.get("device_id", "dev_001")
        room_id = payload.get("room_id", "Kitchen")
        flame_raw = int(payload.get("flame_raw", 800))
        fire_angle = int(payload.get("fire_angle", 90))
        is_fire_sensor = payload.get("is_fire", False)
        temp_c = float(payload.get("temp_c", payload.get("tempC", 25.0)))
        humidity = float(payload.get("humidity", 55.0))
        gas_raw = int(payload.get("gas_raw", payload.get("gasRaw", 120)))
        smoke_raw = int(payload.get("smoke_raw", payload.get("smokeRaw", 120)))
        
        timestamp_str = datetime.datetime.now().isoformat()
        
        # Keep history buffer for AI analysis
        reading_history.append({
            "pc_timestamp": timestamp_str,
            "flame_raw": flame_raw,
            "temp_c": temp_c,
            "humidity": humidity,
            "gas_raw": gas_raw,
            "smoke_raw": smoke_raw
        })
        if len(reading_history) > 100:
            reading_history.pop(0)
            
        # Run AI Risk Engine Analysis
        import pandas as pd
        df = pd.DataFrame(reading_history)
        df = extract_features(df)
        df = calculate_baseline(df)
        df = detect_anomalies_zscore(df)
        
        latest_row = df.iloc[-1]
        dev = latest_row.get('deviation_from_baseline', 0)
        roc = latest_row.get('first_derivative', 0)
        anomaly_flag = latest_row.get('anomaly_flag_zscore', 0)
        
        # Calculate Risk Score (0-100) & State (SAFE, WARNING, HIGH_RISK, FIRE)
        risk_score, fire_state = risk_engine.evaluate_risk(dev, roc, anomaly_flag)
        
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
            "firmwareVersion": "v2.0-AI",
            "isOnline": True,
            "batteryLevel": 90,
            "wifiSignalStrength": 85,
            "lastSync": timestamp_str,
            "flameRaw": flame_raw,
            "fireAngle": fire_angle,
            "tempC": temp_c,
            "humidity": humidity,
            "gasRaw": gas_raw,
            "smokeRaw": smoke_raw,
            "riskScore": float(risk_score),
            "fireState": fire_state,
            "responseStatus": response_status
        }
        
        # Update local RAM
        in_memory_devices[device_id] = device_doc

        # Sync to Cloud Firestore if connected
        if db:
            try:
                db.collection("devices").document(device_id).set(device_doc, merge=True)
                db.collection("devices").document(device_id).collection("readings").add({
                    "flameRaw": flame_raw,
                    "fireAngle": fire_angle,
                    "tempC": temp_c,
                    "humidity": humidity,
                    "gasRaw": gas_raw,
                    "smokeRaw": smoke_raw,
                    "riskScore": risk_score,
                    "fireState": fire_state,
                    "timestamp": firestore.SERVER_TIMESTAMP
                })
                
                # Push Alert if Critical
                if fire_state in ["HIGH_RISK", "FIRE"]:
                    db.collection("alerts").add({
                        "deviceId": device_id,
                        "room": room_id,
                        "severity": "critical",
                        "title": f"FIRE ALERT - {room_id}",
                        "message": f"Fire detected at {fire_angle}deg angle! Risk Score: {risk_score:.1f}%",
                        "timestamp": firestore.SERVER_TIMESTAMP
                    })
                print(f"[FIRESTORE] Updated {device_id} | State: {fire_state} | Risk: {risk_score:.1f}%")
            except Exception as fe:
                print(f"[FIRESTORE ERROR] {fe}")

        print(f"[AI ENGINE] Device: {device_id} | Raw: {flame_raw} | Angle: {fire_angle}deg | Risk: {risk_score:.1f}% | State: {fire_state}")
        
        return jsonify({
            "status": "success",
            "risk_score": risk_score,
            "fire_state": fire_state,
            "response_status": response_status
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Telemetry handling error: {e}")
        return jsonify({"error": str(e)}), 400

@app.route('/api/devices', methods=['GET'])
def get_devices():
    if db:
        try:
            docs = db.collection("devices").stream()
            result = [doc.to_dict() for doc in docs]
            if result:
                return jsonify(result)
        except Exception as e:
            print(f"[FIRESTORE READ ERROR] {e}")
            
    return jsonify(list(in_memory_devices.values()))

if __name__ == '__main__':
    print("=" * 60)
    print(" FIRESHIELD AI BACKEND SERVER & FIRESTORE ENGINE STARTED")
    print(" Ingestion Endpoint: http://0.0.0.0:5000/api/telemetry")
    print(" Devices Endpoint:   http://0.0.0.0:5000/api/devices")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=False)
