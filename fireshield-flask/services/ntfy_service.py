from __future__ import annotations

import logging
from typing import Any, Dict, Optional
import requests

from config import Config

logger = logging.getLogger(__name__)


class NtfyService:
    """Mobile push notification service via ntfy (HTTP/HTTPS publishing, zero Firebase)."""

    def __init__(self, config=None):
        self.config = config or Config
        self.base_url = self.config.NTFY_BASE_URL.rstrip("/")
        self.default_topic = self.config.NTFY_TOPIC
        self.access_token = getattr(self.config, "NTFY_ACCESS_TOKEN", "").strip()

    def publish_event(
        self,
        event: Dict[str, Any],
        topic: Optional[str] = None,
        click_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Publish a risk event to the configured ntfy topic."""
        target_topic = topic or self.default_topic
        if not target_topic:
            return {
                "success": False,
                "error": "No ntfy topic configured. Set NTFY_TOPIC in environment.",
                "status_code": 0,
            }

        url = f"{self.base_url}/{target_topic}"
        event_type = event.get("event_type", "UNKNOWN")
        severity = event.get("severity", "INFO")
        reason = event.get("reason", "Hazard evaluation update")
        temp = event.get("temperature_c")
        hum = event.get("humidity_pct")
        flame = event.get("raw_flame")
        smoke = event.get("raw_smoke")

        # Map to ntfy priority and emoji tags
        priority, tags, title = self._map_event_presentation(event_type, severity)

        # Construct concise message body
        metrics = []
        if temp is not None:
            metrics.append(f"Temp: {temp:.1f}°C")
        if hum is not None:
            metrics.append(f"Hum: {hum:.1f}%")
        if flame is not None:
            metrics.append(f"Flame A0: {flame:.0f}")
        if smoke is not None:
            metrics.append(f"Smoke DO: {'DETECTED' if smoke == 1 else 'Clear'}")

        metrics_line = " | ".join(metrics)
        body = f"{reason}\n{metrics_line}" if metrics_line else reason

        headers = {
            "Title": title,
            "Priority": str(priority),
            "Tags": tags,
        }

        # Add click URL to open dashboard on notification click
        action_url = click_url or f"http://{self.config.FLASK_HOST if self.config.FLASK_HOST != '0.0.0.0' else '127.0.0.1'}:{self.config.FLASK_PORT}"
        headers["Click"] = action_url

        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        try:
            response = requests.post(
                url,
                data=body.encode("utf-8"),
                headers=headers,
                timeout=10.0
            )

            if response.status_code in (200, 201, 202):
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "topic": target_topic,
                    "event_id": event.get("event_id"),
                }
            else:
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": f"ntfy HTTP {response.status_code}: {response.text[:200]}",
                    "topic": target_topic,
                }
        except requests.exceptions.RequestException as e:
            logger.warning(f"ntfy delivery failed for topic {target_topic}: {e}")
            return {
                "success": False,
                "status_code": 0,
                "error": str(e),
                "topic": target_topic,
            }

    def send_test_notification(self, topic: Optional[str] = None) -> Dict[str, Any]:
        """Send a test notification to verify mobile receipt."""
        test_event = {
            "event_id": "test_ping",
            "event_type": "TEST_NOTIFICATION",
            "severity": "INFO",
            "reason": "Test alert: FireShield AI background notification channel verified.",
            "temperature_c": 26.5,
            "humidity_pct": 52.0,
            "raw_flame": 1024.0,
            "raw_smoke": 0,
        }
        return self.publish_event(test_event, topic=topic)

    def _map_event_presentation(self, event_type: str, severity: str) -> tuple[int, str, str]:
        if event_type == "HARDWARE_FIRE_ALERT":
            return (5, "fire,warning,rotating_light", "FIRE ALERT: FireShield AI")
        elif event_type == "EARLY_WARNING":
            return (4, "warning,thermometer", "Early Warning: Elevated Fire Risk")
        elif event_type == "BASELINE_ANOMALY":
            return (3, "chart_with_upwards_trend", "Room Baseline Anomaly")
        elif event_type == "SENSOR_OR_DATA_FAULT":
            return (2, "wrench,warning", "Sensor or Telemetry Fault")
        elif event_type == "ALL_CLEAR":
            return (3, "white_check_mark,green_heart", "All Clear: Normal Conditions Restored")
        elif event_type == "TEST_NOTIFICATION":
            return (3, "bell,shield", "FireShield AI: Test Notification")
        else:
            return (3, "bell", "FireShield AI Notification")

    def get_public_topic_url(self) -> str:
        """Get the URL where the user can subscribe in their mobile browser or ntfy app."""
        return f"{self.base_url}/{self.default_topic}"
