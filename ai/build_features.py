"""
FireShield AI — Feature Table Generator

Processes session-grouped time-series data from data/processed/ into
a comprehensive ML-ready feature table in data/features/v1/.
Guarantees zero cross-session leakage during rolling feature extraction.
"""

import os
import argparse
import pandas as pd
import numpy as np
from ai.features import extract_features
from ai.anomaly_detection import calculate_baseline, detect_anomalies_zscore, detect_anomalies_isolation_forest

def process_session_features(session_df: pd.DataFrame) -> pd.DataFrame:
    """
    Applies the full feature engineering pipeline to a single isolated session.
    """
    df = session_df.sort_values(by='timestamp').copy()
    
    # 1. Multi-channel rolling features and derivatives
    df = extract_features(df, window_size=5)
    
    # 2. Baseline and Z-score calculations per channel
    df['flame_baseline'] = df['flameRaw'].rolling(window=50, min_periods=1).median()
    df['deviation_from_baseline'] = df['flameRaw'] - df['flame_baseline']
    
    df['temp_baseline'] = df['tempC'].rolling(window=50, min_periods=1).median()
    df['temp_deviation'] = df['tempC'] - df['temp_baseline']
    
    df['gas_baseline'] = df['gasRaw'].rolling(window=50, min_periods=1).median()
    df['gas_deviation'] = df['gasRaw'] - df['gas_baseline']
    
    # Flame rolling z-score
    long_mean = df['flameRaw'].rolling(window=50, min_periods=1).mean()
    long_std = df['flameRaw'].rolling(window=50, min_periods=1).std().fillna(1e-5)
    df['z_score'] = (df['flameRaw'] - long_mean) / (long_std + 1e-5)
    df['anomaly_flag_zscore'] = (df['z_score'].abs() > 3.0).astype(int)
    
    # 3. Isolation forest unsupervised feature embedding
    df = detect_anomalies_isolation_forest(df)
    
    # 4. Time since last anomaly (in seconds)
    anomaly_indices = df.index[df['anomaly_flag_zscore'] == 1].tolist()
    time_since_anomaly = []
    last_anom_time = None
    
    for idx, row in df.iterrows():
        t = pd.to_datetime(row['timestamp'])
        if row['anomaly_flag_zscore'] == 1:
            last_anom_time = t
            time_since_anomaly.append(0.0)
        elif last_anom_time is not None:
            time_since_anomaly.append((t - last_anom_time).total_seconds())
        else:
            time_since_anomaly.append(999.0) # No anomaly yet
            
    df['time_since_last_anomaly'] = time_since_anomaly
    
    return df

def build_features_table(input_path: str = "data/processed/v1/dataset.parquet", 
                         output_dir: str = "data/features/v1") -> pd.DataFrame:
    """
    Builds the master feature dataset grouped by session.
    """
    if not os.path.exists(input_path):
        # Fallback to CSV if parquet not present
        input_path = input_path.replace('.parquet', '.csv')
        
    print(f"[INFO] Reading processed dataset from {input_path}...")
    if input_path.endswith('.parquet'):
        master_df = pd.read_parquet(input_path)
    else:
        master_df = pd.read_csv(input_path)
        
    os.makedirs(output_dir, exist_ok=True)
    
    session_groups = master_df.groupby('sessionId')
    feature_dfs = []
    
    print(f"[INFO] Extracting features across {session_groups.ngroups} sessions...")
    for session_id, group in session_groups:
        feat_df = process_session_features(group)
        feature_dfs.append(feat_df)
        
    result_df = pd.concat(feature_dfs, ignore_index=True)
    result_df = result_df.sort_values(by=['sessionId', 'timestamp']).reset_index(drop=True)
    
    parquet_out = os.path.join(output_dir, "features.parquet")
    csv_out = os.path.join(output_dir, "features.csv")
    
    result_df.to_parquet(parquet_out, index=False)
    result_df.to_csv(csv_out, index=False)
    
    print(f"[SUCCESS] Feature table generated: {result_df.shape[0]} rows, {result_df.shape[1]} columns")
    print(f"[SUCCESS] Saved to {parquet_out} and {csv_out}")
    
    return result_df

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Feature Table")
    parser.add_argument("--input", type=str, default="data/processed/v1/dataset.parquet")
    parser.add_argument("--output-dir", type=str, default="data/features/v1")
    args = parser.parse_args()
    
    build_features_table(input_path=args.input, output_dir=args.output_dir)
