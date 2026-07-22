"""Guarded embedded-gateway credentials and full post-reset radio restoration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from tools.config_backup import (
    diff_snapshots, encode_channels_write, encode_radio_slot_time_write,
    encode_sampling_write,
)
from tools.device_service import DeviceService
from tools.firmware_service import crc16_xmodem
from tools.til90_cli import READ_QUERIES


class RadioConfigurationError(RuntimeError):
    pass


PROFILE_REGISTRY = Path(__file__).resolve().parents[1] / "analysis/protocol/radio_profiles.json"
EUROPE_GENERAL_BODY = bytes.fromhex("84 10 7b 0e 0c 3c cb f7 00 00 00")


def load_regional_profile(name: str) -> dict[str, Any]:
    profiles = json.loads(PROFILE_REGISTRY.read_text(encoding="utf-8"))["profiles"]
    try:
        profile = next(item for item in profiles if item["name"] == name)
    except StopIteration as exc:
        raise RadioConfigurationError(f"unknown original-app profile: {name}") from exc
    if profile["name"] != "EUROPE" or profile["plan"] != "EDGE" or profile["mac"] != "EU868_V1":
        raise RadioConfigurationError(
            "profile writes are hardware-validated only for the embedded EUROPE profile"
        )
    return profile


def encode_lora_channels(am_type: int, frequencies_hz: list[int]) -> bytes:
    if am_type not in {0x85, 0x8E}:
        raise RadioConfigurationError("unsupported LoRa channel configuration type")
    if len(frequencies_hz) != 8 or not all(
        isinstance(value, int) and 0 <= value <= 0xFFFFFFFF for value in frequencies_hz
    ):
        raise RadioConfigurationError("LoRa channel profile must contain eight frequencies")
    mask = sum(1 << (7 - index) for index, value in enumerate(frequencies_hz) if value)
    return bytes((am_type, 0x00, mask)) + b"".join(
        value.to_bytes(4, "big") for value in frequencies_hz
    )


def _profile_mismatches(snapshot: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    config = snapshot["configuration"]
    general = config["radio_general"]
    expected_general = {
        "mac_version": 0,
        "channel_500khz_enabled": profile["use_500khz"],
        "radio_enabled": True,
        "etsi_enabled": profile["etsi"][0],
        "adr_enabled": profile["adr"][0],
        "spreading_factor": profile["sf"][2],
        "tx_power": profile["tx_power_dbm"],
    }
    mismatches = [
        f"radio_general.{key}" for key, expected in expected_general.items()
        if general.get(key) != expected
    ]
    expected_frequencies = profile["uplink_hz"][profile["default_group"]]
    uplink = config["radio_channels"]
    if list(uplink.get("frequencies_hz", [])) != expected_frequencies:
        mismatches.append("radio_channels.frequencies_hz")
    expected_enabled = [bool(value) for value in expected_frequencies]
    if list(uplink.get("enabled", [])) != expected_enabled:
        mismatches.append("radio_channels.enabled")
    return mismatches


def apply_regional_profile(
    service: DeviceService, profile_name: str, confirmation: str,
) -> dict[str, Any]:
    """Apply the hardware-validated embedded EUROPE radio fields with rollback."""
    profile = load_regional_profile(profile_name)
    if not service.writes_enabled:
        raise RadioConfigurationError("hardware writes are disabled")
    before = service.backup()
    node_id = before["device"]["node_id"]
    required = f"APPLY PROFILE {node_id} {profile_name}"
    if confirmation != required:
        raise RadioConfigurationError(f"confirmation must be exactly: {required}")
    if before["device"]["product_code"] != 0x4E:
        raise RadioConfigurationError("regional profile write is validated only for product 0x4E")
    if not _profile_mismatches(before, profile):
        return {
            "status": "regional-profile-already-configured",
            "node_id": node_id,
            "profile": profile_name,
            "operations": 0,
            "after_backup": before,
        }

    operations = [
        ("regional-profile-general", EUROPE_GENERAL_BODY, "radio-general"),
        (
            "regional-profile-uplink",
            encode_lora_channels(0x85, profile["uplink_hz"][profile["default_group"]]),
            "radio-channels",
        ),
    ]
    rollback_bodies = {
        "radio-general": _backup_body(before, "radio-general"),
        "radio-channels": _backup_body(before, "radio-channels"),
    }
    evidence: list[dict[str, Any]] = []
    applied: list[tuple[str, str]] = []
    try:
        with service._lock, service._open() as connection:
            for name, body, query in operations:
                applied.append((name, query))
                evidence.append(_write_verified(service, connection, name, body, query))
        after = service.backup()
        mismatches = _profile_mismatches(after, profile)
        if mismatches:
            raise RadioConfigurationError(f"regional profile readback differs: {mismatches}")
        preserved_fields = (
            "radio_address", "radio_network_id", "radio_join", "radio_slot_time"
        )
        changed = [
            field for field in preserved_fields
            if after["configuration"][field] != before["configuration"][field]
        ]
        if changed:
            raise RadioConfigurationError(f"gateway-specific fields changed unexpectedly: {changed}")
    except Exception as original:
        rollback_errors: list[str] = []
        if applied:
            try:
                with service._lock, service._open() as connection:
                    for name, query in reversed(applied):
                        _write_verified(
                            service, connection, f"rollback-{name}", rollback_bodies[query], query
                        )
            except Exception as rollback_error:
                rollback_errors.append(str(rollback_error))
        raise RadioConfigurationError(
            f"regional profile change failed: {original}; rollback_errors={rollback_errors}"
        ) from original
    return {
        "status": "regional-profile-applied",
        "node_id": node_id,
        "profile": profile_name,
        "operations": len(operations),
        "evidence": evidence,
        "after_backup": after,
    }


def encode_embedded_auth(network_id: int, password: str) -> bytes:
    if not 1 <= network_id <= 0xFFFFFFFF:
        raise RadioConfigurationError("network ID must be between 1 and 4294967295")
    if not password or len(password.encode("utf-8")) > 128:
        raise RadioConfigurationError("gateway password must contain 1..128 UTF-8 bytes")
    identity = str(network_id)
    app_key = hashlib.sha1((identity + password + "lpvid433J17WI9qM").encode()).digest()[:16]
    net_key = hashlib.sha1((identity + password + "wu5FJtk22T29W9nw").encode()).digest()[:16]
    body = b"\x8d" + app_key + net_key + network_id.to_bytes(4, "big")
    return body + crc16_xmodem(body[1:]).to_bytes(2, "big")


def encode_embedded_join(node_id: int, network_id: int) -> bytes:
    if not 0 <= node_id <= 0xFFFFF:
        raise RadioConfigurationError("node ID must fit 20 bits")
    if not 1 <= network_id <= 0xFFFFFFFF:
        raise RadioConfigurationError("network ID must be positive")
    base = 0x70B3D52C70100000
    dev_eui = (base + node_id).to_bytes(8, "big")
    app_eui = (base + network_id).to_bytes(8, "big")
    return b"\x94\x00" + dev_eui + app_eui + bytes.fromhex("27 60 00 01 18 00")


def _backup_body(snapshot: dict[str, Any], query: str) -> bytes:
    evidence = next(item for item in snapshot["evidence"] if item.get("query") == query)
    raw = bytes.fromhex(evidence["rx_body"])
    if len(raw) < 7:
        raise RadioConfigurationError(f"backup evidence for {query} is too short")
    # The six-byte response header includes the AM/configuration type as its
    # final byte. A write starts with that same type, followed by its payload.
    return raw[5:]


def _write_verified(
    service: DeviceService, connection: Any, name: str, body: bytes,
    readback_query: str | None = None,
) -> dict[str, Any]:
    ack = service._write_and_ack(connection, name, body, timeout=8.0)
    result = None
    if readback_query:
        result = service._query_runner(connection, readback_query, READ_QUERIES[readback_query])
        if result.get("status") != "ok":
            raise RadioConfigurationError(f"{name} readback failed")
    return {"operation": name, "ack": ack, "readback": result}


def change_gateway_credentials(
    service: DeviceService, network_id: int, password: str, confirmation: str,
) -> dict[str, Any]:
    before = service.backup()
    node_id = before["device"]["node_id"]
    required = f"CHANGE GATEWAY {node_id} {network_id}"
    if confirmation != required:
        raise RadioConfigurationError(f"confirmation must be exactly: {required}")
    evidence = []
    with service._lock, service._open() as connection:
        evidence.append(_write_verified(
            service, connection, "gateway-join", encode_embedded_join(node_id, network_id),
            "radio-join",
        ))
        evidence.append(_write_verified(
            service, connection, "gateway-authentication",
            encode_embedded_auth(network_id, password), "radio-network-id",
        ))
    after = service.backup()
    if after["configuration"]["radio_network_id"] != network_id:
        raise RadioConfigurationError("network ID readback does not match")
    return {
        "status": "gateway-credentials-changed",
        "node_id": node_id, "network_id": network_id,
        "password_written_but_not_readable": True,
        "evidence": evidence, "before_backup": before, "after_backup": after,
    }


def restore_after_factory_reset(
    service: DeviceService, target: dict[str, Any], network_id: int, password: str,
    confirmation: str,
) -> dict[str, Any]:
    current = service.backup()
    node_id = current["device"]["node_id"]
    required = f"RESTORE AFTER RESET {node_id}"
    if confirmation != required:
        raise RadioConfigurationError(f"confirmation must be exactly: {required}")
    if current["device"]["product_code"] != target["device"]["product_code"]:
        raise RadioConfigurationError("backup product does not match the reset node")
    config = target["configuration"]
    operations = [
        ("radio-general", _backup_body(target, "radio-general"), "radio-general"),
        ("radio-uplink-channels", _backup_body(target, "radio-channels"), "radio-channels"),
        ("radio-downlink-channels", _backup_body(target, "radio-down-channels"), "radio-down-channels"),
        ("sampling", encode_sampling_write(config["sampling"]), "sampling"),
        ("gateway-slot", encode_radio_slot_time_write(config["radio_slot_time"]), "radio-slot-time"),
        ("channels", encode_channels_write(config["channels"]["enabled"]), "channels"),
        ("gateway-join", encode_embedded_join(node_id, network_id), "radio-join"),
        ("gateway-authentication", encode_embedded_auth(network_id, password), "radio-network-id"),
    ]
    evidence = []
    with service._lock, service._open() as connection:
        for name, body, query in operations:
            evidence.append(_write_verified(service, connection, name, body, query))
    after = service.backup()
    if after["configuration"]["radio_network_id"] != network_id:
        raise RadioConfigurationError("post-restore network ID mismatch")
    changes = diff_snapshots(after, target)
    return {
        "status": "post-reset-configuration-restored",
        "node_id": node_id, "network_id": network_id,
        "password_written_but_not_readable": True,
        "calibration_write_not_needed": not any(
            item["path"].startswith("configuration.calibration") for item in changes
        ),
        "configuration_changes_from_target": changes,
        "evidence": evidence, "before_backup": current, "target_backup": target,
        "after_backup": after,
    }
