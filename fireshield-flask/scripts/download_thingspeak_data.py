from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
CURRENT_DIR = Path(__file__).resolve().parent
FLASK_ROOT = CURRENT_DIR.parent
if str(FLASK_ROOT) not in sys.path:
    sys.path.insert(0, str(FLASK_ROOT))

from config import Config
from services.data_service import DataService
from services.thingspeak_service import ThingSpeakService


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download historical telemetry feeds from ThingSpeak channel."
    )
    parser.add_argument("--channel-id", type=str, default="", help="ThingSpeak Channel ID (overrides .env)")
    parser.add_argument("--api-key", type=str, default="", help="ThingSpeak Read API Key (overrides .env)")
    parser.add_argument("--limit", type=int, default=500, help="Maximum number of records to retrieve (default: 500)")
    parser.add_argument("--start", type=str, default=None, help="Start timestamp (YYYY-MM-DD or ISO)")
    parser.add_argument("--end", type=str, default=None, help="End timestamp (YYYY-MM-DD or ISO)")
    parser.add_argument("--output-dir", type=str, default=None, help="Directory to save CSV files")
    args = parser.parse_args()

    channel_id = args.channel_id or Config.THINGSPEAK_CHANNEL_ID
    read_key = args.api_key or Config.THINGSPEAK_READ_API_KEY

    if not channel_id:
        print("ERROR: ThingSpeak Channel ID is not set. Please supply via --channel-id or in .env.")
        return 1

    print(f"Connecting to ThingSpeak Channel ID: {channel_id}...")
    if read_key:
        print("Using provided Read API Key (masked for security).")
    else:
        print("No Read API Key provided (assuming public channel).")

    # Override config dynamically for this run
    class CustomConfig(Config):
        THINGSPEAK_CHANNEL_ID = channel_id
        THINGSPEAK_READ_API_KEY = read_key

    ts_service = ThingSpeakService(config=CustomConfig)
    data_service = DataService(config=CustomConfig)

    feeds_res = ts_service.fetch_feeds(
        results=args.limit,
        start=args.start,
        end=args.end,
        force_refresh=True,
    )

    if not feeds_res.get("success"):
        print(f"FAILED: ThingSpeak fetch error: {feeds_res.get('error')}")
        return 1

    normalized_feeds = feeds_res.get("normalized_feeds", [])
    raw_feeds = feeds_res.get("raw_feeds", [])
    record_count = len(normalized_feeds)

    if record_count == 0:
        print("WARNING: Zero records returned from ThingSpeak channel.")
        return 0

    print(f"Successfully retrieved {record_count} feed records.")

    raw_path, proc_path = data_service.save_feeds(
        feeds=normalized_feeds,
        channel_id=channel_id,
        tag=datetime.now(timezone.utc).strftime("%Y%m%d"),
    )

    # Save retrieval metadata
    meta = {
        "channel_id": channel_id,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "record_count": record_count,
        "raw_csv_file": str(raw_path.name),
        "processed_csv_file": str(proc_path.name),
        "channel_info": feeds_res.get("channel", {}),
    }
    meta_path = raw_path.with_suffix(".json")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"Saved Raw CSV:       {raw_path}")
    print(f"Saved Processed CSV: {proc_path}")
    print(f"Saved Metadata JSON: {meta_path}")
    print(f"Completed download of {record_count} entries without modifying raw values.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
