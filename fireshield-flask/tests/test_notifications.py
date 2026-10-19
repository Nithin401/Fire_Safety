from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile

from services.event_store import EventStore
from services.ntfy_service import NtfyService
from services.webpush_service import WebPushService
from services.alert_service import AlertService
from app import create_app


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_events.db"
    return EventStore(db_path=db_file)


def test_event_store_record_and_retrieve(temp_db):
    event = temp_db.record_event(
        event_type="HARDWARE_FIRE_ALERT",
        severity="CRITICAL",
        reason="Flame detected on A0",
        entry_id=555,
        raw_flame=320.0,
        raw_smoke=0,
        temperature_c=31.5,
        humidity_pct=45.0,
        servo_angle=90.0,
        fire_status=1,
    )
    assert event["event_id"].startswith("evt_")
    assert event["event_type"] == "HARDWARE_FIRE_ALERT"
    assert event["raw_flame"] == 320.0
    assert event["acknowledged"] == 0

    # Retrieve by ID
    fetched = temp_db.get_event_by_id(event["event_id"])
    assert fetched is not None
    assert fetched["entry_id"] == 555

    # Acknowledge
    assert temp_db.acknowledge_event(event["event_id"]) is True
    assert temp_db.get_event_by_id(event["event_id"])["acknowledged"] == 1


def test_outbox_queue_and_retry_backoff(temp_db):
    outbox_id = temp_db.enqueue_notification(
        event_id="evt_test_123",
        channel="ntfy",
        payload={"msg": "fire"},
        recipient_id="test_topic"
    )
    assert outbox_id > 0

    pending = temp_db.get_pending_outbox_items()
    assert len(pending) == 1
    assert pending[0]["id"] == outbox_id
    assert pending[0]["attempts"] == 0

    # Simulate transient failure
    temp_db.mark_outbox_failed(outbox_id, "Network timeout 504", permanent=False)
    
    with temp_db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT attempts, status FROM notification_outbox WHERE id = ?", (outbox_id,))
        row = cursor.fetchone()
        assert row["attempts"] == 1
        assert row["status"] == "pending"

    # Mark delivered
    temp_db.mark_outbox_delivered(outbox_id)
    with temp_db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status, delivered_at FROM notification_outbox WHERE id = ?", (outbox_id,))
        row = cursor.fetchone()
        assert row["status"] == "delivered"
        assert row["delivered_at"] is not None


def test_webpush_subscription_management(temp_db):
    sub_endpoint = "https://fcm.googleapis.com/fcm/send/sample_token_xyz"
    saved = temp_db.save_push_subscription(
        endpoint=sub_endpoint,
        p256dh="sample_p256dh_key",
        auth="sample_auth_key",
        user_agent="Mozilla/5.0"
    )
    assert saved is True

    subs = temp_db.get_active_push_subscriptions()
    assert len(subs) == 1
    assert subs[0]["endpoint"] == sub_endpoint

    # Deactivate / Unsubscribe
    temp_db.deactivate_push_subscription(sub_endpoint)
    assert len(temp_db.get_active_push_subscriptions()) == 0


def test_ntfy_payload_mapping():
    ntfy = NtfyService()
    # Ensure ASCII titles (no unicode characters in HTTP headers)
    p_fire, tag_fire, title_fire = ntfy._map_event_presentation("HARDWARE_FIRE_ALERT", "CRITICAL")
    assert p_fire == 5
    assert "fire" in tag_fire
    assert "FIRE ALERT" in title_fire
    title_fire.encode("latin-1")  # Must not raise UnicodeEncodeError

    p_warn, tag_warn, title_warn = ntfy._map_event_presentation("EARLY_WARNING", "HIGH")
    assert p_warn == 4
    title_warn.encode("latin-1")


@patch("requests.post")
def test_ntfy_publish_success(mock_post):
    mock_post.return_value.status_code = 200
    mock_post.return_value.text = "ok"

    ntfy = NtfyService()
    res = ntfy.publish_event({
        "event_id": "evt_test",
        "event_type": "HARDWARE_FIRE_ALERT",
        "severity": "CRITICAL",
        "reason": "Test alarm",
        "temperature_c": 33.0,
    }, topic="test_fireshield")

    assert res["success"] is True
    assert mock_post.called
    args, kwargs = mock_post.call_args
    assert "Priority" in kwargs["headers"]
    assert kwargs["headers"]["Priority"] == "5"


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_api_vapid_public_key_schema(client):
    res = client.get("/api/notifications/vapid-public-key")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert len(data["public_key"]) > 40


def test_api_notification_status_schema(client):
    res = client.get("/api/notifications/status")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "ntfy" in data["channels"]
    assert "webpush" in data["channels"]
    assert data["channels"]["ntfy"]["topic"].startswith("fireshield_alerts_")


def test_api_events_schema(client):
    res = client.get("/api/events")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert isinstance(data["events"], list)


def test_api_current_risk_schema(client):
    res = client.get("/api/risk/current")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "risk_state" in data
    assert "metrics" in data
