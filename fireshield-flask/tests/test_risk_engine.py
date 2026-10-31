from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta
from services.risk_engine import RiskEngine, RiskState


@pytest.fixture
def baseline_fixture():
    return {
        "temperature_mean": 24.0,
        "temperature_std": 1.2,
        "humidity_mean": 50.0,
        "humidity_std": 5.0,
    }


@pytest.fixture
def engine():
    return RiskEngine()


def test_normal_reading_evaluates_to_normal(engine, baseline_fixture):
    reading = {
        "entry_id": 100,
        "temperature_c": 24.2,
        "humidity_pct": 51.0,
        "flame_raw": 1024.0,
        "smoke_status": 0,
        "fire_status": 0,
        "servo_angle": 90.0,
        "is_stale": False,
        "created_at": "2026-10-19T10:00:00Z",
    }
    res = engine.evaluate_reading(reading, baseline=baseline_fixture)
    assert res["state"] == RiskState.NORMAL
    assert res["should_alert"] is False
    assert res["severity"] == "NORMAL"


def test_hardware_fire_priority_with_field6(engine, baseline_fixture):
    reading = {
        "entry_id": 101,
        "temperature_c": 24.5,
        "humidity_pct": 50.0,
        "flame_raw": 1024.0,
        "smoke_status": 0,
        "fire_status": 1,  # Hardware rule fired!
        "servo_angle": 45.0,
        "is_stale": False,
        "created_at": "2026-10-19T10:00:16Z",
    }
    res = engine.evaluate_reading(reading, baseline=baseline_fixture)
    # Single unverified field6 trigger without dual confirmation or thermal drop flags suspect false alarm
    assert res["state"] == RiskState.SINGLE_SENSOR_SUSPECT
    assert res["should_alert"] is True
    assert res["should_phone_call"] is False
    assert res["severity"] == "WARNING"
    assert "field6=1" in res["reason"]


def test_single_flame_sensor_identified_as_suspected_false_alarm(engine, baseline_fixture):
    # Single optical flame without smoke or thermal confirmation is a suspected false alarm
    reading = {
        "entry_id": 102,
        "temperature_c": 24.0,
        "humidity_pct": 50.0,
        "flame_raw": 350.0,  # Below 600
        "smoke_status": 0,    # Smoke is NOT active
        "fire_status": 0,
        "servo_angle": 30.0,
        "is_stale": False,
        "created_at": "2026-10-19T10:00:32Z",
    }
    res = engine.evaluate_reading(reading, baseline=baseline_fixture)
    assert res["state"] == RiskState.SINGLE_SENSOR_SUSPECT
    assert res["should_alert"] is True
    assert res["should_phone_call"] is False
    assert res["severity"] == "WARNING"
    assert "Suspected False Alarm" in res["reason"]
    assert "Flame sensor" in res["reason"]


def test_single_smoke_sensor_identified_as_suspected_false_alarm(engine, baseline_fixture):
    # Smoke active without optical flame or thermal confirmation
    reading = {
        "entry_id": 103,
        "temperature_c": 24.0,
        "humidity_pct": 50.0,
        "flame_raw": 1024.0,  # Flame NOT detected
        "smoke_status": 1,     # Smoke active
        "fire_status": 0,
        "servo_angle": 90.0,
        "is_stale": False,
        "created_at": "2026-10-19T10:00:48Z",
    }
    res = engine.evaluate_reading(reading, baseline=baseline_fixture)
    assert res["state"] == RiskState.SINGLE_SENSOR_SUSPECT
    assert res["should_alert"] is True
    assert res["should_phone_call"] is False
    assert res["severity"] == "WARNING"
    assert "Suspected False Alarm" in res["reason"]
    assert "Smoke detector" in res["reason"]


