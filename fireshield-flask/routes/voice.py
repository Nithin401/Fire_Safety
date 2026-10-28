from __future__ import annotations

import logging
from flask import Blueprint, Response, jsonify, render_template, request

from config import Config
from services.event_store import EventStore
from services.voice_service import VoiceService

logger = logging.getLogger(__name__)

voice_bp = Blueprint("voice", __name__)
event_store = EventStore()
voice_service = VoiceService(config=Config, event_store=event_store)


@voice_bp.route("/voice-alerts", methods=["GET"])
def voice_alerts_page():
    """Render the Voice Alerts configuration & audit log UI."""
    status = voice_service.get_config_status()
    calls = event_store.get_recent_voice_calls(limit=30)
    return render_template(
        "voice_alerts.html",
        status=status,
        calls=calls,
        cooldown_seconds=Config.VOICE_ALERT_COOLDOWN_SECONDS,
    )


@voice_bp.route("/api/voice/status", methods=["GET"])
def get_voice_status():
    """Return sanitized Exotel configuration status, dry-run state, and recent calls."""
    status = voice_service.get_config_status()
    calls = event_store.get_recent_voice_calls(limit=10)
    return jsonify({
        "success": True,
        "config": status,
        "recent_calls": calls,
    })


@voice_bp.route("/api/voice/test-call", methods=["POST"])
def trigger_test_call():
    """Trigger an authorized test call to verify telephony configuration.

    Supports dry-run testing or live calls when explicitly configured.
    """
    data = request.get_json(silent=True) or {}
    phone_override = data.get("phone")

    # Safety: Prohibit emergency numbers even in tests
    if phone_override and not voice_service.validate_destination_number(phone_override):
        return jsonify({
            "success": False,
            "error": "Invalid destination phone number. Emergency numbers are strictly prohibited.",
        }), 400

    test_event = {
        "event_id": "test_manual_call",
        "entry_id": 0,
        "event_type": "TEST_VOICE_ALERT",
        "severity": "CRITICAL",
        "temperature_c": 38.5,
        "raw_flame": 450.0,
        "raw_smoke": 0,
        "servo_angle": 90,
        "fire_status": 1,
    }

    result = voice_service.trigger_fire_voice_call(
        event=test_event,
        recipient_override=phone_override,
        force=True,  # Test calls bypass the 300s cooldown
    )

    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code


@voice_bp.route("/api/voice/callback", methods=["POST", "GET"])
def voice_status_callback():
    """Webhook callback endpoint for Exotel call progress updates.

    Exotel posts CallSid, Status (queued, in-progress, completed, failed, busy, no-answer),
    RecordingUrl, Duration, etc.
    """
    params = request.values.to_dict()
    if not params:
        params = request.get_json(silent=True) or {}

    logger.info(f"[VoiceCallback] Received Exotel callback: {params}")
    res = voice_service.handle_status_callback(params)
    return jsonify(res), 200


@voice_bp.route("/api/voice/exoml", methods=["GET", "POST"])
def exoml_voice_script():
    """Return dynamic ExoML (XML) voice prompt for Exotel TTS."""
    message = request.args.get("message")
    xml_content = voice_service.get_exoml_response(message)
    return Response(xml_content, mimetype="application/xml")


@voice_bp.route("/api/voice/calls", methods=["GET"])
def get_voice_calls():
    """Return historical voice calls with masked recipient phone numbers."""
    limit = min(int(request.args.get("limit", 50)), 100)
    calls = event_store.get_recent_voice_calls(limit=limit)
    return jsonify({
        "success": True,
        "count": len(calls),
        "calls": calls,
    })
