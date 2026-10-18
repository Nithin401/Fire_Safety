from __future__ import annotations

import json
from flask import Blueprint, jsonify, render_template, request

from config import Config
from services import DataService, MLService, ThingSpeakService

models_bp = Blueprint("models", __name__)

ml_service = MLService()
ts_service = ThingSpeakService()
data_service = DataService()


@models_bp.route("/ml-studio", methods=["GET", "POST"])
def ml_studio():
    """ML experimentation studio with honest data readiness evaluation."""
    registry = []
    if ml_service.MODEL_REGISTRY_PATH.exists():
        try:
            registry = json.loads(ml_service.MODEL_REGISTRY_PATH.read_text(encoding="utf-8"))
        except Exception:
            registry = []

    # Get recent feeds to inspect data readiness
    feeds_res = ts_service.fetch_feeds(results=200)
    feeds = feeds_res.get("normalized_feeds", [])
    df = data_service.feeds_to_dataframe(feeds)
    data_summary = ml_service.analyze_dataset_for_ml(df)

    training_result = None
    error = None

    if request.method == "POST":
        action = request.form.get("action")
        if action == "train":
            model_type = request.form.get("model_type", "random_forest")
            features = request.form.getlist("features")
            label_col = request.form.get("label_col", "verified_label")

            training_result = ml_service.train_classifier(
                df=df,
                feature_cols=features,
                label_col=label_col,
                model_type=model_type,
            )
            if not training_result.get("success"):
                error = training_result.get("error")
            else:
                # Refresh registry
                try:
                    registry = json.loads(ml_service.MODEL_REGISTRY_PATH.read_text(encoding="utf-8"))
                except Exception:
                    pass

    return render_template(
        "ml_studio.html",
        data_summary=data_summary,
        models=registry,
        training_result=training_result,
        error=error,
        feed_count=len(feeds),
        is_configured=ts_service.is_configured(),
    )
