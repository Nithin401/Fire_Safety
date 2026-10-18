from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import requests

from config import Config


class ThingSpeakService:
    """Service to communicate with ThingSpeak API and normalize feeds."""

    def __init__(self, config: type[Config] = Config):
        self.config = config
        self._cache: Dict[str, Tuple[float, Any]] = {}

    @property
    def channel_id(self) -> str:
        return self.config.THINGSPEAK_CHANNEL_ID

    @property
    def read_api_key(self) -> str:
        return self.config.THINGSPEAK_READ_API_KEY

    @property
    def base_url(self) -> str:
        return self.config.THINGSPEAK_BASE_URL.rstrip("/")

    def is_configured(self) -> bool:
        return bool(self.channel_id)

    def _get_cached(self, cache_key: str) -> Optional[Any]:
        if cache_key in self._cache:
            cached_time, data = self._cache[cache_key]
            if time.time() - cached_time < self.config.CACHE_TTL_SECONDS:
                return data
            del self._cache[cache_key]
        return None

    def _set_cached(self, cache_key: str, data: Any) -> None:
        self._cache[cache_key] = (time.time(), data)

    def clear_cache(self) -> None:
        self._cache.clear()

    def fetch_feeds(
        self,
        results: int = 100,
        start: Optional[str] = None,
        end: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Fetch channel feed records with caching and error handling.
        
        Returns a dict:
        {
            "success": bool,
            "channel": dict,
            "raw_feeds": list,
            "normalized_feeds": list,
            "error": str | None,
            "cached": bool,
            "fetched_at": str
        }
        """
        if not self.is_configured():
            return {
                "success": False,
                "channel": {},
                "raw_feeds": [],
                "normalized_feeds": [],
                "error": "ThingSpeak Channel ID is not configured in .env",
                "cached": False,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }

        cache_key = f"feeds_{results}_{start}_{end}"
        if not force_refresh:
            cached_data = self._get_cached(cache_key)
            if cached_data is not None:
                cached_data["cached"] = True
                return cached_data

        url = f"{self.base_url}/channels/{self.channel_id}/feeds.json"
        params: Dict[str, Any] = {"results": min(results, self.config.MAX_HISTORY_RESULTS)}
        if self.read_api_key:
            params["api_key"] = self.read_api_key
        if start:
            params["start"] = start
        if end:
            params["end"] = end

        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                payload = resp.json()
                raw_feeds = payload.get("feeds", [])
                channel_info = payload.get("channel", {})
                normalized = [self.normalize_entry(entry) for entry in raw_feeds]

                result = {
                    "success": True,
                    "channel": channel_info,
                    "raw_feeds": raw_feeds,
                    "normalized_feeds": normalized,
                    "error": None,
                    "cached": False,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }
                self._set_cached(cache_key, result)
                return result
            elif resp.status_code == 404:
                return {
                    "success": False,
                    "channel": {},
                    "raw_feeds": [],
                    "normalized_feeds": [],
                    "error": f"Channel {self.channel_id} not found on ThingSpeak (404).",
                    "cached": False,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }
            elif resp.status_code == 400:
                return {
                    "success": False,
                    "channel": {},
                    "raw_feeds": [],
                    "normalized_feeds": [],
                    "error": "Bad request to ThingSpeak API (400). Check channel ID and parameters.",
                    "cached": False,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }
            else:
                return {
                    "success": False,
                    "channel": {},
                    "raw_feeds": [],
                    "normalized_feeds": [],
                    "error": f"ThingSpeak API responded with status code {resp.status_code}",
                    "cached": False,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "channel": {},
                "raw_feeds": [],
                "normalized_feeds": [],
                "error": "Connection to ThingSpeak timed out (10s limit).",
                "cached": False,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
        except (requests.exceptions.RequestException, Exception) as e:
            return {
                "success": False,
                "channel": {},
                "raw_feeds": [],
                "normalized_feeds": [],
                "error": f"Network error connecting to ThingSpeak: {type(e).__name__}",
                "cached": False,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
        except ValueError:
            return {
                "success": False,
                "channel": {},
                "raw_feeds": [],
                "normalized_feeds": [],
                "error": "Malformed JSON received from ThingSpeak API.",
                "cached": False,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }

    def fetch_latest_reading(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Fetch the single latest reading from the channel."""
        if not self.is_configured():
            return {
                "success": False,
                "reading": None,
                "error": "ThingSpeak Channel ID is not configured in .env",
                "cached": False,
            }

        cache_key = "latest_entry"
        if not force_refresh:
            cached_data = self._get_cached(cache_key)
            if cached_data is not None:
                cached_data["cached"] = True
                return cached_data

        url = f"{self.base_url}/channels/{self.channel_id}/feeds/last.json"
        params: Dict[str, Any] = {}
        if self.read_api_key:
            params["api_key"] = self.read_api_key

        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                payload = resp.json()
                if not payload or payload == -1 or not isinstance(payload, dict):
                    result = {
                        "success": True,
                        "reading": None,
                        "error": "Channel has no recorded feeds.",
                        "cached": False,
                    }
                else:
                    norm = self.normalize_entry(payload)
                    result = {
                        "success": True,
                        "reading": norm,
                        "error": None,
                        "cached": False,
                    }
                self._set_cached(cache_key, result)
                return result
            elif resp.status_code == 404:
                return {
                    "success": False,
                    "reading": None,
                    "error": f"Channel {self.channel_id} not found.",
                    "cached": False,
                }
            else:
                return {
                    "success": False,
                    "reading": None,
                    "error": f"ThingSpeak returned HTTP {resp.status_code}",
                    "cached": False,
                }
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "reading": None,
                "error": "ThingSpeak request timed out.",
                "cached": False,
            }
        except (requests.exceptions.RequestException, Exception) as e:
            return {
                "success": False,
                "reading": None,
                "error": f"Network error connecting to ThingSpeak: {type(e).__name__}",
                "cached": False,
            }
        except ValueError:
            return {
                "success": False,
                "reading": None,
                "error": "Malformed JSON received from ThingSpeak.",
                "cached": False,
            }

    @staticmethod
    def _parse_float(val: Any) -> Optional[float]:
        if val is None or val == "":
            return None
        try:
            f = float(val)
            if str(f).lower() in ("nan", "inf", "-inf"):
                return None
            return f
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_int(val: Any) -> Optional[int]:
        if val is None or val == "":
            return None
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return None

    @classmethod
    def normalize_entry(cls, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a raw ThingSpeak record preserving raw fields and deriving mapped columns.
        
        Strict 6-field contract:
        field1: FLAME (raw analog reading)
        field2: SMOKEVALUE (1 = detected, 0 = not detected)
        field3: TEMPERATURE (DHT11 in °C)
        field4: HUMIDITY (DHT11 relative %)
        field5: SERVO ANGLE (degrees)
        field6: FIRE STATUS (1 = hardware fire rule triggered, 0 = not triggered)
        """
        entry_id = cls._parse_int(raw.get("entry_id"))
        created_at_raw = raw.get("created_at")

        # Parse timestamp safely
        created_dt: Optional[datetime] = None
        is_stale = True
        age_seconds: Optional[float] = None
        if created_at_raw:
            for fmt in (
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f%z",
                "%Y-%m-%dT%H:%M:%S.%fZ",
            ):
                try:
                    created_dt = datetime.strptime(created_at_raw, fmt)
                    if created_dt.tzinfo is None:
                        created_dt = created_dt.replace(tzinfo=timezone.utc)
                    age_seconds = (datetime.now(timezone.utc) - created_dt).total_seconds()
                    is_stale = age_seconds > Config.STALE_THRESHOLD_SECONDS
                    break
                except ValueError:
                    continue

        flame_raw = cls._parse_float(raw.get("field1"))
        smoke_val = cls._parse_int(raw.get("field2"))
        temp_c = cls._parse_float(raw.get("field3"))
        humidity = cls._parse_float(raw.get("field4"))
        servo = cls._parse_float(raw.get("field5"))
        fire_stat = cls._parse_int(raw.get("field6"))

        # Fire status classification
        if fire_stat is None:
            fire_label = "UNAVAILABLE"
        elif fire_stat == 1:
            fire_label = "HARDWARE_TRIGGERED"
        elif fire_stat == 0:
            fire_label = "NOT_TRIGGERED"
        else:
            fire_label = f"UNKNOWN_STATE_{fire_stat}"

        return {
            # Raw original ThingSpeak schema
            "entry_id": entry_id,
            "created_at": created_at_raw,
            "field1": raw.get("field1"),
            "field2": raw.get("field2"),
            "field3": raw.get("field3"),
            "field4": raw.get("field4"),
            "field5": raw.get("field5"),
            "field6": raw.get("field6"),
            # Derived mapped columns
            "flame_raw": flame_raw,
            "smoke_status": smoke_val,
            "temperature_c": temp_c,
            "humidity_pct": humidity,
            "servo_angle": servo,
            "fire_status": fire_stat,
            # Metadata & freshness
            "fire_label": fire_label,
            "age_seconds": round(age_seconds, 1) if age_seconds is not None else None,
            "is_stale": is_stale,
        }
