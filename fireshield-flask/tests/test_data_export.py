from __future__ import annotations

import unittest
import pandas as pd

from services.data_service import DataService


class TestDataService(unittest.TestCase):

    def test_raw_csv_export_preserves_field_names(self):
        """Rule: Raw ThingSpeak CSV export must strictly preserve field1..field6 columns."""
        feeds = [
            {
                "entry_id": 10,
                "created_at": "2026-10-18T10:00:00Z",
                "field1": "450",
                "field2": "0",
                "field3": "27.5",
                "field4": "60.0",
                "field5": "90",
                "field6": "0",
            }
        ]
        csv_str = DataService.export_raw_csv_string(feeds)
        header = csv_str.splitlines()[0]
        self.assertIn("field1,field2,field3,field4,field5,field6", header)
        self.assertNotIn("flame_raw", header)

    def test_processed_csv_export_has_mapped_columns(self):
        """Processed CSV should contain derived columns."""
        feeds = [
            {
                "entry_id": 10,
                "created_at": "2026-10-18T10:00:00Z",
                "flame_raw": 450.0,
                "smoke_status": 0,
                "temperature_c": 27.5,
                "humidity_pct": 60.0,
                "servo_angle": 90.0,
                "fire_status": 0,
                "fire_label": "NOT_TRIGGERED",
            }
        ]
        csv_str = DataService.export_processed_csv_string(feeds)
        header = csv_str.splitlines()[0]
        self.assertIn("flame_raw", header)
        self.assertIn("temperature_c", header)
        self.assertIn("fire_label", header)

    def test_filter_feeds_by_fire_status(self):
        feeds = [
            {"entry_id": 1, "fire_status": 0},
            {"entry_id": 2, "fire_status": 1},
            {"entry_id": 3, "fire_status": 0},
        ]
        filtered = DataService.filter_feeds(feeds, fire_status_filter=1)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["entry_id"], 2)


if __name__ == "__main__":
    unittest.main()
