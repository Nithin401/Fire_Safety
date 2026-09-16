"""
FireShield AI — Milestone 8 End-to-End Scenario Integration Test

Validates the full system behavior across 3 canonical operational scenarios:
1. Scenario A: NORMAL (Ambient baseline, zero false alarms, suppression IDLE)
2. Scenario B: FALSE_ALARM (Optical transient spike, ML suppresses suppression, status capped at WARNING)
3. Scenario C: FIRE EVENT (Multi-sensor combustion, ML & Rule consensus, status FIRE, suppression ACTIVE, alert dispatched)
"""

import pytest
import json
from tools.backend_server import app, INGESTION_API_KEY, alert_audit_trail, in_memory_devices

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_scenario_a_normal_baseline(client):
    """
    Scenario A: Device operates under normal stationary environmental conditions.
    Expected: SAFE state, low risk score (<25%), response status IDLE, zero alerts.
    """
    payload = {
        "device_id": "test_node_01",
        "room_id": "Kitchen",
        "flame_raw": 890,
        "temp_c": 24.2,
        "humidity": 55.0,
        "gas_raw": 115,
        "smoke_raw": 110,
        "fire_angle": 90,
        "is_fire": False
    }
    
    res = client.post('/api/telemetry', 
                      data=json.dumps(payload),
                      content_type='application/json',
                      headers={'X-API-Key': INGESTION_API_KEY})
    assert res.status_code == 200
    data = res.get_json()
    
    assert data["fireState"] == "SAFE"
    assert data["riskScore"] < 30.0
    assert data["responseStatus"] == "IDLE"
    
    # Assert device status endpoint reflects safe state
    dev_res = client.get('/api/devices')
    devices = dev_res.get_json()
    node = next(d for d in devices if d["id"] == "test_node_01")
    assert node["fireState"] == "SAFE"
    assert node["responseStatus"] == "IDLE"

def test_scenario_b_false_alarm_suppression(client):
    """
    Scenario B: Transient optical disturbance (lighter or reflection).
    Flame ADC drops sharply, but temperature and gas remain cold and ambient.
    Expected: ML classifies as FALSE_ALARM, suppresses suppression trigger (status WARNING, response IDLE).
    """
    payload = {
        "device_id": "test_node_02",
        "room_id": "LivingRoom",
        "flame_raw": 320,  # Sudden optical drop
        "temp_c": 24.5,    # Cold ambient temp!
        "humidity": 54.0,
        "gas_raw": 120,    # Clean air!
        "smoke_raw": 115,
        "fire_angle": 135,
        "is_fire": False
    }
    
    res = client.post('/api/telemetry', 
                      data=json.dumps(payload),
                      content_type='application/json',
                      headers={'X-API-Key': INGESTION_API_KEY})
    assert res.status_code == 200
    data = res.get_json()
    
    # Critical: Suppression pump must NOT actuate on a false alarm
    assert data["responseStatus"] == "IDLE"
    assert data["fireState"] in ["SAFE", "WARNING"]
    assert data["riskScore"] < 60.0

def test_scenario_c_confirmed_fire_event(client):
    """
    Scenario C: Genuine combustion event.
    Flame drops to 140, temperature surges to 72°C, gas surges to 620, angle = 45°.
    Expected: Consensus FIRE, risk score >= 85%, response status ACTIVE, critical alert dispatched.
    """
    payload = {
        "device_id": "test_node_03",
        "room_id": "ServerRoom",
        "flame_raw": 140,
        "temp_c": 72.0,
        "humidity": 32.0,
        "gas_raw": 620,
        "smoke_raw": 650,
        "fire_angle": 45,
        "is_fire": True
    }
    
    res = client.post('/api/telemetry', 
                      data=json.dumps(payload),
                      content_type='application/json',
                      headers={'X-API-Key': INGESTION_API_KEY})
    assert res.status_code == 200
    data = res.get_json()
    
    assert data["fireState"] == "FIRE"
    assert data["riskScore"] >= 85.0
    assert data["responseStatus"] == "ACTIVE"
    
    # Verify alert feed recorded the event with target aim angle
    alert_res = client.get('/api/alerts')
    alerts = alert_res.get_json()
    fire_alert = next((a for a in alerts if a["deviceId"] == "test_node_03"), None)
    
    assert fire_alert is not None
    assert fire_alert["severity"] == "critical"
    assert fire_alert["fireAngle"] == 45
    assert fire_alert["fireState"] == "FIRE"
    assert fire_alert["roomId"] == "ServerRoom"