def test_dual_sensor_activation_triggers_phone_alarm(engine, baseline_fixture):
    # Both flame AND smoke active simultaneously!
    reading = {
        "entry_id": 104,
        "temperature_c": 24.0,
        "humidity_pct": 50.0,
        "flame_raw": 380.0,  # Flame active!
        "smoke_status": 1,    # Smoke active!
        "fire_status": 1,
        "servo_angle": 90.0,
        "is_stale": False,
        "created_at": "2026-10-19T10:01:00Z",
    }
    res = engine.evaluate_reading(reading, baseline=baseline_fixture)
    assert res["state"] in (RiskState.DUAL_SENSOR_ALERT, RiskState.CONFIRMED_FIRE_ALERT)
    assert res["should_alert"] is True
    assert res["should_phone_call"] is True
    assert res["severity"] == "CRITICAL"
    assert res["metrics"]["dual_sensor_confirmed"] is True
    assert res["metrics"]["confidence_score"] >= 70


def test_multi_sensor_physical_verification_with_humidity_and_temp(engine, baseline_fixture):
    # Flame + Smoke + Temperature Rise + Combustion Humidity Drop!
    reading = {
        "entry_id": 105,
        "temperature_c": 32.0,  # +8C above baseline (temp rise)
        "humidity_pct": 28.0,   # Humidity decreased below 30% (combustion drying)
        "flame_raw": 320.0,     # Flame active
        "smoke_status": 1,      # Smoke active
        "fire_status": 1,
        "servo_angle": 45.0,
        "is_stale": False,
        "created_at": "2026-10-19T10:01:16Z",
    }
    res = engine.evaluate_reading(reading, baseline=baseline_fixture)
    assert res["state"] == RiskState.CONFIRMED_FIRE_ALERT
    assert res["should_alert"] is True
    assert res["should_phone_call"] is True
    assert res["severity"] == "CRITICAL"
    assert res["metrics"]["is_temp_rising"] is True
    assert res["metrics"]["is_hum_dropping"] is True
    assert res["metrics"]["confidence_score"] >= 90
    assert "Confirmed Fire" in res["reason"]


def test_baseline_anomaly_environmental_only(engine, baseline_fixture):
    # Baseline mean: 24.0, std: 1.2. 28.0 C is +4.0 C (> 3 sigma), flame & smoke normal
    reading = {
        "entry_id": 104,
        "temperature_c": 28.0,
        "humidity_pct": 48.0,
        "flame_raw": 1024.0,
        "smoke_status": 0,
        "fire_status": 0,
        "servo_angle": 90.0,
        "is_stale": False,
        "created_at": "2026-10-19T10:01:00Z",
    }
    res = engine.evaluate_reading(reading, baseline=baseline_fixture)
    assert res["state"] == RiskState.BASELINE_ANOMALY
    assert res["should_alert"] is True
    assert res["severity"] == "INFO"
    assert "Environmental baseline anomaly" in res["reason"]
    assert "Flame and smoke sensors remain clear" in res["reason"]


def test_early_warning_rapid_temp_rise(engine, baseline_fixture):
    # Consecutive readings showing rise > 1.5 C / min
    t0 = datetime(2026, 10, 19, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=16)
    t2 = t0 + timedelta(seconds=32)

    r1 = {
        "entry_id": 201,
        "temperature_c": 24.0,
        "humidity_pct": 50.0,
        "flame_raw": 1024.0,
        "smoke_status": 0,
        "fire_status": 0,
        "is_stale": False,
        "created_at": t0.isoformat(),
    }
    r2 = {
        "entry_id": 202,
        "temperature_c": 24.2,
        "humidity_pct": 49.0,
        "flame_raw": 1024.0,
        "smoke_status": 0,
        "fire_status": 0,
        "is_stale": False,
        "created_at": t1.isoformat(),
    }
    r3 = {
        "entry_id": 203,
        "temperature_c": 25.4,  # +1.4 C in 32s = +2.6 C/min (> 1.5 C/min threshold)
        "humidity_pct": 48.0,
        "flame_raw": 1024.0,
        "smoke_status": 0,
        "fire_status": 0,
        "is_stale": False,
        "created_at": t2.isoformat(),
    }

    engine.evaluate_reading(r1, baseline=baseline_fixture)
    engine.evaluate_reading(r2, baseline=baseline_fixture)
    res3 = engine.evaluate_reading(r3, baseline=baseline_fixture)

    assert res3["state"] == RiskState.EARLY_WARNING
    assert res3["should_alert"] is True
    assert res3["severity"] == "HIGH"
    assert "Rapid temperature rise" in res3["reason"]


