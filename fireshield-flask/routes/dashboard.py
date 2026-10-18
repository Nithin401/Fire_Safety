from __future__ import annotations

from flask import Blueprint, redirect, render_template, request, url_for

from config import Config
from services import BaselineService, DataService, ThingSpeakService

dashboard_bp = Blueprint("dashboard", __name__)

ts_service = ThingSpeakService()
baseline_service = BaselineService()
data_service = DataService()


@dashboard_bp.route("/")
def index():
    """Redirect to main overview dashboard."""
    return redirect(url_for("dashboard.overview"))


@dashboard_bp.route("/overview")
def overview():
    """Main overview dashboard showing live metrics, status badges, and staleness."""
    latest_res = ts_service.fetch_latest_reading()
    reading = latest_res.get("reading") if latest_res else None

    # Fetch recent feeds to show count
    feeds_res = ts_service.fetch_feeds(results=20)
    feed_count = len(feeds_res.get("normalized_feeds", []))

    # Evaluate baseline if available
    baseline = baseline_service.load_baseline()

    return render_template(
        "dashboard.html",
        reading=reading,
        feed_count=feed_count,
        is_configured=ts_service.is_configured(),
        channel_id=Config.THINGSPEAK_CHANNEL_ID,
        error=latest_res.get("error") if latest_res else None,
        baseline=baseline,
        stale_threshold=Config.STALE_THRESHOLD_SECONDS,
    )


@dashboard_bp.route("/graphs")
def graphs():
    """Graphs page rendering 6 separate sensor time-series."""
    limit_param = request.args.get("limit", "100")
    try:
        limit = min(int(limit_param), Config.MAX_HISTORY_RESULTS)
    except ValueError:
        limit = 100

    feeds_res = ts_service.fetch_feeds(results=limit)
    normalized = feeds_res.get("normalized_feeds", [])

    return render_template(
        "graphs.html",
        feeds=normalized,
        limit=limit,
        is_configured=ts_service.is_configured(),
        error=feeds_res.get("error"),
    )


@dashboard_bp.route("/baseline", methods=["GET", "POST"])
def baseline_page():
    """Room-temperature baseline analysis and visualization page."""
    baseline = baseline_service.load_baseline()
    message = None
    error = None

    if request.method == "POST":
        room_name = request.form.get("room_name", "Living Room")
        feeds_res = ts_service.fetch_feeds(results=Config.MAX_HISTORY_RESULTS)
        if not feeds_res.get("success") or not feeds_res.get("normalized_feeds"):
            error = "Could not fetch telemetry records from ThingSpeak to train baseline."
        else:
            df = data_service.feeds_to_dataframe(feeds_res["normalized_feeds"])
            train_res = baseline_service.compute_baseline(df, room_name=room_name)
            if train_res.get("success"):
                baseline = train_res
                message = f"Baseline successfully computed and saved for {room_name}."
            else:
                error = train_res.get("error")

    # If baseline exists, fetch recent feeds to plot with anomaly detection
    feeds_res = ts_service.fetch_feeds(results=100)
    normalized = feeds_res.get("normalized_feeds", [])

    return render_template(
        "baseline.html",
        baseline=baseline,
        feeds=normalized,
        message=message,
        error=error,
        is_configured=ts_service.is_configured(),
    )
