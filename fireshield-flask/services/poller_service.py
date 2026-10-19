from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from config import Config
from services.alert_service import AlertService
from services.baseline_service import BaselineService
from services.event_store import EventStore
from services.thingspeak_service import ThingSpeakService

logger = logging.getLogger(__name__)


class ThingSpeakPoller:
    """Continuous background daemon polling ThingSpeak, evaluating risk, and delivering alerts."""

    def __init__(
        self,
        config=None,
        ts_service: Optional[ThingSpeakService] = None,
        alert_service: Optional[AlertService] = None,
        baseline_service: Optional[BaselineService] = None,
        event_store: Optional[EventStore] = None,
    ):
        self.config = config or Config
        self.ts_service = ts_service or ThingSpeakService(config=self.config)
        self.event_store = event_store or EventStore()
        self.alert_service = alert_service or AlertService(config=self.config, event_store=self.event_store)
        self.baseline_service = baseline_service or BaselineService(config=self.config)

        self.interval = self.config.POLL_INTERVAL_SECONDS
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start poller daemon thread if not already running."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="ThingSpeakPollerThread")
        self._thread.start()
        logger.info(f"ThingSpeak poller daemon started (Interval: {self.interval}s)")

    def stop(self) -> None:
        """Signal poller thread to stop."""
        self._running = False

    def _run_loop(self) -> None:
        """Poller loop running in background."""
        while self._running:
            try:
                self.tick()
            except Exception as e:
                logger.error(f"Error in ThingSpeak poller tick: {e}", exc_info=True)

            # Sleep in 1-second slices so thread stops promptly on shutdown
            for _ in range(max(1, self.interval)):
                if not self._running:
                    break
                time.sleep(1)

    def tick(self) -> Optional[dict]:
        """Execute one polling cycle."""
        if not self.ts_service.is_configured():
            return None

        # 1. Fetch latest reading
        res = self.ts_service.fetch_latest_reading(force_refresh=True)
        if not res.get("success") or not res.get("reading"):
            return None

        reading = res["reading"]
        entry_id = reading.get("entry_id")
        if entry_id is None:
            return None

        # 2. Check if this entry was already evaluated
        last_id = self.event_store.get_last_processed_entry_id()
        if last_id is not None and entry_id <= last_id:
            # Entry already processed, check outbox retries instead
            self.alert_service.process_outbox()
            return None

        # 3. New valid entry! Update last processed entry id
        self.event_store.set_last_processed_entry_id(entry_id)

        # 4. Evaluate risk and alert
        baseline = self.baseline_service.get_baseline()
        alert_res = self.alert_service.evaluate_and_alert(reading, baseline=baseline)

        # 5. Process any retries in the outbox
        self.alert_service.process_outbox()

        return alert_res
