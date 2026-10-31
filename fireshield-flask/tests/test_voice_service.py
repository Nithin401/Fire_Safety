from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest
import requests

from config import Config
from services.event_store import EventStore
from services.voice_service import VoiceService
from services.alert_service import AlertService
from services.risk_engine import RiskEngine, RiskState
from app import create_app


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_events.db"
    return EventStore(db_path=db_file)


@pytest.fixture
def mock_config():
    class TestVoiceConfig(Config):
        EXOTEL_ACCOUNT_SID = "test_acc_sid"
        EXOTEL_API_KEY = "test_api_key"
        EXOTEL_API_TOKEN = "test_api_token"
        EXOTEL_CALLER_ID = "08047100000"
        EXOTEL_API_BASE_URL = "https://api.exotel.com"
        EXOTEL_APP_ID = "12345"
        FIRESHIELD_ALERT_PHONE = "+919876543210"
        VOICE_ALERT_ENABLED = True
        VOICE_ALERT_DRY_RUN = True
        VOICE_ALERT_COOLDOWN_SECONDS = 300
        PUBLIC_BASE_URL = "http://localhost:5000"
    return TestVoiceConfig


class TestVoiceServiceUnit:
    """Unit tests for VoiceService and Exotel provider adapter."""

    def test_number_normalization(self, temp_db, mock_config):
        service = VoiceService(config=mock_config, event_store=temp_db)

        # 10 digit Indian number -> +91
        assert service.normalize_phone("9876543210") == "+919876543210"
        # 11 digit with leading 0 -> +91
        assert service.normalize_phone("09876543210") == "+919876543210"
        # 12 digit with 91 prefix -> +91
        assert service.normalize_phone("919876543210") == "+919876543210"
        # Standard E.164
        assert service.normalize_phone("+919876543210") == "+919876543210"
        # Spaces and hyphens cleaned
        assert service.normalize_phone("+91 98765-43210") == "+919876543210"

    def test_prohibited_emergency_numbers(self, temp_db, mock_config):
        service = VoiceService(config=mock_config, event_store=temp_db)

        emergency_numbers = ["100", "101", "102", "108", "112", "911", "999", "+91100", "+91101"]
        for num in emergency_numbers:
            assert service.validate_destination_number(num) is False
            with pytest.raises(ValueError):
                service.normalize_phone(num)

    def test_credential_redaction_in_config_status(self, temp_db, mock_config):
        service = VoiceService(config=mock_config, event_store=temp_db)
        status = service.get_config_status()

        # Credentials must not be leaked
        assert "test_api_key" not in json.dumps(status)
        assert "test_api_token" not in json.dumps(status)
        assert status["has_account_sid"] is True
        assert status["has_api_key"] is True
        assert status["has_api_token"] is True
        assert status["masked_recipient"] == "+91****3210"
        assert status["provider"] == "exotel"

    def test_dry_run_mode_simulation(self, temp_db, mock_config):
        mock_config.VOICE_ALERT_DRY_RUN = True
        service = VoiceService(config=mock_config, event_store=temp_db)

        event = {
            "event_id": "evt_fire_001",
            "entry_id": 105,
            "event_type": "HARDWARE_FIRE_ALERT",
            "temperature_c": 45.2,
            "raw_flame": 300,
            "servo_angle": 45,
        }

        # Dry run should not make any HTTP calls
        with patch("requests.post") as mock_post:
            res = service.trigger_fire_voice_call(event)
            mock_post.assert_not_called()

        assert res["success"] is True
        assert res["status"] == "accepted"
        assert res["is_dry_run"] is True
        assert res["provider_call_sid"].startswith("dryrun_exo_")

        # Verify recorded in SQLite audit log
        call_record = temp_db.get_voice_call_by_id(res["call_id"])
        assert call_record is not None
        assert call_record["incident_id"] == "evt_fire_001"
        assert call_record["is_dry_run"] == 1
        assert call_record["status"] == "accepted"

    def test_cooldown_prevents_spamming_calls(self, temp_db, mock_config):
        service = VoiceService(config=mock_config, event_store=temp_db)

        event = {"event_id": "evt_fire_001", "entry_id": 101, "temperature_c": 50.0}

        # 1st call: succeeds in dry run
        res1 = service.trigger_fire_voice_call(event)
        assert res1["success"] is True

        # 2nd call immediately after: should be suppressed by cooldown
        res2 = service.trigger_fire_voice_call(event)
        assert res2["success"] is False
        assert res2["status"] == "cooldown_suppressed"

        # Force bypasses cooldown (for manual tests)
        res_forced = service.trigger_fire_voice_call(event, force=True)
        assert res_forced["success"] is True

    @patch("requests.post")
    def test_live_exotel_call_success(self, mock_post, temp_db, mock_config):
        mock_config.VOICE_ALERT_DRY_RUN = False
        service = VoiceService(config=mock_config, event_store=temp_db)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "Call": {
                "Sid": "exo_call_abc123",
                "Status": "in-progress",
                "To": "+919876543210",
                "CallerId": "08047100000",
                "DateCreated": "2026-10-28 17:00:00",
            }
        }
        mock_post.return_value = mock_resp

        event = {"event_id": "evt_live_01", "entry_id": 201, "temperature_c": 55.0}
        res = service.trigger_fire_voice_call(event)

        assert res["success"] is True
        assert res["status"] == "accepted"
        assert res["provider_call_sid"] == "exo_call_abc123"
        assert res["is_dry_run"] is False

        # Verify Basic Auth credentials and payload passed
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs["auth"] == ("test_api_key", "test_api_token")
        assert kwargs["data"]["From"] == "+919876543210"
        assert kwargs["data"]["CallerId"] == "08047100000"
        assert kwargs["data"]["CallType"] == "trans"

        # Verify recorded in DB
        db_call = temp_db.get_voice_call_by_id(res["call_id"])
        assert db_call["provider_call_sid"] == "exo_call_abc123"
        assert db_call["status"] == "accepted"

    @patch("requests.post")
    def test_exotel_api_error_handling(self, mock_post, temp_db, mock_config):
        mock_config.VOICE_ALERT_DRY_RUN = False
        service = VoiceService(config=mock_config, event_store=temp_db)

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {
            "RestException": {
                "Status": 401,
                "Message": "Authentication Failed: Invalid API Key or Token",
                "Code": 40101,
            }
        }
        mock_post.return_value = mock_resp

        event = {"event_id": "evt_auth_fail", "entry_id": 202}
        res = service.trigger_fire_voice_call(event)

        assert res["success"] is False
        assert res["status"] == "failed"
        assert "Authentication Failed" in res["error"]

        # Ensure failed status recorded
        call_record = temp_db.get_voice_call_by_id(res["call_id"])
        assert call_record["status"] == "failed"
        assert "Authentication Failed" in call_record["error_message"]

    @patch("requests.post", side_effect=requests.exceptions.Timeout("Connection timed out"))
    def test_exotel_timeout_handling(self, mock_post, temp_db, mock_config):
        mock_config.VOICE_ALERT_DRY_RUN = False
        service = VoiceService(config=mock_config, event_store=temp_db)

        event = {"event_id": "evt_timeout", "entry_id": 203}
        res = service.trigger_fire_voice_call(event)

        assert res["success"] is False
        assert res["status"] == "failed"
        assert "timed out" in res["error"]

    def test_webhook_status_callback_updates_call(self, temp_db, mock_config):
        service = VoiceService(config=mock_config, event_store=temp_db)

        # Pre-seed a call in 'accepted' status
        temp_db.record_voice_call(
            call_id="call_test_hook",
            incident_id="inc_001",
            recipient_phone="+919876543210",
            status="accepted",
            message_text="Alert text",
            provider_call_sid="exo_sid_999",
        )

        # Simulate Exotel terminal status callback
        callback_payload = {
            "CallSid": "exo_sid_999",
            "Status": "completed",
            "Duration": "18",
            "RecordingUrl": "https://s3.amazonaws.com/rec.mp3",
        }

        hook_res = service.handle_status_callback(callback_payload)
        assert hook_res["success"] is True
        assert hook_res["mapped_status"] == "completed"

        # Verify SQLite updated
        updated = temp_db.get_voice_call_by_id("call_test_hook")
        assert updated["status"] == "completed"
        assert updated["provider_response"]["Duration"] == "18"

    def test_exoml_generation(self, temp_db, mock_config):
        service = VoiceService(config=mock_config, event_store=temp_db)
        xml = service.get_exoml_response("Flame detected at kitchen zone.")

        assert '<?xml version="1.0" encoding="UTF-8"?>' in xml
        assert '<Say voice="female" language="en-IN">Flame detected at kitchen zone.</Say>' in xml
        assert "<Hangup/>" in xml


