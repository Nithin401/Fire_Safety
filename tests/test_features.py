import pytest
import pandas as pd
import numpy as np
from ai.features import extract_features
from ai.synthetic_data_generator import generate_session

def test_feature_extraction_multi_channel():
    df = generate_session("TEST_MULTI_001", "FIRE", num_samples=30, seed=42)
    df_feat = extract_features(df, window_size=5)
    
    # Check that flame features exist
    assert 'rolling_mean' in df_feat.columns
    assert 'first_derivative' in df_feat.columns
    assert 'second_derivative' in df_feat.columns
    assert 'signal_variance' in df_feat.columns
    
    # Check that multi-channel features exist
    assert 'temp_rolling_mean' in df_feat.columns
    assert 'temp_roc' in df_feat.columns
    assert 'gas_rolling_mean' in df_feat.columns
    assert 'gas_roc' in df_feat.columns
    
    # Check fusion features
    assert 'flame_temp_correlation' in df_feat.columns
    assert 'fusion_confidence_score' in df_feat.columns
    assert 'false_alarm_suspect' in df_feat.columns

def test_sensor_fusion_fire_vs_false_alarm():
    # Fire session: flame drops, temp rises, gas rises
    df_fire = generate_session("TEST_FIRE", "FIRE", num_samples=60, seed=10)
    feat_fire = extract_features(df_fire)
    
    # During fire, fusion confidence should reach high levels (> 0.5)
    fire_rows = feat_fire[feat_fire['label'] == 'FIRE']
    assert fire_rows['fusion_confidence_score'].max() > 0.5
    
    # False alarm session: flame drops but temp/gas are ambient
    df_false = generate_session("TEST_FALSE", "FALSE_ALARM", num_samples=60, seed=20)
    feat_false = extract_features(df_false)
    
    # During false alarm spike, false_alarm_suspect should trigger
    false_rows = feat_false[feat_false['label'] == 'FALSE_ALARM']
    assert (false_rows['false_alarm_suspect'] == True).any()
