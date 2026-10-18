from __future__ import annotations

import unittest
import pandas as pd

from services.ml_service import MLService


class TestMLService(unittest.TestCase):

    def setUp(self):
        self.service = MLService()

    def test_prevent_field6_as_fire_ground_truth(self):
        """Rule: Never allow field6/fire_status alone as supervised ground truth."""
        df = pd.DataFrame([
            {"temperature_c": 25.0, "flame_raw": 500, "fire_status": 0},
            {"temperature_c": 35.0, "flame_raw": 200, "fire_status": 1},
        ])
        res = self.service.train_classifier(
            df=df,
            feature_cols=["temperature_c", "flame_raw"],
            label_col="fire_status",
        )
        self.assertFalse(res["success"])
        self.assertIn("field6 represents the ESP8266 hardware rule", res["error"])

    def test_insufficient_samples_rejection(self):
        """Rule: Reject training when class sample counts are sparse (< 5 samples per class)."""
        df = pd.DataFrame([
            {"temperature_c": 25.0, "flame_raw": 700, "verified_label": "NORMAL"},
            {"temperature_c": 25.1, "flame_raw": 710, "verified_label": "NORMAL"},
            {"temperature_c": 38.0, "flame_raw": 150, "verified_label": "FIRE"},  # Only 1 sample
        ])
        res = self.service.train_classifier(
            df=df,
            feature_cols=["temperature_c", "flame_raw"],
            label_col="verified_label",
        )
        self.assertFalse(res["success"])
        self.assertIn("Insufficient samples", res["error"])

    def test_valid_supervised_training_with_labels(self):
        """Verify reproducible training when verified ground-truth labels meet quota."""
        # 10 NORMAL and 10 FIRE
        records = []
        for i in range(10):
            records.append({"temperature_c": 24.0 + i * 0.1, "flame_raw": 800 + i, "verified_label": "NORMAL"})
            records.append({"temperature_c": 45.0 + i * 0.5, "flame_raw": 100 + i, "verified_label": "FIRE"})

        df = pd.DataFrame(records)
        res = self.service.train_classifier(
            df=df,
            feature_cols=["temperature_c", "flame_raw"],
            label_col="verified_label",
            model_type="logistic_regression",
            test_size=0.3,
            random_state=42,
        )
        self.assertTrue(res["success"])
        self.assertIn("metrics_per_class", res)
        self.assertIn("NORMAL", res["metrics_per_class"])
        self.assertIn("FIRE", res["metrics_per_class"])


if __name__ == "__main__":
    unittest.main()
