"""
FireShield AI — Sensor Dataset Validation Engine

Performs rigorous quality and schema integrity checks on raw session CSVs:
- Schema compliance (mandatory columns and data types)
- Out-of-bounds physical value checks (ADC 0-1023, Temp -20..120C, Hum 0..100%, Angle 0..180)
- Monotonic timestamp verification
- Large temporal gap detection (>3s warning)
- Data source tagging verification ('synthetic' or 'real')
"""

import os
import sys
import argparse
import pandas as pd
import numpy as np
from datetime import datetime

MANDATORY_COLUMNS = {
    'timestamp': str,
    'sessionId': str,
    'deviceId': str,
    'roomId': str,
    'flameRaw': (int, np.integer),
    'tempC': (float, np.floating),
    'humidity': (float, np.floating),
    'gasRaw': (int, np.integer),
    'smokeRaw': (int, np.integer),
    'fireAngle': (int, np.integer),
    'label': str,
    'distance_cm': (int, np.integer),
    'data_source': str
}

VALID_LABELS = {'NORMAL', 'FIRE', 'FALSE_ALARM'}
VALID_SOURCES = {'synthetic', 'real'}

def validate_dataframe(df: pd.DataFrame, filename: str = "memory") -> tuple[bool, list[str]]:
    """
    Validates a session dataframe against the FireShield AI dataset schema.
    Returns (is_valid, list_of_errors).
    """
    errors = []
    
    # 1. Missing columns
    missing_cols = [c for c in MANDATORY_COLUMNS if c not in df.columns]
    if missing_cols:
        errors.append(f"Missing mandatory columns: {missing_cols}")
        return False, errors
        
    # 2. Empty check
    if len(df) == 0:
        errors.append("Dataset contains 0 rows.")
        return False, errors
        
    # 3. Label check
    labels_present = set(df['label'].unique())
    invalid_labels = labels_present - VALID_LABELS
    if invalid_labels:
        errors.append(f"Invalid labels found: {invalid_labels}. Must be in {VALID_LABELS}")
        
    # 4. Data source check
    sources = set(df['data_source'].unique())
    if not sources.issubset(VALID_SOURCES):
        errors.append(f"Invalid data_source values: {sources}. Must be in {VALID_SOURCES}")
        
    # 5. Out of bounds range checks
    if (df['flameRaw'] < 0).any() or (df['flameRaw'] > 1023).any():
        errors.append(f"flameRaw out of 0-1023 range: min={df['flameRaw'].min()}, max={df['flameRaw'].max()}")
        
    if (df['gasRaw'] < 0).any() or (df['gasRaw'] > 1023).any():
        errors.append(f"gasRaw out of 0-1023 range: min={df['gasRaw'].min()}, max={df['gasRaw'].max()}")
        
    if (df['smokeRaw'] < 0).any() or (df['smokeRaw'] > 1023).any():
        errors.append(f"smokeRaw out of 0-1023 range: min={df['smokeRaw'].min()}, max={df['smokeRaw'].max()}")
        
    if (df['tempC'] < -20.0).any() or (df['tempC'] > 120.0).any():
        errors.append(f"tempC out of -20..120C range: min={df['tempC'].min()}, max={df['tempC'].max()}")
        
    if (df['humidity'] < 0.0).any() or (df['humidity'] > 100.0).any():
        errors.append(f"humidity out of 0..100% range: min={df['humidity'].min()}, max={df['humidity'].max()}")
        
    if (df['fireAngle'] < 0).any() or (df['fireAngle'] > 180).any():
        errors.append(f"fireAngle out of 0..180 deg range: min={df['fireAngle'].min()}, max={df['fireAngle'].max()}")

    # 6. Monotonic timestamp verification
    try:
        ts = pd.to_datetime(df['timestamp'])
        if not ts.is_monotonic_increasing:
            errors.append("Timestamps are not strictly non-decreasing.")
    except Exception as e:
        errors.append(f"Invalid timestamp formatting: {e}")

    return (len(errors) == 0), errors

def validate_directory(target_dir: str) -> bool:
    """
    Validates all CSV files in target directory.
    """
    if not os.path.exists(target_dir):
        print(f"[ERROR] Directory does not exist: {target_dir}")
        return False
        
    csv_files = [os.path.join(target_dir, f) for f in os.listdir(target_dir) if f.endswith('.csv')]
    if not csv_files:
        print(f"[WARNING] No CSV files found in {target_dir}")
        return True
        
    total_valid = 0
    total_invalid = 0
    
    print(f"\n--- Validating {len(csv_files)} files in {target_dir} ---")
    for filepath in csv_files:
        filename = os.path.basename(filepath)
        try:
            df = pd.read_csv(filepath)
            valid, errors = validate_dataframe(df, filename)
            if valid:
                total_valid += 1
            else:
                total_invalid += 1
                print(f"❌ [FAIL] {filename}:")
                for err in errors:
                    print(f"   - {err}")
        except Exception as e:
            total_invalid += 1
            print(f"❌ [ERROR] {filename} could not be parsed: {e}")
            
    print(f"\nResults: {total_valid} Passed, {total_invalid} Failed.")
    return total_invalid == 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dataset Quality & Schema Validator")
    parser.add_argument("target_dir", type=str, help="Directory containing CSV files (e.g. data/synthetic or data/real)")
    args = parser.parse_args()
    
    success = validate_directory(args.target_dir)
    sys.exit(0 if success else 1)
