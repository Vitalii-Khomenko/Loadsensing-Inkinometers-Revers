"""Background acquisition loop for a directly attached TIL90 sensor."""

from __future__ import annotations

from copy import deepcopy
import threading
import time
from typing import Any

from tools.alert_engine import evaluate_health, evaluate_missing_data, evaluate_sample
from tools.monitoring_store import DEFAULT_MONITOR_CONFIG, MonitoringStore


RECONNECT_RETRY_SECONDS = 2


class MonitoringService:
    """Poll live and health data without overlapping other serial transactions."""

    def __init__(self, device: Any, store: MonitoringStore) -> None:
        self.device, self.store = device, store
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._last_success_utc: str | None = None
        self._last_error: str | None = None
        self._next_measurement_epoch: int | None = None
        self._next_health_epoch: int | None = None

    def config(self) -> dict[str, Any]:
        stored = self.store.get_monitor_config()
        merged = deepcopy(DEFAULT_MONITOR_CONFIG)
        merged.update({k: v for k, v in stored.items() if k != "alerts"})
        merged["alerts"].update(stored.get("alerts", {}))
        return merged

    @staticmethod
    def validate_config(config: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(DEFAULT_MONITOR_CONFIG)
        result.update({k: v for k, v in config.items() if k != "alerts"})
        result["alerts"].update(config.get("alerts", {}))
        if not 10 <= int(result["measurement_interval_seconds"]) <= 86400:
            raise ValueError("measurement interval must be between 10 and 86400 seconds")
        if not 30 <= int(result["health_interval_seconds"]) <= 86400:
            raise ValueError("health interval must be between 30 and 86400 seconds")
        if not 1 <= int(result["retention_days"]) <= 3650:
            raise ValueError("retention must be between 1 and 3650 days")
        for key, value in result["alerts"].items():
            if key == "sensor_error":
                continue
            if value is not None and float(value) < 0:
                raise ValueError(f"alert threshold {key} must not be negative")
        return result

    def update_config(self, config: dict[str, Any]) -> dict[str, Any]:
        config = self.validate_config(config)
        self.store.set_monitor_config(config)
        if config["enabled"]:
            self.start()
        else:
            self.stop()
        return self.status()

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="til90-monitor", daemon=True)
            self._thread.start()

    def stop(self, timeout: float = 5) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout)

    def status(self) -> dict[str, Any]:
        thread = self._thread
        device_status = self.device.status()
        if not device_status.get("device_detected"):
            connection_state = "waiting"
        elif self._last_error:
            connection_state = "retrying"
        elif self._last_success_utc:
            connection_state = "connected"
        else:
            connection_state = "connecting"
        return {
            "running": bool(thread and thread.is_alive() and not self._stop.is_set()),
            "connection_state": connection_state,
            "device": device_status,
            "config": self.config(),
            "last_success_utc": self._last_success_utc,
            "last_error": self._last_error,
            "next_measurement_epoch": self._next_measurement_epoch,
            "next_health_epoch": self._next_health_epoch,
            "latest_sample": self.store.latest_sample(),
            "latest_health": self.store.latest_health(),
            "storage": self.store.summary(),
        }

    def _store_result(self, result: dict[str, Any], source: str) -> None:
        if result.get("status") != "ok":
            raise RuntimeError(f"{result.get('query', 'read')} returned {result.get('status')}")
        previous = self.store.latest_sample()
        kind, inserted = self.store.insert_record(result, source)
        rules = self.config()["alerts"]
        if kind == "sample" and inserted:
            current = self.store.latest_sample()
            if current:
                evaluate_sample(self.store, current, previous, rules)
        elif kind == "health" and inserted:
            current = self.store.latest_health()
            if current:
                evaluate_health(self.store, current, rules)

    def ingest(self, results: list[dict[str, Any]], source: str = "manual") -> None:
        """Persist supported results obtained outside the background loop."""
        for result in results:
            if result.get("query") in {"live", "health"} and result.get("status") == "ok":
                self._store_result(result, source)

    def _run(self) -> None:
        next_measurement = next_health = 0.0
        cleanup_at = 0.0
        while not self._stop.is_set():
            config = self.config()
            if not config["enabled"]:
                break
            now = time.time()
            self._next_measurement_epoch = int(next_measurement) if next_measurement else int(now)
            self._next_health_epoch = int(next_health) if next_health else int(now)
            try:
                did_work = False
                if now >= next_measurement:
                    self._store_result(self.device.read("live")[0], "live")
                    next_measurement = time.time() + int(config["measurement_interval_seconds"])
                    did_work = True
                if now >= next_health:
                    self._store_result(self.device.read("health")[0], "live")
                    next_health = time.time() + int(config["health_interval_seconds"])
                    did_work = True
                evaluate_missing_data(self.store, config["alerts"])
                if now >= cleanup_at:
                    self.store.cleanup(int(config["retention_days"]))
                    cleanup_at = now + 86400
                if did_work:
                    from tools.monitoring_store import utc_now
                    self._last_success_utc, self._last_error = utc_now(), None
            except Exception as exc:
                self._last_error = f"{type(exc).__name__}: {exc}"
                next_measurement = max(
                    next_measurement, time.time() + RECONNECT_RETRY_SECONDS
                )
                next_health = max(next_health, time.time() + RECONNECT_RETRY_SECONDS)
            self._stop.wait(min(1, RECONNECT_RETRY_SECONDS))
