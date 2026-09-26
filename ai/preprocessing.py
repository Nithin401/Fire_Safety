import pandas as pd
import numpy as np

def validate_dataset(df):
    """
    Validates the dataset for quality issues.
    """
    report = {
        "total_rows": len(df),
        "missing_values": df.isnull().sum().to_dict(),
        "duplicate_timestamps": df.duplicated(subset=['pc_timestamp']).sum(),
        "removed_rows": 0,
        "warnings": [],
        "status": "DATA QUALITY PASS"
    }

    # Check for missing values
    if df['flame_raw'].isnull().any():
        report["warnings"].append("Missing flame_raw values detected.")
        initial_len = len(df)
        df = df.dropna(subset=['flame_raw'])
        report["removed_rows"] += (initial_len - len(df))

    # Convert to numeric
    df['flame_raw'] = pd.to_numeric(df['flame_raw'], errors='coerce')
    
    # Check invalid values
    invalid_mask = df['flame_raw'].isnull() | (df['flame_raw'] < 0) | (df['flame_raw'] > 1024)
    if invalid_mask.any():
        report["warnings"].append(f"Found {invalid_mask.sum()} invalid flame_raw values (out of 0-1024 range or NaN).")
        df = df[~invalid_mask]
        report["removed_rows"] += invalid_mask.sum()

    # Sort by time
    df['pc_timestamp'] = pd.to_datetime(df['pc_timestamp'])
    df = df.sort_values(by='pc_timestamp').reset_index(drop=True)

    # Flatline detection
    if len(df) > 10 and df['flame_raw'].std() == 0:
        report["warnings"].append("Flatline detected. Sensor might be disconnected.")
        
    if len(report["warnings"]) > 0:
        report["status"] = "DATA QUALITY WARNING"

    return df, report

def clean_data(filepath):
    df = pd.read_csv(filepath)
    df_clean, report = validate_dataset(df)
    return df_clean, report
