from __future__ import annotations

import os
import sys
from pathlib import Path

# Add fireshield-flask to Python path
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

from config import Config
from routes import api_bp, dashboard_bp, export_bp, models_bp


def create_app(config_class: type[Config] = Config) -> Flask:
    """Application factory for FireShield AI Flask backend."""
    app = Flask(
        __name__,
        template_folder=str(CURRENT_DIR / "templates"),
        static_folder=str(CURRENT_DIR / "static"),
    )
    app.config.from_object(config_class)

    # Initialize restricted CORS for Flutter web / mobile dev origins (supports any localhost/127.0.0.1 port)
    allowed_origins = [
        r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    ] + config_class.CORS_ALLOWED_ORIGINS
    CORS(
        app,
        resources={r"/api/*": {"origins": allowed_origins}},
        supports_credentials=True,
    )

    # Register blueprints
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(models_bp)

    # Ensure required data directories exist
    Config.DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    Config.DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    Config.DATA_LABELS_DIR.mkdir(parents=True, exist_ok=True)
    Config.DATA_MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # Error Handlers
    @app.errorhandler(404)
    def not_found_error(error):
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "error": "Endpoint not found", "status_code": 404}), 404
        return render_template("base.html", content="<div class='card'><h2>404 - Page Not Found</h2></div>"), 404

    @app.errorhandler(500)
    def internal_error(error):
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "error": "Internal server error", "status_code": 500}), 500
        return render_template("base.html", content="<div class='card'><h2>500 - Internal Server Error</h2></div>"), 500

    return app


app = create_app()

if __name__ == "__main__":
    host = Config.FLASK_HOST
    port = Config.FLASK_PORT
    debug = Config.DEBUG
    print(f"[FireShield AI] Flask running on http://{host}:{port} (Debug: {debug})")
    print(f"[ThingSpeak] Configured Channel: {Config.THINGSPEAK_CHANNEL_ID or 'Not Set'}")
    app.run(host=host, port=port, debug=debug)
