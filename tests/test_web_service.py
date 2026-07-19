from fastapi.testclient import TestClient
import time

from tools.web_service import create_app
from tests.test_config_backup import sample_snapshot


class FakeDevice:
    writes_enabled = False
    hardware_validated_writes = frozenset()
    def status(self):
        return {"device_detected": True, "selected_port": "/dev/fake", "ports": ["/dev/fake"], "busy": False, "writes_enabled": False, "hardware_validated_writes": []}
    def read(self, selection, count=1, delay=0):
        return [{"query": selection, "status": "ok"}]
    def backup(self): return sample_snapshot()
    def preview_restore(self, target):
        return {"operations": [], "blocked_changes": [], "can_apply": False, "requires_confirmation": "RESTORE 101677"}
    def apply_restore(self, target, confirmation):
        raise RuntimeError("must not be called")
    def history(self, start_epoch, end_epoch, max_records=500):
        return {"status": "ok", "complete": True, "records": []}


def test_web_app_is_local_token_protected_and_hardened() -> None:
    client = TestClient(create_app(FakeDevice()))
    page = client.get("/")
    assert page.status_code == 200
    assert "TIL90 Field Desk" in page.text
    assert page.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in page.headers["content-security-policy"]
    assert client.post("/api/read", json={"selection": "health"}).status_code == 403
    token = client.get("/api/session").json()["token"]
    response = client.post("/api/read", json={"selection": "health"}, headers={"X-TIL90-Token": token})
    assert response.status_code == 200
    assert response.json()["results"][0]["status"] == "ok"
    assert client.get("/api/status", headers={"host": "sensor.example"}).status_code == 403


def test_backup_validation_and_restore_preview_api() -> None:
    client = TestClient(create_app(FakeDevice()))
    token = client.get("/api/session").json()["token"]
    headers = {"X-TIL90-Token": token}
    backup = sample_snapshot()
    valid = client.post("/api/backup/validate", json={"backup": backup}, headers=headers)
    assert valid.status_code == 200 and valid.json()["valid"]
    backup["configuration"]["sampling"] = 999
    invalid = client.post("/api/backup/validate", json={"backup": backup}, headers=headers)
    assert invalid.status_code == 400


def test_frontend_has_no_external_runtime_dependencies() -> None:
    client = TestClient(create_app(FakeDevice()))
    for path in ("/", "/assets/app.js", "/assets/styles.css"):
        response = client.get(path)
        assert response.status_code == 200
        assert "https://" not in response.text and "http://" not in response.text

    page = client.get("/").text
    script = client.get("/assets/app.js").text
    assert "Measurement interval" in page
    assert "Radio slot / gateway transmission timing" in page
    assert "Engineering log and UART evidence" in page
    assert "Reinstall verified firmware 2.81" in page
    assert "Reset, restore, and verify" in page
    assert "Replace network ID and password" in page
    assert "<pre" not in page
    assert "JSON.stringify(results" not in script


def test_destructive_web_operations_require_explicit_write_mode() -> None:
    client = TestClient(create_app(FakeDevice()))
    token = client.get("/api/session").json()["token"]
    headers = {"X-TIL90-Token": token}
    backup = sample_snapshot()
    flash = client.post(
        "/api/firmware/flash", json={"confirmation": "FLASH FIRMWARE 101677 2.81"},
        headers=headers,
    )
    reset = client.post(
        "/api/recovery/factory-reset-restore",
        json={
            "backup": backup, "network_id": 27484, "password": "temporary",
            "confirmation": "RESET AND RESTORE 101677",
        },
        headers=headers,
    )
    gateway = client.post(
        "/api/radio/gateway-credentials",
        json={
            "network_id": 27484, "password": "temporary",
            "confirmation": "CHANGE GATEWAY 101677 27484",
        },
        headers=headers,
    )
    assert flash.status_code == reset.status_code == gateway.status_code == 400


