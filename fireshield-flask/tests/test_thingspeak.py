from __future__ import annotations

import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from services.thingspeak_service import ThingSpeakService
from config import Config


class TestThingSpeakService(unittest.TestCase):

    def setUp(self):
        self.service = ThingSpeakService()
        self.service.clear_cache()

    def test_normalize_entry_complete_valid(self):
        """Test full 6-field normalization with valid values."""
        raw = {
            "entry_id": "142",
            "created_at": "2026-10-18T10:00:00Z",
            "field1": "450",     # flame raw
            "field2": "1",       # smoke
            "field3": "28.5",    # temp
            "field4": "55.2",    # humidity
            "field5": "90",      # servo
            "field6": "1",       # fire status
        }
        entry = self.service.normalize_entry(raw)

        self.assertEqual(entry["entry_id"], 142)
        self.assertEqual(entry["flame_raw"], 450.0)
        self.assertEqual(entry["smoke_status"], 1)
        self.assertEqual(entry["temperature_c"], 28.5)
        self.assertEqual(entry["humidity_pct"], 55.2)
        self.assertEqual(entry["servo_angle"], 90.0)
        self.assertEqual(entry["fire_status"], 1)
        self.assertEqual(entry["fire_label"], "HARDWARE_TRIGGERED")
        self.assertTrue(entry["is_stale"])  # 2026-10-18T10:00:00Z vs now

    def test_normalize_missing_fields_never_zeroed(self):
        """Rule: Never silently substitute 0 for missing readings."""
        raw = {
            "entry_id": "143",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "field1": None,
            "field2": "",
            "field3": "invalid_num",
            "field4": None,
            "field5": None,
            "field6": None,
        }
        entry = self.service.normalize_entry(raw)

        self.assertIsNone(entry["flame_raw"])
        self.assertIsNone(entry["smoke_status"])
        self.assertIsNone(entry["temperature_c"])
        self.assertIsNone(entry["humidity_pct"])
        self.assertIsNone(entry["servo_angle"])
        self.assertIsNone(entry["fire_status"])
        self.assertEqual(entry["fire_label"], "UNAVAILABLE")

    def test_fresh_vs_stale_detection(self):
        """Test that data age correctly flags is_stale."""
        fresh_raw = {
            "entry_id": "1",
            "created_at": (datetime.now(timezone.utc) - timedelta(seconds=10)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "field6": "0",
        }
        fresh_entry = self.service.normalize_entry(fresh_raw)
        self.assertFalse(fresh_entry["is_stale"])
        self.assertLessEqual(fresh_entry["age_seconds"], Config.STALE_THRESHOLD_SECONDS)

        stale_raw = {
            "entry_id": "2",
            "created_at": (datetime.now(timezone.utc) - timedelta(seconds=120)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "field6": "0",
        }
        stale_entry = self.service.normalize_entry(stale_raw)
        self.assertTrue(stale_entry["is_stale"])

    @patch("requests.get")
    def test_fetch_feeds_caching(self, mock_get):
        """Verify repeated calls within TTL return cached data without extra network calls."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "channel": {"id": 12345},
            "feeds": [{"entry_id": 1, "created_at": "2026-10-18T12:00:00Z", "field1": "500"}]
        }
        mock_get.return_value = mock_resp

        # Force configured channel
        self.service.config.THINGSPEAK_CHANNEL_ID = "12345"

        res1 = self.service.fetch_feeds(results=50)
        self.assertTrue(res1["success"])
        self.assertFalse(res1["cached"])

        # Second call should use cache
        res2 = self.service.fetch_feeds(results=50)
        self.assertTrue(res2["success"])
        self.assertTrue(res2["cached"])
        self.assertEqual(mock_get.call_count, 1)

    @patch("requests.get")
    def test_fetch_error_handling(self, mock_get):
        """Verify graceful error reporting on network failure."""
        mock_get.side_effect = Exception("Connection refused")
        self.service.config.THINGSPEAK_CHANNEL_ID = "12345"

        res = self.service.fetch_feeds(results=10, force_refresh=True)
        self.assertFalse(res["success"])
        self.assertIn("error", res)
        self.assertIsNotNone(res["error"])


if __name__ == "__main__":
    unittest.main()
