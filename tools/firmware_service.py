"""Guarded G6 TIL90 firmware validation and XMODEM recovery transport."""

from __future__ import annotations

import binascii
import hashlib
from pathlib import Path
import time
from typing import Any, Callable

from tools.config_backup import diff_snapshots
from tools.device_service import DeviceService
from tools.packet_parser import encode_frame
from tools.til90_cli import _open_serial


G6_TIL90_FIRMWARE = Path("firmware/LSG_TIL90_v2_81.bin")
G6_TIL90_SHA256 = "9dba6261df792649b0cebd0db86f1aa459bb93209b8783dad2da020a5f0b227f"
G6_TIL90_SIZE = 124288
G6_TIL90_PRODUCT = 0x4E
G6_TIL90_VERSION = (2, 81)
BOOTLOADER_PASSWORD = b"worldsensing"


class FirmwareError(RuntimeError):
    pass


def crc16_xmodem(data: bytes) -> int:
    return binascii.crc_hqx(data, 0)


def validate_firmware_file(path: str | Path) -> dict[str, Any]:
    """Validate the immutable firmware artifact without touching a sensor."""
    firmware = Path(path)
    if not firmware.is_file():
        raise FirmwareError(f"firmware file does not exist: {firmware}")
    payload = firmware.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if firmware.name != G6_TIL90_FIRMWARE.name:
        raise FirmwareError("firmware filename is not the APK-mapped G6 TIL90 image")
    if len(payload) != G6_TIL90_SIZE or digest != G6_TIL90_SHA256:
        raise FirmwareError("firmware size or SHA-256 does not match the APK inventory")
    return {
        "path": str(firmware), "filename": firmware.name, "size_bytes": len(payload),
        "sha256": digest, "target_product_code": G6_TIL90_PRODUCT,
        "version": "2.81", "block_count": (len(payload) + 127) // 128,
    }


def validate_firmware(path: str | Path, device: dict[str, Any]) -> dict[str, Any]:
    manifest = validate_firmware_file(path)
    if device.get("product_code") != G6_TIL90_PRODUCT:
        raise FirmwareError("connected product is not the mapped G6 TIL90 product 0x4E")
    current = (device.get("firmware_major"), device.get("firmware_minor"))
    if current != G6_TIL90_VERSION:
        raise FirmwareError(
            f"connected firmware {current[0]}.{current[1]} does not match image 2.81"
        )
    return manifest


class _RawReader:
    def __init__(self, connection: Any) -> None:
        self.connection = connection
        self.buffer = bytearray()
        self.transcript = bytearray()

    def next_byte(self, timeout: float) -> int | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.buffer:
                return self.buffer.pop(0)
            chunk = self.connection.read(4096)
            if chunk:
                self.buffer.extend(chunk)
                self.transcript.extend(chunk)
        return None

    def wait_for(self, expected: int, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = self.next_byte(min(0.5, max(0.01, deadline - time.monotonic())))
            if value == expected:
                return
        raise FirmwareError(f"timeout waiting for bootloader byte 0x{expected:02X}")


def _write_all(connection: Any, payload: bytes) -> None:
    written = connection.write(payload)
    if written != len(payload):
        raise FirmwareError(f"short firmware transport write: {written}/{len(payload)}")
    connection.flush()


def send_xmodem(
    connection: Any, reader: _RawReader, payload: bytes,
    progress: Callable[[int, int], None] | None = None,
    *, apk_crc_probe_retries: int = 2,
) -> dict[str, int]:
    """Send 128-byte XMODEM/CRC blocks, matching the APK's two initial CRC probes."""
    block_number = 1
    retries = bytes_sent = 0
    probe_retries = apk_crc_probe_retries
    total_blocks = (len(payload) + 127) // 128
    for offset in range(0, len(payload), 128):
        data = payload[offset:offset + 128].ljust(128, b"\xFF")
        accepted = False
        for _attempt in range(11):
            crc = crc16_xmodem(data)
            if probe_retries:
                crc = (crc + 1) & 0xFFFF
                probe_retries -= 1
            packet = bytes((0x01, block_number, 0xFF - block_number)) + data + crc.to_bytes(2, "big")
            _write_all(connection, packet)
            response = reader.next_byte(2.0)
            if response == 0x06:
                accepted = True
                break
            if response == 0x18:
                raise FirmwareError("bootloader cancelled the XMODEM transfer")
            retries += 1
        if not accepted:
            raise FirmwareError(f"block {block_number} was not acknowledged")
        bytes_sent += min(128, len(payload) - offset)
        if progress:
            progress(offset // 128 + 1, total_blocks)
        block_number = (block_number + 1) & 0xFF
    for attempt in range(10):
        _write_all(connection, b"\x04")
        if reader.next_byte(2.0) == 0x06:
            return {"blocks": total_blocks, "bytes": bytes_sent, "retries": retries,
                    "eot_attempts": attempt + 1}
    raise FirmwareError("bootloader did not acknowledge end of transmission")


def flash_g6_til90(
    port: str, confirmation: str, *, firmware_path: str | Path = G6_TIL90_FIRMWARE,
    timeout: float = 45.0, progress: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    service = DeviceService(port)
    before = service.backup()
    device = before["device"]
    manifest = validate_firmware(firmware_path, device)
    required = f"FLASH FIRMWARE {device['node_id']} 2.81"
    if confirmation != required:
        raise FirmwareError(f"confirmation must be exactly: {required}")
    payload = Path(firmware_path).read_bytes()
    with _open_serial(service.resolve_port()) as connection:
        reader = _RawReader(connection)
        _write_all(connection, encode_frame(b"\x09"))
        # The G6 APK sends the password one second after reboot without first
        # waiting for a prompt. Only the post-password XMODEM 'C' is awaited.
        time.sleep(1.0)
        _write_all(connection, BOOTLOADER_PASSWORD)
        reader.wait_for(0x43, 10.0)
        transfer = send_xmodem(connection, reader, payload, progress)
        bootloader_transcript_tail = bytes(reader.transcript[-512:]).hex(" ")

    deadline = time.monotonic() + timeout
    after = None
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            after = service.backup()
            break
        except Exception as exc:
            last_error = exc
            time.sleep(1)
    if after is None:
        raise FirmwareError(f"firmware transfer completed but node did not return: {last_error}")
    if after["device"]["product_code"] != device["product_code"]:
        raise FirmwareError("post-flash product code changed")
    if (after["device"]["firmware_major"], after["device"]["firmware_minor"]) != G6_TIL90_VERSION:
        raise FirmwareError("post-flash firmware version is not 2.81")
    return {
        "status": "flashed-and-verified", "device": after["device"],
        "firmware": manifest, "transfer": transfer,
        "bootloader_transcript_tail": bootloader_transcript_tail,
        "configuration_changes": diff_snapshots(before, after),
        "before_backup": before, "after_backup": after,
    }
