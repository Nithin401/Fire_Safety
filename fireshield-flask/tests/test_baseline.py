from __future__ import annotations

import unittest
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np

from services.baseline_service import BaselineService


class TestBaselineService(unittest.TestCase):

    def setUp(self):
        self.service = BaselineService()

    def test_compute_baseline_statistics(self):
        """Test statistical baseline calculations on known distribution."""
        base_time = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)
        records = []
        # Generate 20 readings around 25.0 C and 50.0% humidity
        temps = [24.0, 24.5, 25.0, 25.5, 26.0] * 4
        hums = [48.0, 49.0, 50.0, 51.0, 52.0] * 4

        for i, (t, h) in enumerate(zip(temps, hums)):
            records.append({
                "entry_id": i + 1,
                "created_at": (base_time + timedelta(seconds=16 * i)).isoformat(),
                "temperature_c": t,
                "humidity_pct": h,
                "fire_status": 0,
            })

        df = pd.DataFrame(records)
        res = self.service.compute_baseline(df, room_name="Test Lab")

        self.assertTrue(res["success"])
        t_base = res["temperature_baseline"]
        self.assertAlmostEqual(t_base["mean"], 25.0, places=1)
        self.assertAlmostEqual(t_base["median"], 25.0, places=1)
        self.assertEqual(t_base["min"], 24.0)
        self.assertEqual(t_base["max"], 26.0)
        self.assertEqual(res["observations"]["valid_temperatures"], 20)

    def test_insufficient_data_rejection(self):
        """Rule: Do not compute or fabricate baselines on insufficient data (< 5 samples)."""
        df = pd.DataFrame([
            {"entry_id": 1, "created_at": "2026-10-18T10:00:00Z", "temperature_c": 25.0, "humidity_pct": 50.0},
            {"entry_id": 2, "created_at": "2026-10-18T10:00:16Z", "temperature_c": 25.2, "humidity_pct": 50.1},
        ])
        res = self.service.compute_baseline(df)
        self.assertFalse(res["success"])
        self.assertIn("Insufficient", res["error"])

    def test_anomaly_detection_scoring(self):
        """Test that readings outside 2.5 sigma are flagged as anomalies."""
        baseline = {
            "temperature_baseline": {
                "mean": 25.0,
                "std": 1.0,
            }
        }
        df = pd.DataFrame([
            {"temperature_c": 25.2},  # Normal
            {"temperature_c": 28.5},  # Anomaly: z = 3.5 > 2.5
        ])
        annotated = self.service.evaluate_anomalies(df, baseline, z_threshold=2.5)
        self.assertFalse(annotated.loc[0, "is_temp_anomaly"])
        self.assertTrue(annotated.loc[1, "is_temp_anomaly"])


if __name__ == "__main__":
    unittest.main()
