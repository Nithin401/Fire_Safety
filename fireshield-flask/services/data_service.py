from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from config import Config


class DataService:
    """Service for tabular data operations, CSV export/import, and normalization."""

    RAW_COLUMNS = ["entry_id", "created_at", "field1", "field2", "field3", "field4", "field5", "field6"]
    PROCESSED_COLUMNS = [
        "entry_id",
        "created_at",
        "flame_raw",
        "smoke_status",
        "temperature_c",
        "humidity_pct",
        "servo_angle",
        "fire_status",
        "fire_label",
    ]

    def __init__(self, config: type[Config] = Config):
        self.config = config
        self.config.DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
        self.config.DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        self.config.DATA_LABELS_DIR.mkdir(parents=True, exist_ok=True)
        self.config.DATA_MODELS_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def feeds_to_dataframe(cls, feeds: List[Dict[str, Any]]) -> pd.DataFrame:
        """Convert a list of normalized feeds to a structured pandas DataFrame."""
        if not feeds:
            return pd.DataFrame(columns=cls.PROCESSED_COLUMNS)

        records = []
        for f in feeds:
            records.append({
                "entry_id": f.get("entry_id"),
                "created_at": f.get("created_at"),
                "field1": f.get("field1"),
                "field2": f.get("field2"),
                "field3": f.get("field3"),
                "field4": f.get("field4"),
                "field5": f.get("field5"),
                "field6": f.get("field6"),
                "flame_raw": f.get("flame_raw"),
                "smoke_status": f.get("smoke_status"),
                "temperature_c": f.get("temperature_c"),
                "humidity_pct": f.get("humidity_pct"),
                "servo_angle": f.get("servo_angle"),
                "fire_status": f.get("fire_status"),
                "fire_label": f.get("fire_label", "UNKNOWN"),
            })

        df = pd.DataFrame(records)
        df["created_dt"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
        return df

    @classmethod
    def export_raw_csv_string(cls, feeds: List[Dict[str, Any]]) -> str:
        """Export raw ThingSpeak records string without altering raw fields."""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=cls.RAW_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for f in feeds:
            writer.writerow({
                "entry_id": f.get("entry_id", ""),
                "created_at": f.get("created_at", ""),
                "field1": f.get("field1", ""),
                "field2": f.get("field2", ""),
                "field3": f.get("field3", ""),
                "field4": f.get("field4", ""),
                "field5": f.get("field5", ""),
                "field6": f.get("field6", ""),
            })
        return output.getvalue()

    @classmethod
    def export_processed_csv_string(cls, feeds: List[Dict[str, Any]]) -> str:
        """Export processed records with derived sensor columns."""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=cls.PROCESSED_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for f in feeds:
            writer.writerow({
                "entry_id": f.get("entry_id", ""),
                "created_at": f.get("created_at", ""),
                "flame_raw": f.get("flame_raw", ""),
                "smoke_status": f.get("smoke_status", ""),
                "temperature_c": f.get("temperature_c", ""),
                "humidity_pct": f.get("humidity_pct", ""),
                "servo_angle": f.get("servo_angle", ""),
                "fire_status": f.get("fire_status", ""),
                "fire_label": f.get("fire_label", ""),
            })
        return output.getvalue()

    def save_feeds(
        self,
        feeds: List[Dict[str, Any]],
        channel_id: str,
        tag: str = "",
    ) -> Tuple[Path, Path]:
        """Save both raw and processed CSV files to disk with deduplication."""
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        suffix = f"_{tag}" if tag else ""
        raw_filename = f"thingspeak_{channel_id}_{timestamp_str}{suffix}_raw.csv"
        proc_filename = f"thingspeak_{channel_id}_{timestamp_str}{suffix}_processed.csv"

        raw_path = self.config.DATA_RAW_DIR / raw_filename
        proc_path = self.config.DATA_PROCESSED_DIR / proc_filename

        raw_content = self.export_raw_csv_string(feeds)
        raw_path.write_text(raw_content, encoding="utf-8")

        proc_content = self.export_processed_csv_string(feeds)
        proc_path.write_text(proc_content, encoding="utf-8")

        return raw_path, proc_path

    @classmethod
    def filter_feeds(
        cls,
        feeds: List[Dict[str, Any]],
        fire_status_filter: Optional[int] = None,
        start_dt: Optional[datetime] = None,
        end_dt: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Filter feeds by hardware fire status and/or time bounds."""
        filtered = []
        for f in feeds:
            if fire_status_filter is not None and f.get("fire_status") != fire_status_filter:
                continue

            created_raw = f.get("created_at")
            if (start_dt or end_dt) and created_raw:
                try:
                    dt = pd.to_datetime(created_raw, utc=True)
                    if start_dt and dt < start_dt:
                        continue
                    if end_dt and dt > end_dt:
                        continue
                except Exception:
                    pass

            filtered.append(f)
        return filtered

    @classmethod
    def parse_uploaded_csv(cls, file_content: str) -> Dict[str, Any]:
        """Inspect and parse an uploaded CSV file safely."""
        try:
            df = pd.read_csv(io.StringIO(file_content))
            columns = list(df.columns)
            row_count = len(df)
            missing_summary = df.isnull().sum().to_dict()

            # Detect if it's raw ThingSpeak format or processed format
            is_thingspeak_raw = all(c in columns for c in ["field1", "field2", "field3", "field4"])
            is_processed = all(c in columns for c in ["temperature_c", "humidity_pct"])

            sample = df.head(10).to_dict(orient="records")

            return {
                "success": True,
                "columns": columns,
                "row_count": row_count,
                "missing_summary": missing_summary,
                "is_thingspeak_raw": is_thingspeak_raw,
                "is_processed": is_processed,
                "sample": sample,
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "columns": [],
                "row_count": 0,
                "missing_summary": {},
                "is_thingspeak_raw": False,
                "is_processed": False,
                "sample": [],
                "error": f"Failed to parse CSV: {str(e)}",
            }
