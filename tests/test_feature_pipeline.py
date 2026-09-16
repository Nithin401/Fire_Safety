import os
import pytest
import pandas as pd
from ai.build_features import process_session_features
from ai.synthetic_data_generator import generate_session

def test_process_session_features():
    session_df = generate_session("TEST_FEAT_001", "FIRE", num_samples=60, seed=42)
    feat_df = process_session_features(session_df)
    
    assert len(feat_df) == 60
    assert "flame_baseline" in feat_df.columns
    assert "deviation_from_baseline" in feat_df.columns
    assert "z_score" in feat_df.columns
    assert "time_since_last_anomaly" in feat_df.columns
    assert "fusion_confidence_score" in feat_df.columns
    
    # Check that initial baseline is close to ambient
    assert feat_df["flame_baseline"].iloc[5] > 800
    
    # Time since last anomaly should be a float
    assert (feat_df["time_since_last_anomaly"] >= 0.0).all()
