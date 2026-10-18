from __future__ import annotations

import argparse
import sys
from pathlib import Path
import pandas as pd

# Add project root to path
CURRENT_DIR = Path(__file__).resolve().parent
FLASK_ROOT = CURRENT_DIR.parent
if str(FLASK_ROOT) not in sys.path:
    sys.path.insert(0, str(FLASK_ROOT))

from config import Config
from services.baseline_service import BaselineService
from services.data_service import DataService
from services.thingspeak_service import ThingSpeakService


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train room-temperature baseline environmental model."
    )
    parser.add_argument("--csv", type=str, default=None, help="Path to local CSV dataset to train on")
    parser.add_argument("--room", type=str, default="Living Room", help="Target room label")
    parser.add_argument("--limit", type=int, default=500, help="Max records if fetching from ThingSpeak")
    args = parser.parse_args()

    baseline_service = BaselineService()

    if args.csv:
        csv_path = Path(args.csv)
        if not csv_path.exists():
            print(f"ERROR: Specified CSV file not found at {csv_path}")
            return 1
        print(f"Loading telemetry data from {csv_path}...")
        df = pd.read_csv(csv_path)
    else:
        print("Fetching telemetry data from ThingSpeak channel...")
        ts_service = ThingSpeakService()
        if not ts_service.is_configured():
            print("ERROR: ThingSpeak Channel ID is not set. Configure .env or provide --csv <path>.")
            return 1
        res = ts_service.fetch_feeds(results=args.limit)
        if not res.get("success"):
            print(f"FAILED: {res.get('error')}")
            return 1
        data_service = DataService()
        df = data_service.feeds_to_dataframe(res.get("normalized_feeds", []))

    print(f"Analyzing {len(df)} telemetry rows for baseline model...")
    baseline_result = baseline_service.compute_baseline(df, room_name=args.room)

    if not baseline_result.get("success"):
        print(f"FAILED: {baseline_result.get('error')}")
        return 1

    temp_base = baseline_result["temperature_baseline"]
    print("\n=== Room Temperature Baseline Learned ===")
    print(f"Room:               {baseline_result['room_name']}")
    print(f"Observations:       {baseline_result['observations']['valid_temperatures']}")
    print(f"Mean Temperature:   {temp_base['mean']} °C")
    print(f"Median Temperature: {temp_base['median']} °C")
    print(f"Std Deviation:      ±{temp_base['std']} °C")
    print(f"Observed Range:     [{temp_base['min']} °C, {temp_base['max']} °C]")
    print(f"2-Sigma Normal Band:[{temp_base['normal_band_2sigma'][0]} °C, {temp_base['normal_band_2sigma'][1]} °C]")
    print(f"Saved Model File:   {BaselineService.BASELINE_MODEL_PATH}")
    print("\nNote: Baseline variation indicates environmental change, not confirmed fire.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
