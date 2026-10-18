from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
from flask import Blueprint, jsonify, request

from config import Config
from services import BaselineService, DataService, ThingSpeakService

api_bp = Blueprint("api", __name__, url_prefix="/api")

ts_service = ThingSpeakService()
baseline_service = BaselineService()
data_service = DataService()


@api_bp.route("/health", methods=["GET"])
def health():
    """Health check endpoint indicating server and service readiness."""
    return jsonify({
        "status": "healthy",
        "service": "FireShield AI Flask Backend",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "thingspeak_configured": ts_service.is_configured(),
    })


@api_bp.route("/status", methods=["GET"])
def status():
    """Get system status, configuration state, and data freshness."""
    configured = ts_service.is_configured()
    latest_res = ts_service.fetch_latest_reading() if configured else None
    
    reading = latest_res.get("reading") if latest_res else None
    is_stale = reading.get("is_stale", True) if reading else True
    age_seconds = reading.get("age_seconds") if reading else None

    return jsonify({
        "success": True,
        "channel_id": Config.THINGSPEAK_CHANNEL_ID if Config.THINGSPEAK_CHANNEL_ID else None,
        "is_configured": configured,
        "connection_ok": latest_res.get("success", False) if latest_res else False,
        "has_data": reading is not None,
        "is_stale": is_stale,
        "age_seconds": age_seconds,
        "stale_threshold_seconds": Config.STALE_THRESHOLD_SECONDS,
        "error": latest_res.get("error") if latest_res else "Channel not configured",
    })


@api_bp.route("/readings/latest", methods=["GET"])
def latest_reading():
    """Get the latest normalized telemetry reading across the six fields."""
    force = request.args.get("refresh", "false").lower() in ("true", "1")
    res = ts_service.fetch_latest_reading(force_refresh=force)
    return jsonify(res), (200 if res.get("success") else 503)


@api_bp.route("/readings", methods=["GET"])
def readings():
    """Get recent normalized feeds with optional result limit."""
    limit_param = request.args.get("limit", "100")
    try:
        limit = min(int(limit_param), Config.MAX_HISTORY_RESULTS)
    except ValueError:
        limit = 100

    force = request.args.get("refresh", "false").lower() in ("true", "1")
    res = ts_service.fetch_feeds(results=limit, force_refresh=force)
    return jsonify(res), (200 if res.get("success") else 503)


@api_bp.route("/readings/history", methods=["GET"])
def history():
    """Bounded history retrieval by ISO start and end timestamps."""
    start = request.args.get("start")
    end = request.args.get("end")
    limit_param = request.args.get("limit", "200")
    try:
        limit = min(int(limit_param), Config.MAX_HISTORY_RESULTS)
    except ValueError:
        limit = 200

    force = request.args.get("refresh", "false").lower() in ("true", "1")
    res = ts_service.fetch_feeds(results=limit, start=start, end=end, force_refresh=force)
    return jsonify(res), (200 if res.get("success") else 503)


@api_bp.route("/baseline", methods=["GET"])
def get_baseline():
    """Retrieve saved room baseline parameters or compute on the fly."""
    saved = baseline_service.load_baseline()
    if saved:
        return jsonify(saved)

    # Compute baseline on available feeds
    feeds_res = ts_service.fetch_feeds(results=200)
    if not feeds_res.get("success") or not feeds_res.get("normalized_feeds"):
        return jsonify({
            "success": False,
            "error": "No baseline model saved, and no telemetry data available to compute one.",
        }), 404

    df = data_service.feeds_to_dataframe(feeds_res["normalized_feeds"])
    computed = baseline_service.compute_baseline(df)
    return jsonify(computed), (200 if computed.get("success") else 400)


@api_bp.route("/graphs/summary", methods=["GET"])
def graphs_summary():
    """Summary of time-series arrays for UI and graphs."""
    limit_param = request.args.get("limit", "100")
    try:
        limit = min(int(limit_param), Config.MAX_HISTORY_RESULTS)
    except ValueError:
        limit = 100

    res = ts_service.fetch_feeds(results=limit)
    if not res.get("success"):
        return jsonify(res), 503

    normalized = res.get("normalized_feeds", [])
    timestamps = [f.get("created_at") for f in normalized]
    flame_vals = [f.get("flame_raw") for f in normalized]
    smoke_vals = [f.get("smoke_status") for f in normalized]
    temp_vals = [f.get("temperature_c") for f in normalized]
    hum_vals = [f.get("humidity_pct") for f in normalized]
    servo_vals = [f.get("servo_angle") for f in normalized]
    fire_vals = [f.get("fire_status") for f in normalized]

    return jsonify({
        "success": True,
        "count": len(normalized),
        "timestamps": timestamps,
        "fields": {
            "flame": flame_vals,
            "smoke": smoke_vals,
            "temperature": temp_vals,
            "humidity": hum_vals,
            "servo_angle": servo_vals,
            "fire_status": fire_vals,
        },
    })
