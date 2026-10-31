from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from config import Config
from services.event_store import EventStore
from services.ntfy_service import NtfyService
from services.risk_engine import RiskEngine, RiskState
from services.voice_service import VoiceService
from services.webpush_service import WebPushService

logger = logging.getLogger(__name__)


class AlertService:
    """Orchestrates risk evaluation, persistent event recording, and multi-channel alert delivery."""

    def __init__(
        self,
        config=None,
        event_store: Optional[EventStore] = None,
        risk_engine: Optional[RiskEngine] = None,
        ntfy_service: Optional[NtfyService] = None,
        webpush_service: Optional[WebPushService] = None,
        voice_service: Optional[VoiceService] = None,
    ):
        self.config = config or Config
        self.event_store = event_store or EventStore()
        self.risk_engine = risk_engine or RiskEngine(config=self.config)
        self.ntfy_service = ntfy_service or NtfyService(config=self.config)
        self.webpush_service = webpush_service or WebPushService(config=self.config, event_store=self.event_store)
        self.voice_service = voice_service or VoiceService(config=self.config, event_store=self.event_store)

    def evaluate_and_alert(
        self,
        reading: Dict[str, Any],
        baseline: Optional[Dict[str, Any]] = None,
        click_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Evaluate a reading, record an event if needed, and dispatch notifications."""
        eval_res = self.risk_engine.evaluate_reading(reading, baseline=baseline)
        state = eval_res.get("state", RiskState.NORMAL)
        event_type = eval_res.get("event_type", state)
        severity = eval_res.get("severity", "INFO")
        should_alert = eval_res.get("should_alert", False)
        reason = eval_res.get("reason", "")
        metrics = eval_res.get("metrics", {})

        recorded_event = None
        delivery_results = {}

        if should_alert or event_type != RiskState.NORMAL:
            # 1. Persist Event to SQLite
            recorded_event = self.event_store.record_event(
                event_type=event_type,
                severity=severity,
                reason=reason,
                entry_id=reading.get("entry_id"),
                timestamp=reading.get("created_at"),
                raw_flame=metrics.get("flame_raw"),
                raw_smoke=metrics.get("smoke_status"),
                temperature_c=metrics.get("temperature_c"),
                humidity_pct=metrics.get("humidity_pct"),
                servo_angle=metrics.get("servo_angle"),
                fire_status=metrics.get("fire_status"),
                baseline_temp_mean=metrics.get("baseline_temp_mean"),
                baseline_hum_mean=metrics.get("baseline_hum_mean"),
                temp_deviation=metrics.get("temp_deviation"),
                temp_rate_c_min=metrics.get("temp_rate_c_min"),
                details=metrics,
            )

        if should_alert and recorded_event:
            event_id = recorded_event.get("event_id", "")

            # 1. High Priority: Automated Outbound Voice Call for Confirmed Multi-Sensor Fire Incidents
            # Phone calls are triggered ONLY when:
            # - Dual-sensor confirmed (Both Flame + Smoke active), OR
            # - Multi-sensor physically verified (Flame/Smoke confirmed by Temp Rise + Humidity Drop, confidence >= 70%)
            # Single-sensor triggers are flagged as SUSPECT FALSE ALARM and NEVER dial the user's phone.
            is_phone_call_warranted = (
                eval_res.get("should_phone_call", False)
                or metrics.get("dual_sensor_confirmed", False)
                or event_type in (RiskState.CONFIRMED_FIRE_ALERT, RiskState.DUAL_SENSOR_ALERT)
                or (metrics.get("confidence_score", 0) >= 70)
            )
            if event_type == RiskState.SINGLE_SENSOR_SUSPECT or metrics.get("single_sensor_suspect"):
                is_phone_call_warranted = False

            if is_phone_call_warranted:
                voice_outbox_id = self.event_store.enqueue_notification(
                    event_id=event_id,
                    channel="voice",
                    payload=recorded_event,
                    recipient_id=self.voice_service.recipient_phone,
                    max_attempts=3,
                )
                voice_res = self.voice_service.trigger_fire_voice_call(recorded_event)
                delivery_results["voice"] = voice_res
                if voice_res.get("success"):
                    self.event_store.mark_outbox_delivered(voice_outbox_id)
                else:
                    self.event_store.mark_outbox_failed(
                        voice_outbox_id, voice_res.get("error") or voice_res.get("message") or "Voice alert not dispatched"
                    )

            # 2. Dispatch via ntfy (Mobile channel)
            ntfy_outbox_id = self.event_store.enqueue_notification(
                event_id=event_id,
                channel="ntfy",
                payload=recorded_event,
                recipient_id=self.ntfy_service.default_topic
            )
            ntfy_res = self.ntfy_service.publish_event(recorded_event, click_url=click_url)
            delivery_results["ntfy"] = ntfy_res
            if ntfy_res.get("success"):
                self.event_store.mark_outbox_delivered(ntfy_outbox_id)
            else:
                self.event_store.mark_outbox_failed(ntfy_outbox_id, ntfy_res.get("error", "Unknown ntfy error"))

            # 3. Dispatch via Web Push (Browser channel)
            webpush_outbox_id = self.event_store.enqueue_notification(
                event_id=event_id,
                channel="webpush",
                payload=recorded_event,
                recipient_id="broadcast"
            )
            webpush_res = self.webpush_service.broadcast_event(recorded_event, click_url=click_url)
            delivery_results["webpush"] = webpush_res
            if webpush_res.get("success"):
                self.event_store.mark_outbox_delivered(webpush_outbox_id)
            else:
                self.event_store.mark_outbox_failed(webpush_outbox_id, webpush_res.get("message", "Web push error"))

        return {
            "state": state,
            "event_type": event_type,
            "severity": severity,
            "should_alert": should_alert,
            "reason": reason,
            "event": recorded_event,
            "delivery": delivery_results,
            "metrics": metrics,
        }

    def process_outbox(self) -> Dict[str, Any]:
        """Retry pending notifications with exponential backoff."""
        pending_items = self.event_store.get_pending_outbox_items(limit=20)
        retried = 0
        succeeded = 0
        failed = 0

        for item in pending_items:
            retried += 1
            outbox_id = item["id"]
            channel = item["channel"]
            payload = item.get("payload", {})

            if channel == "voice":
                res = self.voice_service.trigger_fire_voice_call(payload, recipient_override=item.get("recipient_id") or None)
                if res.get("success"):
                    self.event_store.mark_outbox_delivered(outbox_id)
                    succeeded += 1
                else:
                    self.event_store.mark_outbox_failed(outbox_id, res.get("error", "Voice call retry failed"))
                    failed += 1

            elif channel == "ntfy":
                res = self.ntfy_service.publish_event(payload, topic=item.get("recipient_id") or None)
                if res.get("success"):
                    self.event_store.mark_outbox_delivered(outbox_id)
                    succeeded += 1
                else:
                    self.event_store.mark_outbox_failed(outbox_id, res.get("error", "ntfy retry failed"))
                    failed += 1

            elif channel == "webpush":
                res = self.webpush_service.broadcast_event(payload)
                if res.get("success"):
                    self.event_store.mark_outbox_delivered(outbox_id)
                    succeeded += 1
                else:
                    self.event_store.mark_outbox_failed(outbox_id, res.get("message", "webpush retry failed"))
                    failed += 1

        return {
            "pending_count": len(pending_items),
            "retried": retried,
            "succeeded": succeeded,
            "failed": failed,
        }

    def send_test_alert(self, channels: Optional[list] = None) -> Dict[str, Any]:
        """Send a test notification across configured channels."""
        target_channels = channels or ["ntfy", "webpush"]
        results = {}

        test_event = {
            "event_id": f"test_{int(Config.POLL_INTERVAL_SECONDS)}",
            "event_type": "TEST_NOTIFICATION",
            "severity": "INFO",
            "reason": "Test notification: FireShield AI background alert service is operational.",
            "temperature_c": 26.5,
            "humidity_pct": 52.0,
            "raw_flame": 1024.0,
            "raw_smoke": 0,
            "servo_angle": 90.0,
            "fire_status": 0,
        }

        if "voice" in target_channels:
            results["voice"] = self.voice_service.trigger_fire_voice_call(test_event, force=True)
        if "ntfy" in target_channels:
            results["ntfy"] = self.ntfy_service.send_test_notification()
        if "webpush" in target_channels:
            results["webpush"] = self.webpush_service.broadcast_event(test_event)

        return {
            "success": any(r.get("success") for r in results.values()),
            "channels": results,
            "event": test_event
        }
