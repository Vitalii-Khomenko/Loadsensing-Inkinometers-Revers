from copy import deepcopy

from tools.recovery_check import run_recovery_check
from tests.test_config_backup import sample_snapshot


class FakeDevice:
    def __init__(self, snapshot=None):
        self.snapshot = snapshot or sample_snapshot()

    def status(self):
        return {"selected_port": "/dev/null", "reconnect_count": 0}

    def read(self, selection):
        return [{
            "query": "health", "status": "ok",
            "header": {"node_id": 101677, "product_code": 78},
            "data": {"battery_v": 3.3, "uptime": 100},
        }]

    def backup(self):
        return self.snapshot


def test_recovery_check_reports_configuration_without_writing(monkeypatch):
    monkeypatch.setattr("tools.recovery_check.diagnose", lambda port: {
        "exists": True, "readable": True, "writable": True,
        "selected_port": port, "stable_alias": "/dev/serial/by-id/fake",
        "recommendations": [],
    })
    result = run_recovery_check(FakeDevice())
    assert result["overall"] == "warning"
    assert result["device"]["node_id"] == 101677
    assert result["actions"]["factory_reset"].startswith("blocked")
    assert not result["configuration"]["factory_reset_indicated_by_apk_rule"]


def test_recovery_check_flags_only_the_apk_factory_reset_sentinel(monkeypatch):
    monkeypatch.setattr("tools.recovery_check.diagnose", lambda port: {
        "exists": True, "readable": True, "writable": True,
        "selected_port": port, "stable_alias": None, "recommendations": [],
    })
    snapshot = deepcopy(sample_snapshot())
    snapshot["configuration"]["radio_address"] = 0xFFFFFFFF
    result = run_recovery_check(FakeDevice(snapshot))
    assert result["overall"] == "failed"
    assert result["configuration"]["factory_reset_indicated_by_apk_rule"]
    assert any("Do not reset automatically" in item for item in result["recommendations"])
