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


def get_voice_service() -> VoiceService:
    """Return active VoiceService, syncing dynamic app configuration or test modes."""
    try:
        from flask import current_app
        if current_app and current_app.config:
            if current_app.config.get("TESTING", False):
                voice_service.dry_run = True
            elif "VOICE_ALERT_DRY_RUN" in current_app.config:
                voice_service.dry_run = bool(current_app.config.get("VOICE_ALERT_DRY_RUN"))
    except Exception:
        pass
    return voice_service


@voice_bp.route("/voice-alerts", methods=["GET"])
def voice_alerts_page():
    """Render the Voice Alerts configuration & audit log UI."""
    vs = get_voice_service()
    status = vs.get_config_status()
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
    vs = get_voice_service()
    status = vs.get_config_status()
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
    vs = get_voice_service()
    data = request.get_json(silent=True) or {}
    phone_override = data.get("phone")

    # Safety: Prohibit emergency numbers even in tests
    if phone_override and not vs.validate_destination_number(phone_override):
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

    result = vs.trigger_fire_voice_call(
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
    vs = get_voice_service()
    params = request.values.to_dict()
    if not params:
        params = request.get_json(silent=True) or {}

    logger.info(f"[VoiceCallback] Received Exotel callback: {params}")
    res = vs.handle_status_callback(params)
    return jsonify(res), 200


@voice_bp.route("/api/voice/exoml", methods=["GET", "POST"])
def exoml_voice_script():
    """Return dynamic ExoML (XML) voice prompt for Exotel TTS."""
    vs = get_voice_service()
    message = request.args.get("message")
    xml_content = vs.get_exoml_response(message)
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


@voice_bp.route("/api/voice/call-now", methods=["POST"])
def initiate_call_now():
    """Immediately initiate an outbound emergency voice call from dashboard."""
    vs = get_voice_service()
    data = request.get_json(silent=True) or {}
    phone_override = data.get("phone")
    reason = data.get("reason", "Manual Dashboard Operator Emergency Call")

    if phone_override and not vs.validate_destination_number(phone_override):
        return jsonify({
            "success": False,
            "error": "Invalid destination phone number. Emergency numbers are strictly prohibited.",
        }), 400

    manual_event = {
        "event_id": f"call_now_{int(request.date.timestamp()) if hasattr(request, 'date') and request.date else 1}",
        "entry_id": 0,
        "event_type": "MANUAL_OPERATOR_CALL",
        "severity": "CRITICAL",
        "temperature_c": data.get("temperature_c", 35.0),
        "raw_flame": data.get("raw_flame", 400.0),
        "raw_smoke": data.get("raw_smoke", 1),
        "servo_angle": data.get("servo_angle", 90),
        "fire_status": 1,
        "reason": reason,
    }

    result = vs.trigger_fire_voice_call(
        event=manual_event,
        recipient_override=phone_override,
        force=True,  # Manual call-now bypasses cooldown
    )

    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code


@voice_bp.route("/api/voice/terminate", methods=["POST"])
def terminate_call():
    """End or cancel an ongoing voice call."""
    vs = get_voice_service()
    data = request.get_json(silent=True) or {}
    call_id = data.get("call_id")

    result = vs.terminate_call(call_id=call_id)
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code


@voice_bp.route("/api/voice/incoming", methods=["GET", "POST"])
def incoming_voice_call():
    """Inbound voice call webhook endpoint for calls received by the Exotel virtual number.

    Plays automated spoken status report in ExoML XML format and logs the inquiry.
    """
    vs = get_voice_service()
    params = request.values.to_dict()
    if not params:
        params = request.get_json(silent=True) or {}

    logger.info(f"[InboundVoiceCall] Incoming call from {params.get('From', 'Unknown')}")
    exoml_response = vs.handle_incoming_call(params)
    return Response(exoml_response, mimetype="application/xml")


@voice_bp.route("/api/voice/contact", methods=["POST"])
def update_emergency_contact():
    """Update and persist the primary emergency contact phone number."""
    vs = get_voice_service()
    data = request.get_json(silent=True) or {}
    phone = data.get("phone")

    if not phone:
        return jsonify({"success": False, "error": "Phone number is required."}), 400

    result = vs.update_emergency_contact(phone)
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code


@voice_bp.route("/api/voice/send-sms", methods=["POST"])
def send_test_sms():
    """Dispatch an emergency or test SMS to the configured emergency contact."""
    vs = get_voice_service()
    data = request.get_json(silent=True) or {}
    phone_override = data.get("phone")

    event = {
        "event_id": "manual_sms_test",
        "temperature_c": data.get("temperature_c", 38.0),
        "servo_angle": data.get("servo_angle", 90),
    }

    result = vs.send_emergency_sms(event=event, recipient_override=phone_override)
    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code
