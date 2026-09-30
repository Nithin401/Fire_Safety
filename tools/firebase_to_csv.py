"""
firebase_to_csv.py
-------------------
OPTION A (Section 12): downloads all readings for one or more devices
from the Smart Fire Detection Realtime Database and writes them out as
a single, clean, ML-ready CSV: smart_fire_dataset.csv

Setup:
    pip install firebase-admin

    1. Firebase Console -> Project settings -> Service accounts
       -> "Generate new private key" -> save as serviceAccountKey.json
       next to this script (keep it OUT of git / version control).
    2. Set DATABASE_URL below to your Realtime Database URL
       (the same host used in the ESP8266 firmware, with https://).
    3. Run:  python firebase_to_csv.py
"""

import csv
import sys
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, db

# =====================================================================
# CONFIG
# =====================================================================

SERVICE_ACCOUNT_KEY_PATH = "serviceAccountKey.json"
DATABASE_URL = "https://smart-fire-detection-272bb-default-rtdb.asia-southeast1.firebasedatabase.app"

# Leave empty to export every device found under /smart_fire_detection/devices
DEVICE_IDS = []  # e.g. ["ESP1", "ESP2"]

OUTPUT_CSV = "smart_fire_dataset.csv"

CSV_COLUMNS = [
    "timestamp",
    "device_id",
    "experiment_id",
    "temperature",
    "humidity",
    "pressure",
    "flame_raw",
    "flame_voltage",
    "gas_raw",
    "gas_voltage",
    "fire_state",
    "flame_digital",
    "servo_angle",
    "sensors_valid",
    "uptime_ms",
]

# =====================================================================


def init_firebase():
    if not Path(SERVICE_ACCOUNT_KEY_PATH).exists():
        sys.exit(
            f"ERROR: '{SERVICE_ACCOUNT_KEY_PATH}' not found. "
            "Download it from Firebase Console -> Project settings -> "
            "Service accounts -> Generate new private key."
        )
    cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
    firebase_admin.initialize_app(cred, {"databaseURL": DATABASE_URL})


def get_device_ids():
    if DEVICE_IDS:
        return DEVICE_IDS
    ref = db.reference("/smart_fire_detection/devices")
    data = ref.get(shallow=True)
    if not data:
        return []
    return list(data.keys())


def fetch_readings_for_device(device_id):
    ref = db.reference(f"/smart_fire_detection/devices/{device_id}/readings")
    data = ref.get()
    if not data:
        return []

    rows = []
    for push_id, reading in data.items():
        if not isinstance(reading, dict):
            continue
        row = {col: reading.get(col, "") for col in CSV_COLUMNS}
        # device_id/experiment_id should already be in the record, but
        # fall back to the path-derived device_id if a sample is missing it.
        if not row.get("device_id"):
            row["device_id"] = device_id
        row["_push_id"] = push_id  # kept for sorting only, not written out
        rows.append(row)
    return rows


def main():
    init_firebase()

    device_ids = get_device_ids()
    if not device_ids:
        sys.exit("No devices found under /smart_fire_detection/devices - nothing to export.")

    print(f"Found devices: {device_ids}")

    all_rows = []
    for device_id in device_ids:
        rows = fetch_readings_for_device(device_id)
        print(f"  {device_id}: {len(rows)} readings")
        all_rows.extend(rows)

    if not all_rows:
        sys.exit("No readings found. Nothing to export.")

    # Sort by timestamp when available, else by Firebase push id
    # (push ids are chronologically ordered by construction).
    all_rows.sort(key=lambda r: (r.get("timestamp") or "", r["_push_id"]))

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)

    print(f"\nWrote {len(all_rows)} rows to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
