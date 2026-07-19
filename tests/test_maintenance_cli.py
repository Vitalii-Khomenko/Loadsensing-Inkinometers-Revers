from types import SimpleNamespace

import pytest

from tools.maintenance_cli import (
    FACTORY_RESET_BODY,
    LOCAL_SAMPLING_STOP,
    MaintenanceError,
    _wait_for_health,
    encode_local_sampling,
    validate_gateway_slot,
)
from tools.packet_parser import encode_frame


class Connection:
    def __init__(self, body: bytes):
        self.wire = encode_frame(body)

    def read(self, size: int) -> bytes:
        wire, self.wire = self.wire, b""
        return wire


def test_wait_for_health_decodes_expected_node(monkeypatch):
    body = bytes.fromhex("41 4e 8d 2d 01 4f") + bytes.fromhex(
        "6a 57 b3 fa 00 00 00 05 14 c1 b1 8d 2d 02 51 00 00"
    )
    result = _wait_for_health(Connection(body), 101677, 0.1)
    assert result["status"] == "ok"
    assert result["data"]["uptime"] == 5


def test_wait_for_health_rejects_another_node():
    body = bytes.fromhex("41 4e 00 01 01 4f") + bytes(17)
    with pytest.raises(MaintenanceError, match="identity changed"):
        _wait_for_health(Connection(body), 101677, 0.1)


def test_local_sampling_exact_original_app_bit_packing():
    assert FACTORY_RESET_BODY == bytes.fromhex("08 75 b5 44 a2")
    assert encode_local_sampling(6, 2) == bytes.fromhex(
        "15 00 02 00 00 00 20 00 00 60"
    )
    assert LOCAL_SAMPLING_STOP == bytes.fromhex(
        "15 00 02 00 00 00 00 00 00 00"
    )
    with pytest.raises(MaintenanceError):
        encode_local_sampling(16, 2)
