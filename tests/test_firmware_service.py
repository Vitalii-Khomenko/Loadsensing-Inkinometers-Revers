import binascii
import hashlib

import pytest

import tools.firmware_service as firmware_service
from tools.firmware_service import (
    FirmwareError,
    crc16_xmodem,
    send_xmodem,
    validate_firmware_file,
)


class FakeConnection:
    def __init__(self):
        self.writes = []

    def write(self, payload):
        self.writes.append(payload)
        return len(payload)

    def flush(self):
        pass


class FakeReader:
    def __init__(self, responses):
        self.responses = list(responses)

    def next_byte(self, timeout):
        return self.responses.pop(0) if self.responses else None


def test_xmodem_crc_matches_standard_vector():
    assert crc16_xmodem(b"123456789") == 0x31C3
    assert crc16_xmodem(b"abc") == binascii.crc_hqx(b"abc", 0)


def test_xmodem_matches_apk_probe_retries_blocks_and_eot():
    connection = FakeConnection()
    reader = FakeReader([0x15, 0x15, 0x06, 0x06, 0x06])
    result = send_xmodem(connection, reader, bytes(range(200)))
    assert result == {"blocks": 2, "bytes": 200, "retries": 2, "eot_attempts": 1}
    assert len(connection.writes[0]) == 133
    assert connection.writes[0][:3] == bytes((1, 1, 0xFE))
    assert connection.writes[2][-2:] == crc16_xmodem(bytes(range(128))).to_bytes(2, "big")
    assert connection.writes[3][:3] == bytes((1, 2, 0xFD))
    assert connection.writes[-1] == b"\x04"


def test_xmodem_aborts_on_bootloader_cancel():
    with pytest.raises(FirmwareError, match="cancelled"):
        send_xmodem(FakeConnection(), FakeReader([0x18]), b"payload", apk_crc_probe_retries=0)


def test_bundled_firmware_matches_validated_manifest():
    manifest = validate_firmware_file(firmware_service.G6_TIL90_FIRMWARE)
    assert manifest["size_bytes"] == 124288
    assert manifest["sha256"] == firmware_service.G6_TIL90_SHA256
    assert manifest["target_product_code"] == 0x4E
    assert manifest["version"] == "2.81"


def test_standalone_firmware_validation_accepts_only_exact_artifact(tmp_path, monkeypatch):
    payload = b"validated-test-image"
    path = tmp_path / firmware_service.G6_TIL90_FIRMWARE.name
    path.write_bytes(payload)
    monkeypatch.setattr(firmware_service, "G6_TIL90_SIZE", len(payload))
    monkeypatch.setattr(
        firmware_service, "G6_TIL90_SHA256", hashlib.sha256(payload).hexdigest()
    )
    manifest = validate_firmware_file(path)
    assert manifest["size_bytes"] == len(payload)
    assert manifest["version"] == "2.81"
    path.write_bytes(payload + b"corrupt")
    with pytest.raises(FirmwareError, match="size or SHA-256"):
        validate_firmware_file(path)
