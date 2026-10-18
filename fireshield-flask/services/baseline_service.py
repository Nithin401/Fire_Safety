from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from config import Config


class BaselineService:
    """Service to compute statistical room-temperature and humidity baselines and detect anomalies."""

    BASELINE_MODEL_PATH = Config.DATA_MODELS_DIR / "room_baseline.json"

    def __init__(self, config: type[Config] = Config):
        self.config = config
        self.config.DATA_MODELS_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def clean_telemetry_series(cls, df: pd.DataFrame) -> pd.DataFrame:
        """Sort chronologically, deduplicate by entry_id, parse timestamps, and filter valid ranges."""
        if df.empty:
            return df

        cleaned = df.copy()
        # Handle column aliases
        if "temperature_c" not in cleaned.columns:
            if "temperature" in cleaned.columns:
                cleaned["temperature_c"] = pd.to_numeric(cleaned["temperature"], errors="coerce")
            elif "field3" in cleaned.columns:
                cleaned["temperature_c"] = pd.to_numeric(cleaned["field3"], errors="coerce")
        if "humidity_pct" not in cleaned.columns:
            if "humidity" in cleaned.columns:
                cleaned["humidity_pct"] = pd.to_numeric(cleaned["humidity"], errors="coerce")
            elif "field4" in cleaned.columns:
                cleaned["humidity_pct"] = pd.to_numeric(cleaned["field4"], errors="coerce")
        if "created_at" not in cleaned.columns and "timestamp" in cleaned.columns:
            cleaned["created_at"] = cleaned["timestamp"]

        if "created_dt" not in cleaned.columns:
            cleaned["created_dt"] = pd.to_datetime(cleaned.get("created_at"), errors="coerce", utc=True)

        cleaned = cleaned.dropna(subset=["created_dt"])
        cleaned = cleaned.sort_values(by="created_dt")

        if "entry_id" in cleaned.columns:
            cleaned = cleaned.drop_duplicates(subset=["entry_id"])

        # Filter physically plausible ranges for room DHT11 (temp: -10C to 60C, humidity: 0% to 100%)
        if "temperature_c" in cleaned.columns:
            cleaned.loc[(cleaned["temperature_c"] < -10) | (cleaned["temperature_c"] > 60), "temperature_c"] = np.nan
        if "humidity_pct" in cleaned.columns:
            cleaned.loc[(cleaned["humidity_pct"] < 0) | (cleaned["humidity_pct"] > 100), "humidity_pct"] = np.nan

        return cleaned

    def compute_baseline(
        self,
        df: pd.DataFrame,
        room_name: str = "Default Room",
        exclude_fire_records: bool = True,
    ) -> Dict[str, Any]:
        """Compute interpretable statistical baseline metrics for temperature and humidity."""
        cleaned = self.clean_telemetry_series(df)

        if exclude_fire_records and "fire_status" in cleaned.columns:
            # Exclude records where hardware fire status was active to learn non-fire baseline
            usable = cleaned[cleaned["fire_status"] != 1]
        else:
            usable = cleaned

        temp_series = usable["temperature_c"].dropna()
        hum_series = usable["humidity_pct"].dropna()

        obs_count = len(usable)
        valid_temp_count = len(temp_series)
        valid_hum_count = len(hum_series)

        if valid_temp_count < 5:
            return {
                "success": False,
                "error": f"Insufficient valid temperature data (minimum 5 readings required, found {valid_temp_count}).",
                "observations": obs_count,
                "usable_temperatures": valid_temp_count,
            }

        start_time = usable["created_dt"].min().isoformat() if not usable.empty else None
        end_time = usable["created_dt"].max().isoformat() if not usable.empty else None

        # Statistical calculations for Temperature
        temp_mean = float(temp_series.mean())
        temp_median = float(temp_series.median())
        temp_std = float(temp_series.std()) if len(temp_series) > 1 else 0.0
        temp_min = float(temp_series.min())
        temp_max = float(temp_series.max())
        temp_p05 = float(np.percentile(temp_series, 5))
        temp_p25 = float(np.percentile(temp_series, 25))
        temp_p75 = float(np.percentile(temp_series, 75))
        temp_p95 = float(np.percentile(temp_series, 95))

        # Humidity metrics
        hum_mean = float(hum_series.mean()) if valid_hum_count > 0 else None
        hum_median = float(hum_series.median()) if valid_hum_count > 0 else None
        hum_std = float(hum_series.std()) if valid_hum_count > 1 else (0.0 if valid_hum_count == 1 else None)
        hum_min = float(hum_series.min()) if valid_hum_count > 0 else None
        hum_max = float(hum_series.max()) if valid_hum_count > 0 else None

        # Hourly diurnal pattern (if span covers multiple hours)
        hourly_pattern = {}
        if "created_dt" in usable.columns and valid_temp_count >= 20:
            usable_with_hour = usable.copy()
            usable_with_hour["hour"] = usable_with_hour["created_dt"].dt.hour
            hourly_stats = usable_with_hour.groupby("hour")["temperature_c"].agg(["mean", "std", "count"]).dropna()
            for hour, row in hourly_stats.iterrows():
                hourly_pattern[int(hour)] = {
                    "mean_temp": round(float(row["mean"]), 2),
                    "std_temp": round(float(row["std"]), 2) if not np.isnan(row["std"]) else 0.0,
                    "count": int(row["count"]),
                }

        baseline_data = {
            "success": True,
            "room_name": room_name,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "time_range": {
                "start": start_time,
                "end": end_time,
            },
            "observations": {
                "total_rows": obs_count,
                "valid_temperatures": valid_temp_count,
                "valid_humidities": valid_hum_count,
            },
            "temperature_baseline": {
                "mean": round(temp_mean, 2),
                "median": round(temp_median, 2),
                "std": round(temp_std, 2),
                "min": round(temp_min, 2),
                "max": round(temp_max, 2),
                "percentiles": {
                    "p05": round(temp_p05, 2),
                    "p25": round(temp_p25, 2),
                    "p75": round(temp_p75, 2),
                    "p95": round(temp_p95, 2),
                },
                "normal_band_2sigma": [
                    round(max(temp_mean - 2 * temp_std, temp_min), 2),
                    round(min(temp_mean + 2 * temp_std, temp_max), 2),
                ],
            },
            "humidity_baseline": {
                "mean": round(hum_mean, 2) if hum_mean is not None else None,
                "median": round(hum_median, 2) if hum_median is not None else None,
                "std": round(hum_std, 2) if hum_std is not None else None,
                "min": round(hum_min, 2) if hum_min is not None else None,
                "max": round(hum_max, 2) if hum_max is not None else None,
            },
            "hourly_pattern": hourly_pattern,
            "disclaimer": (
                "Anomalies indicate environmental deviation from learned baseline, "
                "NOT confirmed fire. Weather, occupancy, doors, or appliances routinely alter room baseline."
            ),
        }

        # Save to disk
        self.save_baseline(baseline_data)
        return baseline_data

    def save_baseline(self, baseline_data: Dict[str, Any]) -> None:
        self.BASELINE_MODEL_PATH.write_text(json.dumps(baseline_data, indent=2), encoding="utf-8")

    def load_baseline(self) -> Optional[Dict[str, Any]]:
        if not self.BASELINE_MODEL_PATH.exists():
            return None
        try:
            return json.loads(self.BASELINE_MODEL_PATH.read_text(encoding="utf-8"))
        except Exception:
            return None

    @classmethod
    def evaluate_anomalies(
        cls,
        df: pd.DataFrame,
        baseline: Dict[str, Any],
        z_threshold: float = 2.5,
    ) -> pd.DataFrame:
        """Annotate a dataframe with temperature z-scores and anomaly flags."""
        result = df.copy()
        temp_mean = baseline.get("temperature_baseline", {}).get("mean")
        temp_std = baseline.get("temperature_baseline", {}).get("std", 1.0)
        if temp_std == 0:
            temp_std = 1.0

        if temp_mean is not None and "temperature_c" in result.columns:
            result["temp_zscore"] = (result["temperature_c"] - temp_mean) / temp_std
            result["is_temp_anomaly"] = result["temp_zscore"].abs() > z_threshold
        else:
            result["temp_zscore"] = np.nan
            result["is_temp_anomaly"] = False

        return result
