from __future__ import annotations

import unittest
from unittest.mock import patch

from app import create_app
from config import Config


class TestApiEndpoints(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    def test_health_endpoint(self):
        """Test GET /api/health returns healthy JSON."""
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("thingspeak_configured", data)

    def test_status_endpoint(self):
        """Test GET /api/status returns operational parameters."""
        resp = self.client.get("/api/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertIn("stale_threshold_seconds", data)

    @patch("services.thingspeak_service.ThingSpeakService.fetch_latest_reading")
    def test_latest_reading_endpoint(self, mock_fetch):
        """Test GET /api/readings/latest delivers 6-field payload."""
        mock_fetch.return_value = {
            "success": True,
            "reading": {
                "entry_id": 99,
                "created_at": "2026-10-18T10:00:00Z",
                "flame_raw": 550.0,
                "smoke_status": 1,
                "temperature_c": 30.5,
                "humidity_pct": 45.0,
                "servo_angle": 120.0,
                "fire_status": 1,
                "fire_label": "HARDWARE_TRIGGERED",
                "is_stale": False,
                "age_seconds": 12.0,
            },
            "error": None,
        }

        resp = self.client.get("/api/readings/latest")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        reading = data["reading"]
        self.assertEqual(reading["flame_raw"], 550.0)
        self.assertEqual(reading["fire_status"], 1)

    @patch("services.thingspeak_service.ThingSpeakService.fetch_feeds")
    def test_graphs_summary_endpoint(self, mock_feeds):
        """Test GET /api/graphs/summary downsamples all 6 fields."""
        mock_feeds.return_value = {
            "success": True,
            "normalized_feeds": [
                {
                    "entry_id": 1,
                    "created_at": "2026-10-18T10:00:00Z",
                    "flame_raw": 650.0,
                    "smoke_status": 0,
                    "temperature_c": 26.0,
                    "humidity_pct": 50.0,
                    "servo_angle": 90.0,
                    "fire_status": 0,
                }
            ],
            "error": None,
        }

        resp = self.client.get("/api/graphs/summary")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["count"], 1)
        fields = data["fields"]
        self.assertEqual(fields["flame"], [650.0])
        self.assertEqual(fields["fire_status"], [0])


if __name__ == "__main__":
    unittest.main()
