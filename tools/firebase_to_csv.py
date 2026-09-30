#!/usr/bin/env python3
"""
FireShield AI — Firebase Realtime Database to ML-Ready CSV Exporter
===================================================================
Exports all multi-sensor time-series readings from Firebase Realtime Database
into 'smart_fire_dataset.csv' matching the standardized 18-column Master Schema.

Usage:
    pip install firebase-admin
    python tools/firebase_to_csv.py

Prerequisites:
    Download serviceAccountKey.json from Firebase Console -> Project Settings
    -> Service Accounts -> "Generate new private key", and place next to this script.
"""

import csv
import sys
import os
from pathlib import Path

try:
    import firebase_admin
    from firebase_admin import credentials, db
except ImportError:
    sys.exit("ERROR: firebase-admin is required. Run: pip install firebase-admin")

# =====================================================================
# CONFIGURATION
# =====================================================================

SERVICE_ACCOUNT_KEY_PATH = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "serviceAccountKey.json")
DATABASE_URL = os.getenv(
    "FIREBASE_DATABASE_URL",
    "https://smart-fire-detection-272bb-default-rtdb.asia-southeast1.firebasedatabase.app"
)

# Specific devices to export (leave empty to discover all devices under /devices)
DEVICE_IDS = []

OUTPUT_CSV = "smart_fire_dataset.csv"

# Exact 18-column Master Schema Specification
CSV_COLUMNS = [
    "timestamp",
    "device_id",
    "zone_id",
    "experiment_id",
    "temperature_c",
    "humidity_percent",
    "pressure_hpa",
    "flame_raw",
    "flame_voltage",
    "flame_digital",
    "gas_raw",
    "gas_voltage",
    "servo_angle",
    "fire_state",
    "risk_score",
    "ml_prediction",
    "ml_confidence",
    "responder_status"
]

# =====================================================================
# FIREBASE INITIALIZATION
# =====================================================================

def init_firebase():
    key_path = Path(SERVICE_ACCOUNT_KEY_PATH)
    if not key_path.exists():
        # Check parent directory
        parent_cand = Path(os.path.join(os.path.dirname(__file__), "..", SERVICE_ACCOUNT_KEY_PATH))
        if parent_cand.exists():
            key_path = parent_cand
        else:
            sys.exit(
                f"ERROR: '{SERVICE_ACCOUNT_KEY_PATH}' not found.\n"
                "Please download it from Firebase Console -> Project settings -> "
                "Service accounts -> 'Generate new private key' and save as serviceAccountKey.json."
            )

    cred = credentials.Certificate(str(key_path))
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(cred, {"databaseURL": DATABASE_URL})


def get_device_ids():
    if DEVICE_IDS:
        return DEVICE_IDS

    # Check primary path: /devices
    ref = db.reference("/devices")
    data = ref.get(shallow=True)
    if data and isinstance(data, dict):
        return list(data.keys())

    # Fallback path: /smart_fire_detection/devices
    ref_legacy = db.reference("/smart_fire_detection/devices")
    data_legacy = ref_legacy.get(shallow=True)
    if data_legacy and isinstance(data_legacy, dict):
        return list(data_legacy.keys())

    return ["ESP1"]


def fetch_readings_for_device(device_id: str):
    # Try primary path: /devices/{device_id}/readings
    ref = db.reference(f"/devices/{device_id}/readings")
    data = ref.get()

    if not data or not isinstance(data, dict):
        # Fallback to legacy path
        ref = db.reference(f"/smart_fire_detection/devices/{device_id}/readings")
        data = ref.get()

    if not data or not isinstance(data, dict):
        return []

    rows = []
    for push_id, val in data.items():
        if not isinstance(val, dict):
            continue

        reading = dict(val)
        # Standardize temperature and humidity aliases
        temp_c = reading.get("temperature_c", reading.get("temperature", ""))
        hum_pct = reading.get("humidity_percent", reading.get("humidity", ""))
        press_hpa = reading.get("pressure_hpa", reading.get("pressure", 1013.25))

        row = {
            "timestamp": reading.get("timestamp", ""),
            "device_id": reading.get("device_id", device_id),
            "zone_id": reading.get("zone_id", "ZONE_1"),
            "experiment_id": reading.get("experiment_id", "EXP001"),
            "temperature_c": temp_c,
            "humidity_percent": hum_pct,
            "pressure_hpa": press_hpa,
            "flame_raw": reading.get("flame_raw", ""),
            "flame_voltage": reading.get("flame_voltage", ""),
            "flame_digital": reading.get("flame_digital", 0),
            "gas_raw": reading.get("gas_raw", ""),
            "gas_voltage": reading.get("gas_voltage", ""),
            "servo_angle": reading.get("servo_angle", 90),
            "fire_state": reading.get("fire_state", "NORMAL"),
            "risk_score": reading.get("risk_score", 0.0),
            "ml_prediction": reading.get("ml_prediction", "NORMAL"),
            "ml_confidence": reading.get("ml_confidence", 0.0),
            "responder_status": reading.get("responder_status", "IDLE"),
            "_push_id": push_id
        }
        rows.append(row)

    return rows


def main():
    print(f"==================================================================")
    print(f" FIRESHIELD AI — FIREBASE REALTIME DATABASE DATASET EXPORTER")
    print(f"==================================================================")
    init_firebase()

    device_ids = get_device_ids()
    print(f"[+] Querying devices: {device_ids}")

    all_rows = []
    for d_id in device_ids:
        device_rows = fetch_readings_for_device(d_id)
        print(f"  * {d_id}: {len(device_rows)} records fetched")
        all_rows.extend(device_rows)

    if not all_rows:
        sys.exit("[!] No records found under Firebase database path. Verify firmware is uploading.")

    # Sort chronologically by timestamp, then by push id
    all_rows.sort(key=lambda r: (str(r.get("timestamp") or ""), str(r.get("_push_id") or "")))

    output_path = OUTPUT_CSV
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)

    print(f"\n[SUCCESS] Exported {len(all_rows)} verified records to '{output_path}'")
    print(f"Schema: {len(CSV_COLUMNS)} columns ({', '.join(CSV_COLUMNS[:5])}...)")
    print(f"==================================================================")


if __name__ == "__main__":
    main()
