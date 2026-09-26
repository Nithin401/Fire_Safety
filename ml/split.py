"""
FireShield AI — Session-Separated Dataset Splitter

Performs strict group-wise train/val/test splits grouped by sessionId.
Prevents intra-session temporal data leakage.
"""

import os
import argparse
import pandas as pd
import numpy as np
from sklearn.model_selection import GroupShuffleSplit

def create_session_splits(features_path: str = "data/features/v1/features.parquet",
                          test_size: float = 0.2,
                          val_size: float = 0.15,
                          random_state: int = 42) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Splits features dataframe into train, val, test subsets by sessionId.
    """
    if features_path.endswith('.parquet'):
        df = pd.read_parquet(features_path)
    else:
        df = pd.read_csv(features_path)
        
    session_ids = df['sessionId'].unique()
    
    # Identify primary condition per session for balanced grouping
    session_labels = df.groupby('sessionId')['label'].agg(
        lambda s: 'FIRE' if 'FIRE' in s.values else ('FALSE_ALARM' if 'FALSE_ALARM' in s.values else 'NORMAL')
    )
    
    # First split: train+val vs test
    gss_test = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_state)
    train_val_idx, test_idx = next(gss_test.split(df, groups=df['sessionId']))
    
    train_val_df = df.iloc[train_val_idx].reset_index(drop=True)
    test_df = df.iloc[test_idx].reset_index(drop=True)
    
    # Second split: train vs val
    adj_val_size = val_size / (1.0 - test_size)
    gss_val = GroupShuffleSplit(n_splits=1, test_size=adj_val_size, random_state=random_state)
    train_idx, val_idx = next(gss_val.split(train_val_df, groups=train_val_df['sessionId']))
    
    train_df = train_val_df.iloc[train_idx].reset_index(drop=True)
    val_df = train_val_df.iloc[val_idx].reset_index(drop=True)
    
    print(f"[INFO] Dataset split summary:")
    print(f"  - Train: {len(train_df)} rows across {train_df['sessionId'].nunique()} sessions")
    print(f"  - Val:   {len(val_df)} rows across {val_df['sessionId'].nunique()} sessions")
    print(f"  - Test:  {len(test_df)} rows across {test_df['sessionId'].nunique()} sessions")
    
    # Assert zero session intersection
    train_sessions = set(train_df['sessionId'])
    val_sessions = set(val_df['sessionId'])
    test_sessions = set(test_df['sessionId'])
    
    assert len(train_sessions.intersection(test_sessions)) == 0, "Data leakage: session in train and test!"
    assert len(val_sessions.intersection(test_sessions)) == 0, "Data leakage: session in val and test!"
    assert len(train_sessions.intersection(val_sessions)) == 0, "Data leakage: session in train and val!"
    
    return train_df, val_df, test_df

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create Session-Separated Splits")
    parser.add_argument("--features", default="data/features/v1/features.parquet")
    parser.add_argument("--output-dir", default="data/features/v1/splits")
    args = parser.parse_args()
    
    train_df, val_df, test_df = create_session_splits(args.features)
    os.makedirs(args.output_dir, exist_ok=True)
    
    train_df.to_parquet(os.path.join(args.output_dir, "train.parquet"), index=False)
    val_df.to_parquet(os.path.join(args.output_dir, "val.parquet"), index=False)
    test_df.to_parquet(os.path.join(args.output_dir, "test.parquet"), index=False)
    print(f"[SUCCESS] Splits saved to {args.output_dir}")
