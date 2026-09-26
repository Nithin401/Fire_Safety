import pytest
import pandas as pd
import numpy as np
from ai.data_validation import validate_dataframe
from ai.build_processed_dataset import build_processed_dataset

def test_validate_valid_dataframe():
    df = pd.DataFrame({
        "timestamp": ["2026-09-16T10:00:00Z", "2026-09-16T10:00:01Z"],
        "sessionId": ["S1", "S1"],
        "deviceId": ["D1", "D1"],
        "roomId": ["R1", "R1"],
        "flameRaw": [850, 845],
        "tempC": [24.5, 24.6],
        "humidity": [55.0, 55.1],
        "gasRaw": [120, 122],
        "smokeRaw": [115, 118],
        "fireAngle": [90, 90],
        "label": ["NORMAL", "NORMAL"],
        "distance_cm": [0, 0],
        "data_source": ["synthetic", "synthetic"]
    })
    valid, errors = validate_dataframe(df)
    assert valid is True
    assert len(errors) == 0

def test_validate_out_of_bounds_adc():
    df = pd.DataFrame({
        "timestamp": ["2026-09-16T10:00:00Z"],
        "sessionId": ["S1"],
        "deviceId": ["D1"],
        "roomId": ["R1"],
        "flameRaw": [1500], # Out of 0-1023
        "tempC": [24.5],
        "humidity": [55.0],
        "gasRaw": [120],
        "smokeRaw": [115],
        "fireAngle": [90],
        "label": ["NORMAL"],
        "distance_cm": [0],
        "data_source": ["synthetic"]
    })
    valid, errors = validate_dataframe(df)
    assert valid is False
    assert any("flameRaw out of 0-1023" in e for e in errors)

def test_validate_non_monotonic_timestamps():
    df = pd.DataFrame({
        "timestamp": ["2026-09-16T10:00:05Z", "2026-09-16T10:00:01Z"], # Decreasing
        "sessionId": ["S1", "S1"],
        "deviceId": ["D1", "D1"],
        "roomId": ["R1", "R1"],
        "flameRaw": [850, 845],
        "tempC": [24.5, 24.6],
        "humidity": [55.0, 55.1],
        "gasRaw": [120, 122],
        "smokeRaw": [115, 118],
        "fireAngle": [90, 90],
        "label": ["NORMAL", "NORMAL"],
        "distance_cm": [0, 0],
        "data_source": ["synthetic", "synthetic"]
    })
    valid, errors = validate_dataframe(df)
    assert valid is False
    assert any("Timestamps are not strictly non-decreasing" in e for e in errors)
