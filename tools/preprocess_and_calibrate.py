#!/usr/bin/env python3
"""
FireShield AI — Multi-Sensor Preprocessing, Dynamic Room Baseline & False Alarm Calibration Tool
================================================================================================
Usage:
  python tools/preprocess_and_calibrate.py --input smart_fire_dataset.csv --output data/processed/smart_fire_dataset_calibrated.csv

Performs:
  1. Data Preprocessing & Validation (NaN cleanup, range checking, timestamp sorting).
  2. Per-Room Dynamic Baseline Calibration (continuous ambient tracking per room).
  3. Dynamic rate-of-change calculation (dT/dt, dGas/dt, thermal & gas Z-scores).
  4. False-Alarm Classification vs. Real Fire Detection.
  5. Exports calibrated, ML-ready feature-engineered CSV.
"""

import os
import sys
import argparse
import datetime
import pandas as pd
import numpy as np
from typing import Tuple, Dict, Any

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai.dynamic_room_baseline import DynamicRoomBaselineEngine, process_dataframe_with_baselines


def clean_and_validate(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    initial_count = len(df)
    report = {
        "initial_rows": initial_count,
        "dropped_nan_rows": 0,
        "clamped_outliers": 0,
        "valid_rows": 0,
        "rooms_detected": []
    }

    # Normalize column names
    col_map = {
        "temp": "temperature",
        "temp_c": "temperature",
        "tempC": "temperature",
        "hum": "humidity",
        "gas": "gas_raw",
        "flame": "flame_raw",
        "device": "device_id",
        "room": "room_id"
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    # Drop fully empty rows
    df = df.dropna(how='all')

    # Convert essential columns to numeric
    numeric_cols = [
        "temperature", "humidity", "pressure",
        "flame_raw", "flame_voltage",
        "gas_raw", "gas_voltage",
        "flame_digital", "servo_angle"
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Drop rows where critical telemetry is missing
    crit_cols = [c for c in ["temperature", "gas_raw", "flame_raw"] if c in df.columns]
    pre_drop = len(df)
    df = df.dropna(subset=crit_cols)
    report["dropped_nan_rows"] = pre_drop - len(df)

    # Sanity bounds clamping
    if "temperature" in df.columns:
        df["temperature"] = df["temperature"].clip(lower=-20.0, upper=120.0)
    if "humidity" in df.columns:
        df["humidity"] = df["humidity"].clip(lower=0.0, upper=100.0)
    if "gas_voltage" in df.columns:
        df["gas_voltage"] = df["gas_voltage"].clip(lower=0.0, upper=5.0)
    if "flame_voltage" in df.columns:
        df["flame_voltage"] = df["flame_voltage"].clip(lower=0.0, upper=5.0)

    # Room/Device ID tracking
    room_col = "room_id" if "room_id" in df.columns else ("device_id" if "device_id" in df.columns else None)
    if room_col:
        report["rooms_detected"] = list(df[room_col].unique())
    else:
        df["room_id"] = "ROOM_1"
        report["rooms_detected"] = ["ROOM_1"]

    report["valid_rows"] = len(df)
    return df, report


def main():
    parser = argparse.ArgumentParser(description="Preprocess sensor data and calculate dynamic room baselines.")
    parser.add_argument("--input", "-i", type=str, default="smart_fire_dataset.csv", help="Input CSV dataset path")
    parser.add_argument("--output", "-o", type=str, default="smart_fire_dataset_calibrated.csv", help="Output calibrated CSV path")
    parser.add_argument("--alpha", "-a", type=float, default=0.01, help="Baseline smoothing rate (default: 0.01)")
    args = parser.parse_args()

    input_path = args.input
    # Search fallback locations if not in current directory
    if not os.path.exists(input_path):
        candidates = [
            os.path.join(os.path.dirname(__file__), "..", input_path),
            os.path.join(os.path.dirname(__file__), "..", "data", "real", input_path),
            os.path.join(os.path.dirname(__file__), "..", "data", input_path),
            os.path.expanduser(r"~\Downloads\files (3)\smart_fire_dataset.csv")
        ]
        for c in candidates:
            if os.path.exists(c):
                input_path = c
                break

    if not os.path.exists(input_path):
        print(f"[!] Warning: Input file '{args.input}' not found. Generating sample multi-sensor dataset with sunny room vs fire scenarios for demonstration.")
        # Generate representative sample containing hot room sunny day + kitchen steam + actual fire
        timestamps = [
            (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=i)).isoformat()
            for i in range(120)
        ]
        sample_data = []
        for i, ts in enumerate(timestamps):
            if i < 40:
                # Normal hot afternoon in Living Room (Temp rises from 31°C to 33.5°C naturally, 0 fire)
                sample_data.append({
                    "timestamp": ts, "device_id": "ESP1", "room_id": "LivingRoom_Sunny",
                    "temperature": 31.0 + (i * 0.06), "humidity": 45.0, "pressure": 1012.0,
                    "flame_raw": 15000, "flame_voltage": 3.1, "gas_raw": 1400 + (i * 2), "gas_voltage": 0.35,
                    "flame_digital": 0, "fire_state": "NORMAL", "servo_angle": 45 + (i % 90)
                })
            elif i < 70:
                # Kitchen cooking steam (Humidity surge, mild gas, no flame, mild temp)
                sample_data.append({
                    "timestamp": ts, "device_id": "ESP1", "room_id": "Kitchen",
                    "temperature": 27.5 + ((i - 40) * 0.03), "humidity": 82.0, "pressure": 1011.8,
                    "flame_raw": 14800, "flame_voltage": 3.0, "gas_raw": 2200, "gas_voltage": 0.55,
                    "flame_digital": 0, "fire_state": "NORMAL", "servo_angle": 90
                })
            else:
                # Actual Fire Outbreak (Rapid temp spike, gas runaway, optical flame triggered)
                step = i - 70
                sample_data.append({
                    "timestamp": ts, "device_id": "ESP1", "room_id": "Kitchen",
                    "temperature": 32.0 + (step * 0.8), "humidity": 30.0, "pressure": 1011.0,
                    "flame_raw": max(15000 - (step * 800), 1200), "flame_voltage": max(3.0 - (step * 0.15), 0.2),
                    "gas_raw": 2500 + (step * 350), "gas_voltage": min(0.6 + (step * 0.1), 4.5),
                    "flame_digital": 1 if step > 3 else 0, "fire_state": "FIRE", "servo_angle": 120
                })
        df_raw = pd.DataFrame(sample_data)
        input_path = "smart_fire_dataset.csv"
        df_raw.to_csv(input_path, index=False)
        print(f"[+] Created demonstration dataset: {input_path}")
    else:
        df_raw = pd.read_csv(input_path)

    print(f"\n==================================================================")
    print(f" FIRESHIELD AI — MULTI-SENSOR PREPROCESSING & CALIBRATION ENGINE")
    print(f"==================================================================")
    print(f"[+] Loaded raw dataset: '{input_path}' ({len(df_raw)} records)")

    # 1. Clean & validate data
    df_clean, report = clean_and_validate(df_raw)
    print(f"[+] Validation Report:")
    print(f"    - Rooms detected: {report['rooms_detected']}")
    print(f"    - Dropped incomplete rows: {report['dropped_nan_rows']}")
    print(f"    - Valid telemetry records: {report['valid_rows']}")

    # 2. Compute dynamic per-room baselines & fusion classification
    room_col = "room_id" if "room_id" in df_clean.columns else "device_id"
    df_calibrated = process_dataframe_with_baselines(df_clean, room_column=room_col)

    # 3. Output directory & save
    output_path = args.output
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    df_calibrated.to_csv(output_path, index=False)
    print(f"\n[SUCCESS] Calibrated dataset exported to:")
    print(f"  -> {output_path}")

    # 4. Summary Statistics & False Alarm Analysis
    verdicts = df_calibrated["ai_classification_verdict"].value_counts().to_dict()
    print(f"\n==================================================================")
    print(f" CLASSIFICATION & FALSE-ALARM SUPPRESSION BREAKDOWN")
    print(f"==================================================================")
    for verdict_label, count in verdicts.items():
        pct = (count / len(df_calibrated)) * 100
        print(f"  * {verdict_label:<25} : {count:>4} samples ({pct:>5.1f}%)")

    # Inspect false alarm suppression examples
    suppressed = df_calibrated[df_calibrated["suppression_reason"] != ""]
    if len(suppressed) > 0:
        print(f"\n[+] Active False Alarm Suppressions Identified: {len(suppressed)}")
        sample_sup = suppressed.iloc[0]
        print(f"    Example: Room='{sample_sup.get(room_col)}' | Temp={sample_sup.get('temperature')}°C | Baseline={sample_sup.get('room_baseline_temp')}°C")
        print(f"    Reason : {sample_sup.get('suppression_reason')}")
    print(f"==================================================================\n")


if __name__ == "__main__":
    main()
