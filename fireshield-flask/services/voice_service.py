from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import requests

from config import Config
from services.event_store import EventStore

logger = logging.getLogger(__name__)

# List of prohibited emergency numbers to protect against accidental live dialing
PROHIBITED_EMERGENCY_NUMBERS = {
    "100", "101", "102", "108", "112", "911", "999", "000",
    "+91100", "+91101", "+91102", "+91108", "+91112",
}

DEFAULT_ALERT_MESSAGE = (
    "FireShield AI critical alert. A possible fire condition has been detected. "
    "Please check the affected area safely. This is an automated safety alert."
)


class VoiceService:
    """Dedicated voice call telephony service with Exotel provider integration,

    India number normalization, cooldown management, and safe dry-run mode.
    """

    def __init__(self, config=None, event_store: Optional[EventStore] = None):
        self.config = config or Config
        self.event_store = event_store or EventStore()

        self.account_sid = self.config.EXOTEL_ACCOUNT_SID
        self.api_key = self.config.EXOTEL_API_KEY
        self.api_token = self.config.EXOTEL_API_TOKEN
        self.caller_id = self.config.EXOTEL_CALLER_ID
        self.base_url = self.config.EXOTEL_API_BASE_URL.rstrip("/")
        self.app_id = self.config.EXOTEL_APP_ID
        self.recipient_phone = self.config.FIRESHIELD_ALERT_PHONE
        self.enabled = self.config.VOICE_ALERT_ENABLED
        self.dry_run = self.config.VOICE_ALERT_DRY_RUN
        self.cooldown_seconds = self.config.VOICE_ALERT_COOLDOWN_SECONDS
        self.public_base_url = self.config.PUBLIC_BASE_URL.rstrip("/")

    # -------------------------------------------------------------
    # Configuration Diagnostics & Safety
    # -------------------------------------------------------------

    def is_configured(self) -> bool:
        """Check if all necessary Exotel credentials and numbers are present."""
        return bool(
            self.account_sid
            and self.api_key
            and self.api_token
            and self.caller_id
            and self.recipient_phone
        )

    def is_dry_run_active(self) -> bool:
        """Return True if dry run mode is enabled or credentials are incomplete."""
        return self.dry_run or not self.is_configured()

    def get_config_status(self) -> Dict[str, Any]:
        """Return sanitized provider configuration status without exposing credentials."""
        recipient = self.normalize_phone(self.recipient_phone) if self.recipient_phone else ""
        caller = self.caller_id

        return {
            "provider": "exotel",
            "enabled": self.enabled,
            "dry_run": self.dry_run,
            "effective_dry_run": self.is_dry_run_active(),
            "cooldown_seconds": self.cooldown_seconds,
            "has_account_sid": bool(self.account_sid),
            "has_api_key": bool(self.api_key),
            "has_api_token": bool(self.api_token),
            "has_caller_id": bool(self.caller_id),
            "has_recipient_phone": bool(self.recipient_phone),
            "has_app_id": bool(self.app_id),
            "masked_recipient": self._mask_phone(recipient) if recipient else "Not Set",
            "masked_caller_id": self._mask_phone(caller) if caller else "Not Set",
            "is_ready_for_live": bool(self.enabled and not self.dry_run and self.is_configured()),
            "last_call": self.event_store.get_last_voice_call(),
            "in_cooldown": self.event_store.is_in_voice_cooldown(self.cooldown_seconds),
        }

    # -------------------------------------------------------------
    # Number Normalization & Validation
    # -------------------------------------------------------------

    @staticmethod
    def normalize_phone(phone: str) -> str:
        """Normalize an Indian or international phone number to E.164 (+91XXXXXXXXXX)."""
        if not phone:
            return ""

        clean = re.sub(r"[\s\-\(\)]", "", str(phone).strip())

        # Prohibit emergency numbers
        if clean in PROHIBITED_EMERGENCY_NUMBERS:
            raise ValueError(f"Prohibited emergency number: {clean}")

        # If 10 digits (Standard Indian Mobile, e.g. 9876543210), prepend +91
        if re.match(r"^[6-9]\d{9}$", clean):
            return f"+91{clean}"

        # If 11 digits starting with 0 (e.g. 09876543210), replace leading 0 with +91
        if re.match(r"^0[6-9]\d{9}$", clean):
            return f"+91{clean[1:]}"

        # If 12 digits starting with 91 (e.g. 919876543210), prepend +
        if re.match(r"^91[6-9]\d{9}$", clean):
            return f"+{clean}"

        # If already E.164 (e.g. +919876543210)
        if re.match(r"^\+[1-9]\d{7,14}$", clean):
            return clean

        return clean

    @staticmethod
    def validate_destination_number(phone: str) -> bool:
        """Ensure number is a valid mobile destination and not an emergency service."""
        try:
            norm = VoiceService.normalize_phone(phone)
            if not norm or norm in PROHIBITED_EMERGENCY_NUMBERS:
                return False
            # Valid E.164 length between 8 and 16 chars including +
            return bool(re.match(r"^\+[1-9]\d{7,14}$", norm))
        except ValueError:
            return False

    @staticmethod
    def _mask_phone(phone: str) -> str:
        if not phone or len(phone) < 6:
            return "****"
        return f"{phone[:3]}****{phone[-4:]}"

    # -------------------------------------------------------------
    # Spoken Message Construction
    # -------------------------------------------------------------

    def format_alert_message(self, event: Optional[Dict[str, Any]] = None) -> str:
        """Generate understandable spoken text for TTS."""
        if not event:
            return DEFAULT_ALERT_MESSAGE

        details = []
        temp = event.get("temperature_c")
        if temp is not None:
            details.append(f"Temperature is {float(temp):.1f} degrees Celsius.")

        servo = event.get("servo_angle")
        if servo is not None:
            details.append(f"Scanner azimuth is {int(servo)} degrees.")

        extra = " ".join(details)
        if extra:
            return f"{DEFAULT_ALERT_MESSAGE} {extra}"
        return DEFAULT_ALERT_MESSAGE

    def get_exoml_response(self, message: Optional[str] = None) -> str:
        """Generate valid ExoML XML for Exotel TTS flow."""
        text = message or DEFAULT_ALERT_MESSAGE
        # Sanitize XML characters
        safe_text = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<Response>\n"
            f'    <Say voice="female" language="en-IN">{safe_text}</Say>\n'
            '    <Pause length="1"/>\n'
            f'    <Say voice="female" language="en-IN">{safe_text}</Say>\n'
            "    <Hangup/>\n"
            "</Response>\n"
        )

    # -------------------------------------------------------------
    # Voice Call Execution
    # -------------------------------------------------------------

    def trigger_fire_voice_call(
        self,
        event: Dict[str, Any],
        recipient_override: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Trigger an outbound voice call for a critical fire incident.

        Adheres strictly to cooldown and entry deduplication.
        """
        incident_id = event.get("event_id") or f"inc_{int(datetime.now(timezone.utc).timestamp())}"
        entry_id = event.get("entry_id")
        recipient = recipient_override or self.recipient_phone

        if not recipient:
            if self.is_dry_run_active():
                recipient = "+919999999999"  # Safe dummy number for dry-run simulation
            else:
                err = "Recipient phone number is not configured. Set FIRESHIELD_ALERT_PHONE in settings."
                logger.warning(f"[VoiceAlert] {err}")
                return {
                    "success": False,
                    "status": "failed",
                    "error": err,
                    "is_dry_run": self.is_dry_run_active(),
                }

        # 1. Validation
        if not self.validate_destination_number(recipient):
            err = f"Invalid or prohibited destination phone number: {recipient}"
            logger.warning(f"[VoiceAlert] {err}")
            return {
                "success": False,
                "status": "failed",
                "error": err,
                "is_dry_run": self.is_dry_run_active(),
            }

        norm_recipient = self.normalize_phone(recipient)

        # 2. Check Cooldown (unless force=True, e.g. for manual test)
        if not force and self.event_store.is_in_voice_cooldown(self.cooldown_seconds):
            msg = f"Voice alert suppressed: system is within {self.cooldown_seconds}s cooldown window."
            logger.info(f"[VoiceAlert] {msg}")
            return {
                "success": False,
                "status": "cooldown_suppressed",
                "message": msg,
                "is_dry_run": self.is_dry_run_active(),
            }

        # 3. Check if Voice Alerts are disabled by user configuration
        if not self.enabled and not force:
            msg = "Voice alerts are currently disabled in configuration (VOICE_ALERT_ENABLED=false)."
            logger.info(f"[VoiceAlert] {msg}")
            return {
                "success": False,
                "status": "disabled",
                "message": msg,
                "is_dry_run": self.is_dry_run_active(),
            }

        call_id = f"vcall_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        spoken_message = self.format_alert_message(event)

        # 4. Dry Run Mode Handling
        if self.is_dry_run_active():
            dry_sid = f"dryrun_exo_{uuid.uuid4().hex[:12]}"
            logger.info(
                f"[VoiceAlert] [DRY RUN] Simulating voice call {call_id} to {self._mask_phone(norm_recipient)}"
            )
            simulated_response = {
                "Call": {
                    "Sid": dry_sid,
                    "Status": "in-progress",
                    "To": norm_recipient,
                    "CallerId": self.caller_id or "+910000000000",
                    "DateCreated": datetime.now(timezone.utc).isoformat(),
                    "Note": "Dry-run mode simulated call. No telephony credits consumed.",
                }
            }

            recorded = self.event_store.record_voice_call(
                call_id=call_id,
                incident_id=incident_id,
                entry_id=entry_id,
                recipient_phone=norm_recipient,
                provider="exotel_dryrun",
                provider_call_sid=dry_sid,
                status="accepted",
                message_text=spoken_message,
                is_dry_run=True,
                provider_response=simulated_response,
            )

            return {
                "success": True,
                "status": "accepted",
                "call_id": call_id,
                "provider_call_sid": dry_sid,
                "is_dry_run": True,
                "recipient": self._mask_phone(norm_recipient),
                "message": "Dry-run voice call simulated successfully (no real call placed).",
                "record": recorded,
            }

        # 5. Live Exotel Outbound Call
        return self._place_exotel_call(
            call_id=call_id,
            incident_id=incident_id,
            entry_id=entry_id,
            recipient=norm_recipient,
            spoken_message=spoken_message,
        )

    def _place_exotel_call(
        self,
        call_id: str,
        incident_id: str,
        entry_id: Optional[int],
        recipient: str,
        spoken_message: str,
    ) -> Dict[str, Any]:
        """Execute HTTP request to Exotel Outbound Call Connect API."""
        endpoint = f"{self.base_url}/v1/Accounts/{self.account_sid}/Calls/connect.json"

        # Determine Call Flow URL:
        # If EXOTEL_APP_ID is provided, use Exotel Exoml app URL.
        # Otherwise, fall back to our public dynamic ExoML webhook.
        if self.app_id:
            flow_url = f"http://my.exotel.com/{self.account_sid}/exoml/start_voice/{self.app_id}"
        else:
            flow_url = f"{self.public_base_url}/api/voice/exoml"

        callback_url = f"{self.public_base_url}/api/voice/callback"

        payload = {
            "From": recipient,
            "CallerId": self.caller_id,
            "Url": flow_url,
            "CallType": "trans",
            "StatusCallback": callback_url,
            "CustomField": incident_id,
        }

        # Initial record in status 'requested'
        self.event_store.record_voice_call(
            call_id=call_id,
            incident_id=incident_id,
            entry_id=entry_id,
            recipient_phone=recipient,
            provider="exotel",
            status="requested",
            message_text=spoken_message,
            is_dry_run=False,
        )

        try:
            logger.info(
                f"[VoiceAlert] Placing live Exotel outbound call to {self._mask_phone(recipient)} via endpoint {self.base_url}"
            )
            response = requests.post(
                endpoint,
                auth=(self.api_key, self.api_token),
                data=payload,
                timeout=12.0,
            )

            # Redact credentials from any raw debugging
            resp_data: Dict[str, Any] = {}
            try:
                resp_data = response.json()
            except Exception:
                resp_data = {"raw_text": response.text[:200]}

            if response.status_code in (200, 201):
                call_info = resp_data.get("Call", {})
                provider_sid = call_info.get("Sid") or f"exo_{uuid.uuid4().hex[:10]}"
                provider_status = call_info.get("Status", "queued")

                # Map Exotel status to our standard lifecycle: queued/in-progress -> accepted
                app_status = "accepted" if provider_status in ("queued", "in-progress", "ringing") else provider_status

                self.event_store.update_voice_call_status(
                    call_id=call_id,
                    status=app_status,
                    provider_call_sid=provider_sid,
                    provider_response=resp_data,
                )

                logger.info(f"[VoiceAlert] Exotel call accepted: CallSid={provider_sid}")
                return {
                    "success": True,
                    "status": app_status,
                    "call_id": call_id,
                    "provider_call_sid": provider_sid,
                    "is_dry_run": False,
                    "recipient": self._mask_phone(recipient),
                    "provider_response": resp_data,
                }
            else:
                err_msg = resp_data.get("RestException", {}).get("Message") or f"HTTP {response.status_code}: {response.text[:150]}"
                self.event_store.update_voice_call_status(
                    call_id=call_id,
                    status="failed",
                    error_message=err_msg,
                    provider_response=resp_data,
                )
                logger.error(f"[VoiceAlert] Exotel call failed: {err_msg}")
                return {
                    "success": False,
                    "status": "failed",
                    "call_id": call_id,
                    "error": err_msg,
                    "is_dry_run": False,
                    "status_code": response.status_code,
                }

        except requests.exceptions.Timeout:
            err_msg = "Exotel API connection timed out (12s threshold)."
            self.event_store.update_voice_call_status(call_id=call_id, status="failed", error_message=err_msg)
            logger.error(f"[VoiceAlert] {err_msg}")
            return {"success": False, "status": "failed", "error": err_msg, "is_dry_run": False}
        except Exception as e:
            err_msg = f"Unexpected error initiating Exotel call: {type(e).__name__}: {str(e)}"
            self.event_store.update_voice_call_status(call_id=call_id, status="failed", error_message=err_msg)
            logger.error(f"[VoiceAlert] {err_msg}", exc_info=True)
            return {"success": False, "status": "failed", "error": err_msg, "is_dry_run": False}

    # -------------------------------------------------------------
    # Call Status & Webhook Handling
    # -------------------------------------------------------------

    def handle_status_callback(self, callback_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Exotel webhook callback on call status change."""
        sid = callback_data.get("CallSid") or callback_data.get("Sid")
        status = callback_data.get("Status") or callback_data.get("CallStatus")

        if not sid or not status:
            return {"success": False, "error": "Missing CallSid or Status"}

        # Map Exotel status to our state machine:
        status_map = {
            "queued": "accepted",
            "in-progress": "in-progress",
            "ringing": "ringing",
            "completed": "completed",
            "failed": "failed",
            "busy": "busy",
            "no-answer": "no-answer",
            "canceled": "canceled",
        }
        mapped_status = status_map.get(status.lower(), status.lower())

        updated = self.event_store.update_voice_call_status(
            call_id=sid,
            status=mapped_status,
            provider_response=callback_data,
        )

        logger.info(f"[VoiceAlert] Webhook received for CallSid {sid}: status -> {mapped_status}")
        return {"success": updated, "call_sid": sid, "mapped_status": mapped_status}
