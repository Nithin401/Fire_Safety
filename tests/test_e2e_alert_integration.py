import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
from tools.backend_server import app

def test_alert_system_flow():
    client = app.test_client()
    headers = {"X-API-Key": "fireshield_local_dev_key_2026"}

    # 1. Health check
    res = client.get("/health")
    assert res.status_code == 200, f"Health check failed: {res.data}"
    print("[PASS] Backend health check passed.")

    # 2. Check initial alerts
    res = client.get("/api/alerts")
    assert res.status_code == 200
    alerts = json.loads(res.data)
    assert len(alerts) >= 1
    print(f"[PASS] Initial alerts retrieved: {len(alerts)} alert(s).")

    # 3. Post fire telemetry
    fire_payload = {
        "device_id": "dev_e2e_001",
        "room_id": "Kitchen",
        "flame_raw": 120,
        "fire_angle": 84,
        "is_fire": True,
        "temp_c": 68.5,
        "humidity": 28.0,
        "gas_raw": 650,
        "smoke_raw": 720
    }
    res = client.post("/api/telemetry", json=fire_payload, headers=headers)
    assert res.status_code == 200, f"Telemetry post failed: {res.data}"
    telemetry_resp = json.loads(res.data)
    assert telemetry_resp["fireState"] == "FIRE"
    print(f"[PASS] Fire telemetry ingested. Risk Score: {telemetry_resp['riskScore']}%, State: {telemetry_resp['fireState']}.")

    # 4. Verify alert generated
    res = client.get("/api/alerts")
    assert res.status_code == 200
    alerts = json.loads(res.data)
    fire_alerts = [a for a in alerts if a.get("fireState") == "FIRE"]
    assert len(fire_alerts) >= 1, "No fire alert generated!"
    latest_alert = fire_alerts[0]
    safe_title = latest_alert['title'].encode('ascii', 'replace').decode('ascii')
    print(f"[PASS] Fire alert triggered: {safe_title} (ID: {latest_alert['id']})")
    assert latest_alert["fireAngle"] == 84
    assert latest_alert["severity"] == "critical"
    assert latest_alert["acknowledged"] is False

    # 5. Acknowledge alert
    alert_id = latest_alert["id"]
    res = client.post(f"/api/alerts/{alert_id}/ack")
    assert res.status_code == 200
    ack_data = json.loads(res.data)
    assert ack_data["status"] == "acknowledged"
    print(f"[PASS] Alert {alert_id} successfully acknowledged.")

    # 6. Verify acknowledged status persists
    res = client.get("/api/alerts")
    updated_alerts = json.loads(res.data)
    target_alert = next((a for a in updated_alerts if a["id"] == alert_id), None)
    assert target_alert is not None
    assert target_alert["acknowledged"] is True
    print(f"[PASS] Alert {alert_id} verified as acknowledged in backend state.")

    print("\n==========================================")
    print(" ALL END-TO-END ALERT TESTS PASSED!")
    print("==========================================")

if __name__ == "__main__":
    test_alert_system_flow()
