import pytest
import json
from tools.backend_server import app, INGESTION_API_KEY

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_health_endpoint(client):
    res = client.get('/health')
    assert res.status_code == 200
    data = res.get_json()
    assert data['status'] == 'online'
    assert 'ml_model_active' in data

def test_telemetry_unauthorized(client):
    payload = {"device_id": "dev_001", "flame_raw": 800}
    res = client.post('/api/telemetry', data=json.dumps(payload), content_type='application/json')
    assert res.status_code == 401

def test_telemetry_authorized_normal(client):
    payload = {
        "device_id": "dev_001",
        "room_id": "Kitchen",
        "flame_raw": 880,
        "temp_c": 24.5,
        "humidity": 55.0,
        "gas_raw": 120,
        "smoke_raw": 115,
        "fire_angle": 90,
        "is_fire": False
    }
    res = client.post('/api/telemetry', 
                      data=json.dumps(payload), 
                      content_type='application/json',
                      headers={'X-API-Key': INGESTION_API_KEY})
    assert res.status_code == 200
    data = res.get_json()
    assert data['status'] == 'success'
    assert data['fireState'] == 'SAFE'
    assert data['riskScore'] < 50.0

def test_telemetry_fire_transition_and_alert(client):
    payload = {
        "device_id": "dev_001",
        "room_id": "Kitchen",
        "flame_raw": 150,
        "temp_c": 75.0,
        "humidity": 35.0,
        "gas_raw": 650,
        "smoke_raw": 700,
        "fire_angle": 45,
        "is_fire": True
    }
    res = client.post('/api/telemetry', 
                      data=json.dumps(payload), 
                      content_type='application/json',
                      headers={'X-API-Key': INGESTION_API_KEY})
    assert res.status_code == 200
    data = res.get_json()
    assert data['fireState'] == 'FIRE'
    assert data['responseStatus'] == 'ACTIVE'
    
    # Check that alert feed has the alert
    alert_res = client.get('/api/alerts')
    assert alert_res.status_code == 200
    alerts = alert_res.get_json()
    assert len(alerts) > 0
    assert alerts[0]['fireState'] == 'FIRE'
    assert alerts[0]['fireAngle'] == 45
