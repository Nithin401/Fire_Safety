from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid
from pywebpush import webpush, WebPushException

from config import Config
from services.event_store import EventStore

logger = logging.getLogger(__name__)


class WebPushService:
    """Standard Web Push service using VAPID and pywebpush."""

    def __init__(self, config=None, event_store: Optional[EventStore] = None):
        self.config = config or Config
        self.event_store = event_store or EventStore()
        self.keys_file = Path(self.config.VAPID_KEYS_FILE)
        self.contact_email = self.config.VAPID_CONTACT_EMAIL
        
        self.public_key_b64: str = ""
        self.private_key_pem: str = ""
        self._init_vapid_keys()

    def _init_vapid_keys(self) -> None:
        """Load VAPID keys from config, file, or generate a fresh pair."""
        # 1. Environment variables take precedence if set
        pub = self.config.VAPID_PUBLIC_KEY
        priv = self.config.VAPID_PRIVATE_KEY
        if pub and priv:
            self.public_key_b64 = pub
            self.private_key_pem = priv
            return

        # 2. Check persistent keys file
        if self.keys_file.exists():
            try:
                with open(self.keys_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.public_key_b64 = data.get("public_key", "")
                    self.private_key_pem = data.get("private_key", "")
                    if self.public_key_b64 and self.private_key_pem:
                        return
            except Exception as e:
                logger.warning(f"Could not load VAPID keys from {self.keys_file}: {e}")

        # 3. Generate new VAPID keys if none found
        self._generate_and_save_keys()

    def _generate_and_save_keys(self) -> None:
        v = Vapid()
        v.generate_keys()
        
        # Public key in uncompressed point format, base64url encoded
        pub_bytes = v.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
        self.public_key_b64 = base64.urlsafe_b64encode(pub_bytes).decode("utf-8").rstrip("=")
        
        # Save private key as PEM string
        from cryptography.hazmat.primitives import serialization
        priv_pem = v.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode("utf-8")
        self.private_key_pem = priv_pem

        # Save to keys file
        self.keys_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.keys_file, "w", encoding="utf-8") as f:
                json.dump({
                    "public_key": self.public_key_b64,
                    "private_key": self.private_key_pem,
                    "contact_email": self.contact_email,
                }, f, indent=2)
            logger.info(f"Generated and saved new VAPID keys to {self.keys_file}")
        except Exception as e:
            logger.error(f"Failed to save VAPID keys to file: {e}")

    def get_public_key(self) -> str:
        """Return the base64url-encoded VAPID public key for browser PushManager.subscribe()."""
        return self.public_key_b64

    def subscribe(self, subscription_info: Dict[str, Any], user_agent: Optional[str] = None) -> bool:
        """Register or update a browser push subscription."""
        endpoint = subscription_info.get("endpoint")
        keys = subscription_info.get("keys", {})
        p256dh = keys.get("p256dh")
        auth = keys.get("auth")

        if not endpoint or not p256dh or not auth:
            return False

        return self.event_store.save_push_subscription(
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
            user_agent=user_agent
        )

    def unsubscribe(self, endpoint: str) -> bool:
        """Remove a browser push subscription."""
        return self.event_store.remove_push_subscription(endpoint)

    def send_notification_to_subscription(
        self,
        subscription: Dict[str, Any],
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send a Web Push notification to a specific browser subscription."""
        endpoint = subscription.get("endpoint")
        if not endpoint:
            return {"success": False, "error": "Missing endpoint"}

        sub_info = {
            "endpoint": endpoint,
            "keys": {
                "p256dh": subscription.get("p256dh"),
                "auth": subscription.get("auth"),
            }
        }

        claims = {
            "sub": f"mailto:{self.contact_email}"
        }

        payload_data = json.dumps(payload)

        try:
            response = webpush(
                subscription_info=sub_info,
                data=payload_data,
                vapid_private_key=self.private_key_pem,
                vapid_claims=claims,
                timeout=10
            )
            return {
                "success": True,
                "status_code": response.status_code if response else 200,
                "endpoint": endpoint[:40] + "...",
            }
        except WebPushException as ex:
            status_code = ex.response.status_code if ex.response else 0
            # HTTP 404 or 410 indicates the subscription is expired or unsubscribed
            if status_code in (404, 410):
                logger.info(f"Subscription expired ({status_code}), removing: {endpoint[:30]}...")
                self.event_store.deactivate_push_subscription(endpoint)
                return {
                    "success": False,
                    "status_code": status_code,
                    "error": f"Subscription expired/gone ({status_code})",
                    "permanent": True
                }
            return {
                "success": False,
                "status_code": status_code,
                "error": str(ex),
                "permanent": False
            }
        except Exception as e:
            return {
                "success": False,
                "status_code": 0,
                "error": str(e),
                "permanent": False
            }

    def broadcast_event(self, event: Dict[str, Any], click_url: Optional[str] = None) -> Dict[str, Any]:
        """Broadcast an event to all active Web Push subscriptions."""
        subs = self.event_store.get_active_push_subscriptions()
        if not subs:
            return {"success": True, "count": 0, "delivered": 0, "failed": 0, "message": "No active subscriptions"}

        title, body, icon = self._format_notification(event)
        target_url = click_url or f"http://{self.config.FLASK_HOST if self.config.FLASK_HOST != '0.0.0.0' else '127.0.0.1'}:{self.config.FLASK_PORT}"

        payload = {
            "title": title,
            "body": body,
            "icon": "/static/icons/icon-192.png",
            "badge": "/static/icons/badge-72.png",
            "url": target_url,
            "event_id": event.get("event_id"),
            "event_type": event.get("event_type"),
            "severity": event.get("severity"),
            "timestamp": event.get("timestamp"),
        }

        delivered = 0
        failed = 0
        for sub in subs:
            res = self.send_notification_to_subscription(sub, payload)
            if res.get("success"):
                delivered += 1
            else:
                failed += 1

        return {
            "success": True,
            "count": len(subs),
            "delivered": delivered,
            "failed": failed,
        }

    def _format_notification(self, event: Dict[str, Any]) -> tuple[str, str, str]:
        event_type = event.get("event_type", "INFO")
        reason = event.get("reason", "Hazard evaluation update")
        temp = event.get("temperature_c")

        if event_type == "HARDWARE_FIRE_ALERT":
            title = "🔥 FIRE DETECTED: FireShield AI"
            body = f"Immediate action required! {reason}"
            icon = "🔥"
        elif event_type == "EARLY_WARNING":
            title = "⚠️ Early Warning: Elevated Fire Risk"
            body = f"Thermal activity detected: {reason}"
            icon = "⚠️"
        elif event_type == "BASELINE_ANOMALY":
            title = "ℹ️ Environmental Baseline Anomaly"
            body = f"{reason}"
            icon = "ℹ️"
        elif event_type == "SENSOR_OR_DATA_FAULT":
            title = "⚠️ Sensor or Telemetry Fault"
            body = f"{reason}"
            icon = "🔧"
        elif event_type == "ALL_CLEAR":
            title = "✅ All Clear: Normal Conditions"
            body = f"{reason}"
            icon = "✅"
        else:
            title = "FireShield AI Alert"
            body = reason
            icon = "🔔"

        return title, body, icon
