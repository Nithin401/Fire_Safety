from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import Config


class EventStore:
    """SQLite-backed event history, outbox delivery queue, and push subscriptions store."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Config.DATABASE_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Events Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT UNIQUE NOT NULL,
                    entry_id INTEGER,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    raw_flame REAL,
                    raw_smoke INTEGER,
                    temperature_c REAL,
                    humidity_pct REAL,
                    servo_angle REAL,
                    fire_status INTEGER,
                    baseline_temp_mean REAL,
                    baseline_hum_mean REAL,
                    temp_deviation REAL,
                    temp_rate_c_min REAL,
                    reason TEXT,
                    details_json TEXT,
                    acknowledged INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)

            # Notification Outbox Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notification_outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    recipient_id TEXT,
                    payload_json TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    attempts INTEGER DEFAULT 0,
                    max_attempts INTEGER DEFAULT 5,
                    next_attempt_at TEXT NOT NULL,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    delivered_at TEXT
                )
            """)

            # Web Push Subscriptions Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS push_subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    endpoint TEXT UNIQUE NOT NULL,
                    p256dh TEXT NOT NULL,
                    auth TEXT NOT NULL,
                    user_agent TEXT,
                    created_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    active INTEGER DEFAULT 1
                )
            """)

            # State & Poller Metadata Table (tracks last processed ThingSpeak entry_id)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            conn.commit()

    # -------------------------------------------------------------
    # System State / Ingestion Tracking
    # -------------------------------------------------------------

    def get_last_processed_entry_id(self) -> Optional[int]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM system_state WHERE key = 'last_processed_entry_id'")
            row = cursor.fetchone()
            if row:
                try:
                    return int(row["value"])
                except (ValueError, TypeError):
                    return None
            return None

    def set_last_processed_entry_id(self, entry_id: int) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO system_state (key, value, updated_at)
                VALUES ('last_processed_entry_id', ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """, (str(entry_id), now_iso))
            conn.commit()

    # -------------------------------------------------------------
    # Event Management
    # -------------------------------------------------------------

    def record_event(
        self,
        event_type: str,
        severity: str,
        reason: str,
        entry_id: Optional[int] = None,
        timestamp: Optional[str] = None,
        raw_flame: Optional[float] = None,
        raw_smoke: Optional[int] = None,
        temperature_c: Optional[float] = None,
        humidity_pct: Optional[float] = None,
        servo_angle: Optional[float] = None,
        fire_status: Optional[int] = None,
        baseline_temp_mean: Optional[float] = None,
        baseline_hum_mean: Optional[float] = None,
        temp_deviation: Optional[float] = None,
        temp_rate_c_min: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record a risk event and generate a unique event_id."""
        now_utc = datetime.now(timezone.utc)
        now_iso = now_utc.isoformat()
        event_id = f"evt_{now_utc.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        event_ts = timestamp or now_iso
        details_str = json.dumps(details or {})

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO events (
                    event_id, entry_id, timestamp, event_type, severity,
                    raw_flame, raw_smoke, temperature_c, humidity_pct, servo_angle, fire_status,
                    baseline_temp_mean, baseline_hum_mean, temp_deviation, temp_rate_c_min,
                    reason, details_json, acknowledged, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """, (
                event_id, entry_id, event_ts, event_type, severity,
                raw_flame, raw_smoke, temperature_c, humidity_pct, servo_angle, fire_status,
                baseline_temp_mean, baseline_hum_mean, temp_deviation, temp_rate_c_min,
                reason, details_str, now_iso
            ))
            conn.commit()

        return self.get_event_by_id(event_id) or {}

    def get_event_by_id(self, event_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM events WHERE event_id = ?", (event_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_event_dict(row)
            return None

    def get_recent_events(self, limit: int = 50, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if event_type:
                cursor.execute(
                    "SELECT * FROM events WHERE event_type = ? ORDER BY id DESC LIMIT ?",
                    (event_type, limit)
                )
            else:
                cursor.execute(
                    "SELECT * FROM events ORDER BY id DESC LIMIT ?",
                    (limit,)
                )
            rows = cursor.fetchall()
            return [self._row_to_event_dict(r) for r in rows]

    def get_latest_event(self) -> Optional[Dict[str, Any]]:
        events = self.get_recent_events(limit=1)
        return events[0] if events else None

    def acknowledge_event(self, event_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE events SET acknowledged = 1 WHERE event_id = ?",
                (event_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def _row_to_event_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        if d.get("details_json"):
            try:
                d["details"] = json.loads(d["details_json"])
            except Exception:
                d["details"] = {}
        else:
            d["details"] = {}
        return d

    # -------------------------------------------------------------
    # Notification Outbox Management (Retry-safe with backoff)
    # -------------------------------------------------------------

    def enqueue_notification(
        self,
        event_id: str,
        channel: str,
        payload: Dict[str, Any],
        recipient_id: Optional[str] = None,
        max_attempts: int = 5,
    ) -> int:
        now_iso = datetime.now(timezone.utc).isoformat()
        payload_str = json.dumps(payload)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO notification_outbox (
                    event_id, channel, recipient_id, payload_json, status,
                    attempts, max_attempts, next_attempt_at, created_at
                ) VALUES (?, ?, ?, ?, 'pending', 0, ?, ?, ?)
            """, (event_id, channel, recipient_id or "", payload_str, max_attempts, now_iso, now_iso))
            conn.commit()
            return cursor.lastrowid or 0

    def get_pending_outbox_items(self, limit: int = 20) -> List[Dict[str, Any]]:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM notification_outbox
                WHERE status = 'pending' AND next_attempt_at <= ? AND attempts < max_attempts
                ORDER BY id ASC LIMIT ?
            """, (now_iso, limit))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                try:
                    item["payload"] = json.loads(item["payload_json"])
                except Exception:
                    item["payload"] = {}
                results.append(item)
            return results

    def mark_outbox_delivered(self, outbox_id: int) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE notification_outbox
                SET status = 'delivered', delivered_at = ?, last_error = NULL
                WHERE id = ?
            """, (now_iso, outbox_id))
            conn.commit()

    def mark_outbox_failed(self, outbox_id: int, error_msg: str, permanent: bool = False) -> None:
        now_utc = datetime.now(timezone.utc)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT attempts, max_attempts FROM notification_outbox WHERE id = ?", (outbox_id,))
            row = cursor.fetchone()
            if not row:
                return

            attempts = row["attempts"] + 1
            max_attempts = row["max_attempts"]

            if permanent or attempts >= max_attempts:
                new_status = "failed"
                next_attempt = (now_utc + timedelta(days=365)).isoformat()
            else:
                new_status = "pending"
                # Exponential backoff: 10s, 30s, 90s, 300s
                backoff_seconds = min(10 * (3 ** (attempts - 1)), 600)
                next_attempt = (now_utc + timedelta(seconds=backoff_seconds)).isoformat()

            cursor.execute("""
                UPDATE notification_outbox
                SET attempts = ?, status = ?, next_attempt_at = ?, last_error = ?
                WHERE id = ?
            """, (attempts, new_status, next_attempt, error_msg[:500], outbox_id))
            conn.commit()

    # -------------------------------------------------------------
    # Web Push Subscriptions
    # -------------------------------------------------------------

    def save_push_subscription(
        self,
        endpoint: str,
        p256dh: str,
        auth: str,
        user_agent: Optional[str] = None
    ) -> bool:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO push_subscriptions (
                    endpoint, p256dh, auth, user_agent, created_at, last_seen_at, active
                ) VALUES (?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(endpoint) DO UPDATE SET
                    p256dh = excluded.p256dh,
                    auth = excluded.auth,
                    user_agent = excluded.user_agent,
                    last_seen_at = excluded.last_seen_at,
                    active = 1
            """, (endpoint, p256dh, auth, user_agent or "", now_iso, now_iso))
            conn.commit()
            return True

    def remove_push_subscription(self, endpoint: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,))
            conn.commit()
            return cursor.rowcount > 0

    def deactivate_push_subscription(self, endpoint: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE push_subscriptions SET active = 0 WHERE endpoint = ?", (endpoint,))
            conn.commit()
            return cursor.rowcount > 0

    def get_active_push_subscriptions(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM push_subscriptions WHERE active = 1")
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
