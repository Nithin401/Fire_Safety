import pytest
import numpy as np
from ai.risk_engine_ml import HybridRiskEngine

def test_hybrid_risk_engine_rule_fallback_when_disabled():
    engine = HybridRiskEngine(use_ml=False)
    # Ambient values
    score, state, meta = engine.evaluate_hybrid_risk({'deviation_from_baseline': 0, 'first_derivative': 0, 'anomaly_flag_zscore': 0})
    assert score < 30
    assert state == "SAFE"
    assert meta['ml_active'] is False

def test_hybrid_risk_engine_with_fire_features():
    engine = HybridRiskEngine(model_path="ml/models/v1/model.pkl", use_ml=True)
    
    # Strong fire features: drop in flame, rise in temp, rise in gas, high fusion confidence
    fire_features = {
        'rolling_mean': 200.0,
        'signal_variance': 50.0,
        'first_derivative': -150.0,
        'second_derivative': -20.0,
        'deviation_from_baseline': -650.0,
        'temp_rolling_mean': 65.0,
        'temp_roc': 2.5,
        'temp_accel': 0.5,
        'temp_deviation': 40.0,
        'gas_rolling_mean': 550.0,
        'gas_roc': 25.0,
        'gas_deviation': 400.0,
        'smoke_rolling_mean': 600.0,
        'smoke_roc': 30.0,
        'flame_temp_correlation': 0.85,
        'gas_smoke_index': 0.90,
        'fusion_confidence_score': 0.95,
        'z_score': -8.0,
        'time_since_last_anomaly': 0.0,
        'anomaly_flag_zscore': 1
    }
    
    score, state, meta = engine.evaluate_hybrid_risk(fire_features)
    assert state == "FIRE"
    assert score >= 85.0
    if meta['ml_active']:
        assert meta['ml_prediction'] == "FIRE"

def test_hybrid_risk_engine_false_alarm_suppression():
    engine = HybridRiskEngine(model_path="ml/models/v1/model.pkl", use_ml=True)
    
    # False alarm features: flame dropped briefly, but temp and gas are flat ambient
    false_alarm_features = {
        'rolling_mean': 400.0,
        'signal_variance': 200.0,
        'first_derivative': -400.0,
        'second_derivative': 100.0,
        'deviation_from_baseline': -450.0,
        'temp_rolling_mean': 24.5,
        'temp_roc': 0.0,
        'temp_accel': 0.0,
        'temp_deviation': 0.0,
        'gas_rolling_mean': 120.0,
        'gas_roc': 0.0,
        'gas_deviation': 0.0,
        'smoke_rolling_mean': 115.0,
        'smoke_roc': 0.0,
        'flame_temp_correlation': 0.0,
        'gas_smoke_index': 0.0,
        'fusion_confidence_score': 0.35,
        'z_score': -4.5,
        'time_since_last_anomaly': 0.0,
        'anomaly_flag_zscore': 1
    }
    
    score, state, meta = engine.evaluate_hybrid_risk(false_alarm_features)
    # ML should suppress false alarm to WARNING rather than activating full suppression
    if meta['ml_active'] and meta['ml_prediction'] == "FALSE_ALARM":
        assert state == "WARNING"
        assert score <= 50.0