def test_readable_configuration_profiles_and_history_api() -> None:
    client = TestClient(create_app(FakeDevice()))
    token = client.get("/api/session").json()["token"]
    headers = {"X-TIL90-Token": token}
    current = client.post("/api/config/current", headers=headers)
    assert current.status_code == 200
    assert current.json()["sampling_seconds"] == 300
    assert current.json()["gateway_slot_seconds"] == 0

    preview = client.post(
        "/api/config/preview",
        json={
            "sampling_seconds": 600,
            "gateway_slot_seconds": 3000,
            "axis_x": True,
            "axis_y": True,
            "axis_z": False,
        },
        headers=headers,
    )
    assert preview.status_code == 200
    assert {op["name"] for op in preview.json()["plan"]["operations"]} == {
        "sampling", "channels", "radio_slot_time"
    }
    assert not preview.json()["plan"]["can_apply"]

    profiles = client.get("/api/radio-profiles")
    assert profiles.status_code == 200
    assert len(profiles.json()["profiles"]) == 20
    history = client.post(
        "/api/history",
        json={"start_epoch": 1, "end_epoch": 2, "max_records": 10},
        headers=headers,
    )
    assert history.status_code == 200 and history.json()["complete"]


def test_monitoring_alert_and_usb_diagnostic_apis(tmp_path) -> None:
    with TestClient(create_app(FakeDevice(), database_path=tmp_path / "data.sqlite3")) as client:
        token = client.get("/api/session").json()["token"]
        headers = {"X-TIL90-Token": token}
        status = client.post("/api/monitor/status", headers=headers)
        assert status.status_code == 200
        assert status.json()["config"]["measurement_interval_seconds"] == 60
        configured = client.post(
            "/api/monitor/config",
            json={
                "enabled": False, "measurement_interval_seconds": 120,
                "health_interval_seconds": 600, "retention_days": 30,
                "alerts": {
                    "x_absolute_deg": 2.5, "y_absolute_deg": None,
                    "z_absolute_deg": None, "rate_deg_per_minute": 0.5,
                    "low_battery_v": 3.0, "missing_data_seconds": 400,
                    "sensor_error": True,
                },
            },
            headers=headers,
        )
        assert configured.status_code == 200
        assert configured.json()["config"]["alerts"]["x_absolute_deg"] == 2.5
        assert client.post("/api/alerts", headers=headers).json() == {"alerts": []}
        usb = client.post("/api/usb/diagnostics", headers=headers)
        assert usb.status_code == 200 and "recommendations" in usb.json()
        recovery = client.post("/api/recovery/check", headers=headers)
        assert recovery.status_code == 200
        assert recovery.json()["overall"] == "failed"
        assert recovery.json()["steps"][0]["name"] == "USB enumeration"


def test_resumable_history_job_and_csv_api(tmp_path) -> None:
    with TestClient(create_app(FakeDevice(), database_path=tmp_path / "data.sqlite3")) as client:
        token = client.get("/api/session").json()["token"]
        headers = {"X-TIL90-Token": token}
        created = client.post(
            "/api/history/jobs",
            json={"start_epoch": 1, "end_epoch": 2, "chunk_seconds": 300,
                  "max_records_per_chunk": 10},
            headers=headers,
        )
        assert created.status_code == 200
        deadline = time.monotonic() + 1
        job = None
        while time.monotonic() < deadline:
            jobs = client.post("/api/history/jobs/list", headers=headers).json()["jobs"]
            job = jobs[0]
            if job["status"] == "complete":
                break
            time.sleep(0.01)
        assert job["status"] == "complete" and job["chunks_completed"] == 1
        data = client.post(
            "/api/data/measurements",
            json={"start_epoch": 1, "end_epoch": 2, "max_records": 10},
            headers=headers,
        )
        assert data.status_code == 200 and data.json()["measurements"] == []
        exported = client.get("/api/data/export.csv", headers=headers)
        assert exported.status_code == 200
        assert exported.text.startswith("node_id,timestamp,source")
