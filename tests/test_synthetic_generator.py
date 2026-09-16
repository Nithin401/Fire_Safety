import os
import pytest
import pandas as pd
from ai.synthetic_data_generator import generate_session

def test_generate_session_normal():
    df = generate_session("TEST_NORM_001", "NORMAL", num_samples=50, seed=123)
    assert len(df) == 50
    assert (df["label"] == "NORMAL").all()
    assert (df["data_source"] == "synthetic").all()
    assert (df["flameRaw"] >= 0).all() and (df["flameRaw"] <= 1023).all()
    assert (df["tempC"] >= 20.0).all() and (df["tempC"] <= 35.0).all()

def test_generate_session_fire():
    df = generate_session("TEST_FIRE_001", "FIRE", num_samples=60, fire_angle=45, seed=456)
    assert len(df) == 60
    assert "FIRE" in df["label"].values
    assert "NORMAL" in df["label"].values
    fire_rows = df[df["label"] == "FIRE"]
    assert (fire_rows["fireAngle"] == 45).all()
    # Flame raw should drop significantly during fire
    assert fire_rows["flameRaw"].mean() < df[df["label"] == "NORMAL"]["flameRaw"].mean()
    # Temperature should rise significantly
    assert fire_rows["tempC"].mean() > df[df["label"] == "NORMAL"]["tempC"].mean()

def test_generate_session_false_alarm():
    df = generate_session("TEST_FALSE_001", "FALSE_ALARM", num_samples=50, seed=789)
    assert len(df) == 50
    assert "FALSE_ALARM" in df["label"].values
