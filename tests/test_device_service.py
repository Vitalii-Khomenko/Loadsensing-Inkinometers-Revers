from copy import deepcopy

import pytest

from tools.config_backup import sign_snapshot
from tools.device_service import DeviceService, DeviceServiceError
from tools.packet_parser import encode_frame
from tests.test_config_backup import sample_snapshot


HEADER = bytes.fromhex("41 4e 8d 2d 01")


class FakeConnection:
    def __init__(self) -> None:
        self.response = b""
        self.writes = []

    def write(self, wire: bytes) -> int:
        self.writes.append(wire)
        self.response = encode_frame(HEADER + bytes.fromhex("00 00 00"))
        return len(wire)

    def flush(self) -> None: pass
    def read(self, size: int) -> bytes:
        value, self.response = self.response, b""
        return value
    def close(self) -> None: pass


class RestoreService(DeviceService):
    def __init__(self, current, target, *, mismatch=False):
        self.connection = FakeConnection()
        self.current = current
        self.target = target
        self.backups = 0
        self.mismatch = mismatch
        super().__init__(
            "/dev/fake", writes_enabled=True,
            hardware_validated_writes=frozenset({"sampling", "channels", "radio_slot_time"}),
            opener=lambda port: self.connection, query_runner=self.query,
        )

    def backup(self):
        self.backups += 1
        return self.current if self.backups == 1 else self.target

    def query(self, connection, name, query):
        value = (
            self.target["configuration"]["radio_slot_time"]
            if name == "radio-slot-time"
            else self.target["configuration"]["sampling"]
        )
        if self.mismatch:
            value += 1
        return {"query": name, "status": "ok", "data": value}


def test_restore_enforces_confirmation_ack_readback_and_post_backup() -> None:
    current = sample_snapshot()
    target = deepcopy(current)
    target["configuration"]["sampling"] = 301
    target = sign_snapshot(target)
    service = RestoreService(current, target)
    result = service.apply_restore(target, "RESTORE 101677")
    assert result["status"] == "restored"
    assert service.connection.writes[0] == bytes.fromhex("10 02 82 00 01 2d 10 03")
    assert result["post_backup"]["configuration"]["sampling"] == 301


def test_restore_is_disabled_by_default_and_rolls_back_on_mismatch() -> None:
    current = sample_snapshot()
    target = deepcopy(current)
    target["configuration"]["sampling"] = 301
    target = sign_snapshot(target)
    disabled = DeviceService("/dev/fake")
    with pytest.raises(DeviceServiceError, match="writes are disabled"):
        disabled.apply_restore(target, "RESTORE 101677")

    service = RestoreService(current, target, mismatch=True)
    with pytest.raises(DeviceServiceError, match="restore failed"):
        service.apply_restore(target, "RESTORE 101677")
    assert service.connection.writes[-1] == bytes.fromhex("10 02 82 00 01 2c 10 03")


def test_gateway_slot_restore_uses_separate_uint16_command() -> None:
    current = sample_snapshot()
    target = deepcopy(current)
    target["configuration"]["radio_slot_time"] = 3000
    target = sign_snapshot(target)
    service = RestoreService(current, target)
    result = service.apply_restore(target, "RESTORE 101677")
    assert result["status"] == "restored"
    assert service.connection.writes[0] == bytes.fromhex("10 02 90 0b b8 10 03")


def test_idempotent_read_reopens_after_temporary_usb_error() -> None:
    connection = FakeConnection()
    attempts = []

    def opener(port):
        attempts.append(port)
        if len(attempts) == 1:
            raise OSError("adapter disconnected")
        return connection

    service = DeviceService(
        "/dev/fake", opener=opener,
        query_runner=lambda conn, name, query: {"query": name, "status": "ok"},
    )
    assert service.read("health")[0]["status"] == "ok"
    assert len(attempts) == 2
    assert service.status()["reconnect_count"] == 1
    assert service.status()["last_connection_error"] is None
