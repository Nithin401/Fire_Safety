from __future__ import annotations

from datetime import datetime, timezone
from flask import Blueprint, Response, jsonify, render_template, request

from config import Config
from services import DataService, ThingSpeakService

export_bp = Blueprint("export", __name__)

ts_service = ThingSpeakService()
data_service = DataService()


@export_bp.route("/history")
def history_page():
    """Historical data inspection and CSV export page."""
    limit_param = request.args.get("limit", "100")
    fire_filter_param = request.args.get("fire_status")
    view_mode = request.args.get("view", "processed")  # 'raw' or 'processed'

    try:
        limit = min(int(limit_param), Config.MAX_HISTORY_RESULTS)
    except ValueError:
        limit = 100

    fire_filter = None
    if fire_filter_param in ("0", "1"):
        fire_filter = int(fire_filter_param)

    feeds_res = ts_service.fetch_feeds(results=limit)
    raw_feeds = feeds_res.get("raw_feeds", [])
    normalized_feeds = feeds_res.get("normalized_feeds", [])

    filtered_feeds = data_service.filter_feeds(normalized_feeds, fire_status_filter=fire_filter)

    return render_template(
        "history.html",
        feeds=filtered_feeds,
        raw_feeds=raw_feeds,
        view_mode=view_mode,
        limit=limit,
        fire_filter=fire_filter_param,
        is_configured=ts_service.is_configured(),
        error=feeds_res.get("error"),
    )


@export_bp.route("/export/raw.csv")
def export_raw_csv():
    """Download raw ThingSpeak CSV feed directly."""
    limit_param = request.args.get("limit", "500")
    try:
        limit = min(int(limit_param), Config.MAX_HISTORY_RESULTS)
    except ValueError:
        limit = 500

    feeds_res = ts_service.fetch_feeds(results=limit)
    csv_str = data_service.export_raw_csv_string(feeds_res.get("normalized_feeds", []))

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"fireshield_thingspeak_raw_{timestamp}.csv"

    return Response(
        csv_str,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@export_bp.route("/export/processed.csv")
def export_processed_csv():
    """Download normalized processed sensor dataset."""
    limit_param = request.args.get("limit", "500")
    try:
        limit = min(int(limit_param), Config.MAX_HISTORY_RESULTS)
    except ValueError:
        limit = 500

    feeds_res = ts_service.fetch_feeds(results=limit)
    csv_str = data_service.export_processed_csv_string(feeds_res.get("normalized_feeds", []))

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"fireshield_processed_{timestamp}.csv"

    return Response(
        csv_str,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@export_bp.route("/import/upload", methods=["POST"])
def upload_csv():
    """Upload an existing CSV file for offline inspection."""
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file uploaded."}), 400

    uploaded = request.files["file"]
    if not uploaded.filename or not uploaded.filename.endswith(".csv"):
        return jsonify({"success": False, "error": "Please upload a valid .csv file."}), 400

    content = uploaded.read().decode("utf-8", errors="ignore")
    parsed = data_service.parse_uploaded_csv(content)
    return jsonify(parsed)
