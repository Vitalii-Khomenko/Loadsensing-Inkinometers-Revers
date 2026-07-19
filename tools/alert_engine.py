"""Evaluate local threshold, rate, battery, error, and missing-data alerts."""

from __future__ import annotations

import time
from typing import Any

from tools.monitoring_store import MonitoringStore


def evaluate_sample(
    store: MonitoringStore, sample: dict[str, Any], previous: dict[str, Any] | None,
    rules: dict[str, Any],
) -> None:
    node_id, timestamp = int(sample["node_id"]), int(sample["timestamp"])
    for axis in "xyz":
        value, threshold = sample.get(f"{axis}_deg"), rules.get(f"{axis}_absolute_deg")
        active = threshold is not None and value is not None and abs(value) >= threshold
        store.set_alert(
            node_id, f"{axis}_absolute", active,
            f"{axis.upper()} tilt is {value:.4f} degrees" if value is not None else f"{axis.upper()} tilt unavailable",
            abs(value) if value is not None else None, threshold, timestamp,
        )
    rate_limit = rules.get("rate_deg_per_minute")
    for axis in "xyz":
        rate = None
        if rate_limit is not None and previous and sample.get(f"{axis}_deg") is not None:
            elapsed = timestamp - int(previous["timestamp"])
            if elapsed > 0 and previous.get(f"{axis}_deg") is not None:
                rate = abs(sample[f"{axis}_deg"] - previous[f"{axis}_deg"]) * 60 / elapsed
        store.set_alert(
            node_id, f"{axis}_rate", rate_limit is not None and rate is not None and rate >= rate_limit,
            f"{axis.upper()} changed at {rate:.4f} degrees/minute" if rate is not None else "Rate unavailable",
            rate, rate_limit, timestamp,
        )
    error = sample.get("error_code")
    store.set_alert(
        node_id, "sensor_error", bool(rules.get("sensor_error") and error),
        f"Sensor reported error code {error}", float(error) if error is not None else None,
        0, timestamp, "critical",
    )


def evaluate_health(store: MonitoringStore, health: dict[str, Any], rules: dict[str, Any]) -> None:
    battery, threshold = health.get("battery_v"), rules.get("low_battery_v")
    store.set_alert(
        int(health["node_id"]), "low_battery",
        threshold is not None and battery is not None and battery <= threshold,
        f"Battery voltage is {battery:.2f} V" if battery is not None else "Battery voltage unavailable",
        battery, threshold, int(health["timestamp"]), "critical",
    )


def evaluate_missing_data(store: MonitoringStore, rules: dict[str, Any], now: int | None = None) -> None:
    latest = store.latest_sample()
    if latest is None:
        return
    now = int(time.time()) if now is None else now
    threshold = rules.get("missing_data_seconds")
    age = now - int(latest["timestamp"])
    store.set_alert(
        int(latest["node_id"]), "missing_data",
        threshold is not None and age >= threshold,
        f"No measurement has been stored for {age} seconds", age, threshold,
        int(latest["timestamp"]), "critical",
    )