class TestVoiceAlertIntegration:
    """Integration test: RiskEngine + AlertService hardware fire detection triggers voice call."""

    def test_hardware_fire_reading_triggers_voice_call(self, temp_db, mock_config):
        mock_config.VOICE_ALERT_DRY_RUN = True
        voice_service = VoiceService(config=mock_config, event_store=temp_db)
        alert_service = AlertService(config=mock_config, event_store=temp_db, voice_service=voice_service)

        # Fire detected via field6 == 1 and flame < 600
        fire_reading = {
            "entry_id": 9999,
            "created_at": "2026-10-28T17:00:00Z",
            "flame_raw": 420.0,
            "smoke_status": 0,
            "temperature_c": 52.0,
            "humidity_pct": 30.0,
            "servo_angle": 90,
            "fire_status": 1,
            "is_stale": False,
        }

        result = alert_service.evaluate_and_alert(fire_reading)

        # Risk state must be confirmed fire
        assert result["state"] in (RiskState.CONFIRMED_FIRE_ALERT, RiskState.DUAL_SENSOR_ALERT, RiskState.HARDWARE_FIRE_ALERT)
        assert result["should_alert"] is True

        # Voice call must have been triggered and recorded
        assert "voice" in result["delivery"]
        voice_delivery = result["delivery"]["voice"]
        assert voice_delivery["success"] is True
        assert voice_delivery["status"] == "accepted"
        assert voice_delivery["is_dry_run"] is True

        # Verify persisted in voice_calls table
        calls = temp_db.get_recent_voice_calls(limit=5)
        assert len(calls) == 1
        assert calls[0]["entry_id"] == 9999
        assert calls[0]["status"] == "accepted"

    def test_single_sensor_trigger_does_not_dispatch_voice_call(self, temp_db, mock_config):
        mock_config.VOICE_ALERT_DRY_RUN = True
        voice_service = VoiceService(config=mock_config, event_store=temp_db)
        alert_service = AlertService(config=mock_config, event_store=temp_db, voice_service=voice_service)

        # Single optical flame reading without smoke, normal temp and humidity
        single_flame_reading = {
            "entry_id": 9998,
            "created_at": "2026-10-28T17:00:00Z",
            "flame_raw": 420.0,    # Only flame active (<600)
            "smoke_status": 0,      # Smoke is NOT active
            "temperature_c": 24.0,  # Normal room temperature
            "humidity_pct": 52.0,   # Normal room humidity
            "servo_angle": 90,
            "fire_status": 1,
            "is_stale": False,
        }

        result = alert_service.evaluate_and_alert(single_flame_reading)

        # State must be classified as SINGLE_SENSOR_SUSPECT
        assert result["state"] == RiskState.SINGLE_SENSOR_SUSPECT
        assert result["should_alert"] is True

        # Automated voice call must NOT be placed for suspected false alarms
        assert "voice" not in result["delivery"]
        assert result["metrics"]["should_phone_call"] is False


class TestVoiceRoutes:
    """Test Flask Web and API endpoints for Voice Alerts."""

    @pytest.fixture
    def client(self, mock_config):
        app = create_app(config_class=mock_config)
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_get_voice_status_api(self, client):
        res = client.get("/api/voice/status")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "config" in data
        assert data["config"]["provider"] == "exotel"

    def test_test_call_api_dry_run(self, client):
        res = client.post("/api/voice/test-call", json={})
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["status"] == "accepted"
        assert data["is_dry_run"] is True

    def test_test_call_prohibits_emergency_number(self, client):
        res = client.post("/api/voice/test-call", json={"phone": "101"})
        assert res.status_code == 400
        data = res.get_json()
        assert data["success"] is False
        assert "prohibited" in data["error"].lower()

    def test_exoml_endpoint(self, client):
        res = client.get("/api/voice/exoml?message=Test+alert")
        assert res.status_code == 200
        assert res.mimetype == "application/xml"
        assert b"<Response>" in res.data
        assert b"Test alert" in res.data

    def test_voice_alerts_page_renders(self, client):
        res = client.get("/voice-alerts")
        assert res.status_code == 200
        assert b"Automated Outbound Voice Alerts" in res.data
        assert b"Exotel Credentials Checklist" in res.data