def test_stale_reading_produces_data_fault(engine, baseline_fixture):
    reading = {
        "entry_id": 300,
        "temperature_c": 24.0,
        "humidity_pct": 50.0,
        "flame_raw": 1024.0,
        "smoke_status": 0,
        "fire_status": 0,
        "is_stale": True,
        "age_seconds": 120.0,
        "created_at": "2026-10-19T09:00:00Z",
    }
    res = engine.evaluate_reading(reading, baseline=baseline_fixture)
    assert res["state"] == RiskState.SENSOR_OR_DATA_FAULT
    assert res["severity"] == "WARNING"
    assert "stale" in res["reason"].lower()


def test_missing_fields_produces_data_fault(engine, baseline_fixture):
    reading = {
        "entry_id": 301,
        "temperature_c": None,  # Missing sensor read
        "humidity_pct": 50.0,
        "flame_raw": 1024.0,
        "smoke_status": 0,
        "fire_status": 0,
        "is_stale": False,
    }
    res = engine.evaluate_reading(reading, baseline=baseline_fixture)
    assert res["state"] == RiskState.SENSOR_OR_DATA_FAULT
    assert "Missing required sensor fields" in res["reason"]


def test_all_clear_transition_after_consecutive_normal_readings(engine, baseline_fixture):
    # 1. Trigger Fire
    fire_reading = {
        "entry_id": 401,
        "temperature_c": 35.0,
        "humidity_pct": 30.0,
        "flame_raw": 400.0,
        "smoke_status": 1,
        "fire_status": 1,
        "is_stale": False,
        "created_at": "2026-10-19T10:00:00Z",
    }
    res_fire = engine.evaluate_reading(fire_reading, baseline=baseline_fixture)
    assert res_fire["state"] in (RiskState.CONFIRMED_FIRE_ALERT, RiskState.DUAL_SENSOR_ALERT, RiskState.HARDWARE_FIRE_ALERT)

    # 2. Normal readings arrive: requires 3 consecutive normal
    normal_1 = {
        "entry_id": 402,
        "temperature_c": 24.0,
        "humidity_pct": 50.0,
        "flame_raw": 1024.0,
        "smoke_status": 0,
        "fire_status": 0,
        "is_stale": False,
        "created_at": "2026-10-19T10:00:16Z",
    }
    res1 = engine.evaluate_reading(normal_1, baseline=baseline_fixture)
    assert res1["state"] == RiskState.NORMAL
    assert res1["should_alert"] is False

    normal_2 = {
        "entry_id": 403,
        "temperature_c": 24.1,
        "humidity_pct": 50.0,
        "flame_raw": 1024.0,
        "smoke_status": 0,
        "fire_status": 0,
        "is_stale": False,
        "created_at": "2026-10-19T10:00:32Z",
    }
    res2 = engine.evaluate_reading(normal_2, baseline=baseline_fixture)
    assert res2["state"] == RiskState.NORMAL
    assert res2["should_alert"] is False

    normal_3 = {
        "entry_id": 404,
        "temperature_c": 24.0,
        "humidity_pct": 50.0,
        "flame_raw": 1024.0,
        "smoke_status": 0,
        "fire_status": 0,
        "is_stale": False,
        "created_at": "2026-10-19T10:00:48Z",
    }
    res3 = engine.evaluate_reading(normal_3, baseline=baseline_fixture)
    # 3rd consecutive normal reading generates the ALL_CLEAR event!
    assert res3["event_type"] == "ALL_CLEAR"
    assert res3["should_alert"] is True
    assert "All clear" in res3["reason"]
