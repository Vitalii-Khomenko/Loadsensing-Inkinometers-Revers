import time

import tools.monitoring_service as monitoring_module
from tools.alert_engine import evaluate_health, evaluate_sample
from tools.history_manager import HistoryManager
from tools.monitoring_service import MonitoringService
from tools.monitoring_store import MonitoringStore


def record(timestamp=100, x=1.0, node_id=101677):
    return {
        "query": "live", "status": "ok", "header": {"node_id": node_id},
        "data": {
            "timestamp": timestamp, "temperature_c": 20.5, "error_code": 0,
            "axes": {
                "x": {"angle_deg": x, "stddev_g": 0.01},
                "y": {"angle_deg": 2.0, "stddev_g": 0.02},
                "z": {"angle_deg": 3.0, "stddev_g": 0.03},
            },
        },
    }


def health(timestamp=100, battery=3.2, node_id=101677):
    return {
        "query": "health", "status": "ok", "header": {"node_id": node_id},
        "data": {"timestamp": timestamp, "battery_v": battery, "temperature_c": 20,
                 "uptime": 50, "firmware_major": 2, "firmware_minor": 81},
    }


def wait_for_job(store, job_id, status):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        job = store.history_job(job_id)
        if job["status"] == status:
            return job
        time.sleep(0.01)
    raise AssertionError(f"job did not reach {status}: {store.history_job(job_id)}")


def test_store_deduplicates_records_and_alerts_have_a_lifecycle(tmp_path):
    store = MonitoringStore(tmp_path / "monitor.sqlite3")
    assert store.insert_record(record(), "live") == ("sample", True)
    assert store.insert_record(record(), "history") == ("sample", False)
    first = store.latest_sample()
    assert first["x_deg"] == 1.0 and store.summary()["sample_count"] == 1

    rules = {
        "x_absolute_deg": 0.5, "y_absolute_deg": None, "z_absolute_deg": None,
        "rate_deg_per_minute": None, "sensor_error": True,
    }
    evaluate_sample(store, first, None, rules)
    assert store.alerts("open")[0]["rule"] == "x_absolute"
    newer = record(101, 0.1)
    store.insert_record(newer, "live")
    evaluate_sample(store, store.latest_sample(), first, rules)
    assert not store.alerts("open")
    assert store.alerts("resolved")[0]["resolved_utc"]
    store.close()


def test_monitor_ingests_health_and_evaluates_low_battery(tmp_path):
    store = MonitoringStore(tmp_path / "monitor.sqlite3")
    monitor = MonitoringService(object(), store)
    config = monitor.config()
    config["alerts"]["low_battery_v"] = 3.0
    store.set_monitor_config(config)
    monitor.ingest([health(battery=2.9)])
    assert store.summary()["health_count"] == 1
    assert store.alerts("open")[0]["rule"] == "low_battery"


class DetectedDevice:
    def status(self):
        return {
            "device_detected": True,
            "selected_port": "/dev/serial/by-id/fake-CP2102N",
        }


def test_monitor_status_exposes_connection_and_latest_records(tmp_path):
    store = MonitoringStore(tmp_path / "monitor.sqlite3")
    store.insert_record(record(), "live")
    store.insert_record(health(), "live")
    monitor = MonitoringService(DetectedDevice(), store)
    status = monitor.status()
    assert status["connection_state"] == "connecting"
    assert status["device"]["device_detected"]
    assert status["latest_sample"]["x_deg"] == 1.0
    assert status["latest_health"]["battery_v"] == 3.2
    store.close()


class HotplugDevice:
    def __init__(self):
        self.present = False

    def status(self):
        return {"device_detected": self.present, "selected_port": "/dev/fake"}

    def read(self, selection):
        if not self.present:
            raise OSError("USB sensor is absent")
        timestamp = int(time.time())
        return [record(timestamp) if selection == "live" else health(timestamp)]


def test_monitor_waits_for_hotplug_and_acquires_without_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(monitoring_module, "RECONNECT_RETRY_SECONDS", 0.01)
    store = MonitoringStore(tmp_path / "monitor.sqlite3")
    device = HotplugDevice()
    monitor = MonitoringService(device, store)
    config = monitor.config()
    config["enabled"] = True
    store.set_monitor_config(config)
    monitor.start()
    deadline = time.monotonic() + 1
    while monitor.status()["last_error"] is None and time.monotonic() < deadline:
        time.sleep(0.005)
    assert monitor.status()["connection_state"] == "waiting"
    device.present = True
    deadline = time.monotonic() + 1
    while store.summary()["sample_count"] == 0 and time.monotonic() < deadline:
        time.sleep(0.005)
    monitor.stop()
    assert store.summary()["sample_count"] == 1
    assert monitor.status()["connection_state"] == "connected"
    store.close()


class HistoryDevice:
    def __init__(self):
        self.fail = True

    def history(self, start, end, max_records):
        if self.fail:
            self.fail = False
            raise OSError("temporary disconnect")
        return {
            "status": "ok", "complete": True,
            "identity": {"header": {"node_id": 101677}},
            "records": [record(start)],
        }


def test_history_job_pauses_resumes_chunks_and_deduplicates(tmp_path):
    store = MonitoringStore(tmp_path / "monitor.sqlite3")
    manager = HistoryManager(HistoryDevice(), store)
    job = manager.create(100, 699, chunk_seconds=300, max_records_per_chunk=10)
    paused = wait_for_job(store, job["id"], "paused")
    assert paused["cursor_epoch"] == 100 and "temporary disconnect" in paused["error"]
    manager.resume(job["id"])
    complete = wait_for_job(store, job["id"], "complete")
    assert complete["chunks_completed"] == 2
    assert complete["records_imported"] == 2
    manager.stop()
