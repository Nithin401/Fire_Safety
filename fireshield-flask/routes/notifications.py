from __future__ import annotations

import logging
from typing import Any, Dict
from flask import Blueprint, jsonify, request

from config import Config
from services import (
    AlertService,
    BaselineService,
    EventStore,
    NtfyService,
    RiskEngine,
    ThingSpeakService,
    WebPushService,
)

logger = logging.getLogger(__name__)

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api")

event_store = EventStore()
ts_service = ThingSpeakService()
baseline_service = BaselineService()
risk_engine = RiskEngine()
ntfy_service = NtfyService()
webpush_service = WebPushService(event_store=event_store)
alert_service = AlertService(
    event_store=event_store,
    risk_engine=risk_engine,
    ntfy_service=ntfy_service,
    webpush_service=webpush_service
)


@notifications_bp.route("/notifications/vapid-public-key", methods=["GET"])
def get_vapid_public_key():
    """Return the base64url-encoded VAPID public key for browser push registration."""
    public_key = webpush_service.get_public_key()
    return jsonify({
        "success": bool(public_key),
        "public_key": public_key,
        "contact_email": Config.VAPID_CONTACT_EMAIL,
    })


@notifications_bp.route("/notifications/subscribe", methods=["POST"])
def subscribe_webpush():
    """Register or update a browser Web Push subscription."""
    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint")
    keys = data.get("keys", {})

    if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
        return jsonify({
            "success": False,
            "error": "Invalid subscription object: missing endpoint or cryptographic keys"
        }), 400

    user_agent = request.headers.get("User-Agent", "")
    success = webpush_service.subscribe(data, user_agent=user_agent)

    return jsonify({
        "success": success,
        "message": "Push subscription registered successfully" if success else "Failed to save subscription"
    }), 201 if success else 500


@notifications_bp.route("/notifications/unsubscribe", methods=["POST"])
def unsubscribe_webpush():
    """Remove a browser Web Push subscription."""
    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint")

    if not endpoint:
        return jsonify({"success": False, "error": "Missing endpoint parameter"}), 400

    success = webpush_service.unsubscribe(endpoint)
    return jsonify({
        "success": success,
        "message": "Subscription removed" if success else "Subscription not found"
    })


@notifications_bp.route("/notifications/status", methods=["GET"])
def notification_status():
    """Get status of notification channels (ntfy and Web Push)."""
    active_subs = event_store.get_active_push_subscriptions()
    public_key = webpush_service.get_public_key()

    return jsonify({
        "success": True,
        "channels": {
            "webpush": {
                "enabled": bool(public_key),
                "vapid_configured": bool(public_key),
                "active_subscriptions": len(active_subs),
                "contact_email": Config.VAPID_CONTACT_EMAIL,
            },
            "ntfy": {
                "enabled": bool(ntfy_service.default_topic),
                "base_url": ntfy_service.base_url,
                "topic": ntfy_service.default_topic,
                "public_url": ntfy_service.get_public_topic_url(),
                "protected": bool(ntfy_service.access_token),
            }
        }
    })


@notifications_bp.route("/notifications/test", methods=["POST"])
def send_test_notification():
    """Send a clearly labeled test notification across channels."""
    data = request.get_json(silent=True) or {}
    channels = data.get("channels")  # e.g. ["ntfy", "webpush"]

    res = alert_service.send_test_alert(channels=channels)
    return jsonify({
        "success": res.get("success", False),
        "channels": res.get("channels", {}),
        "message": "Test notification dispatched" if res.get("success") else "Test notification delivery failed",
    })


@notifications_bp.route("/events", methods=["GET"])
def get_events():
    """Get recent persistent risk events from SQLite store."""
    limit = min(int(request.args.get("limit", 50)), 200)
    event_type = request.args.get("event_type")

    events = event_store.get_recent_events(limit=limit, event_type=event_type)
    return jsonify({
        "success": True,
        "count": len(events),
        "events": events
    })


@notifications_bp.route("/events/<event_id>", methods=["GET"])
def get_event_detail(event_id: str):
    """Get single event detail by ID."""
    event = event_store.get_event_by_id(event_id)
    if not event:
        return jsonify({"success": False, "error": "Event not found"}), 404
    return jsonify({"success": True, "event": event})


@notifications_bp.route("/events/<event_id>/ack", methods=["POST"])
def acknowledge_event(event_id: str):
    """Acknowledge a risk event."""
    success = event_store.acknowledge_event(event_id)
    return jsonify({"success": success})


@notifications_bp.route("/risk/current", methods=["GET"])
def current_risk():
    """Evaluate current risk state based on latest telemetry reading."""
    reading_res = ts_service.fetch_latest_reading()
    reading = reading_res.get("reading") if reading_res.get("success") else None
    baseline = baseline_service.get_baseline()

    eval_res = risk_engine.evaluate_reading(reading, baseline=baseline)
    return jsonify({
        "success": True,
        "risk_state": eval_res.get("state"),
        "severity": eval_res.get("severity"),
        "reason": eval_res.get("reason"),
        "metrics": eval_res.get("metrics"),
        "has_baseline": bool(baseline),
        "baseline_summary": {
            "temp_mean": baseline.get("temperature_mean") if baseline else None,
            "temp_std": baseline.get("temperature_std") if baseline else None,
            "sample_count": baseline.get("sample_count") if baseline else 0,
        } if baseline else None,
    })
