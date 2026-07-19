"""Configuration snapshots, integrity checks, diffs, and restore planning."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from typing import Any


SCHEMA = "til90-config-backup/v1"
class BackupError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def calculate_checksum(snapshot: dict[str, Any]) -> str:
    unsigned = deepcopy(snapshot)
    unsigned.pop("checksum", None)
    return "sha256:" + hashlib.sha256(_canonical(unsigned)).hexdigest()


def sign_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    signed = deepcopy(snapshot)
    signed["checksum"] = calculate_checksum(signed)
    return signed


def create_snapshot(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_name = {result["query"]: result for result in results}
    required = {
        "health", "info", "extended", "sampling", "calibration", "channels",
        "interval", "radio-general", "radio-address", "radio-channels",
        "radio-down-channels", "radio-slot-time", "radio-network-id", "radio-join",
    }
    missing = sorted(required - by_name.keys())
    failed = sorted(
        name for name in required & by_name.keys() if by_name[name].get("status") != "ok"
    )
    if missing or failed:
        raise BackupError(f"incomplete snapshot; missing={missing}, failed={failed}")

    health = by_name["health"]
    info = by_name["info"]["data"]
    header = health["header"]
    snapshot = {
        "schema": SCHEMA,
        "created_utc": utc_now(),
        "device": {
            "node_id": header["node_id"],
            "product_code": header["product_code"],
            "serial_number": info["serial_number"],
            "firmware_major": info["firmware_major"],
            "firmware_minor": info["firmware_minor"],
            "firmware_build_time": info["firmware_build_time"],
        },
        "configuration": {
            "sampling": by_name["sampling"]["data"],
            "calibration": by_name["calibration"]["data"],
            "channels": by_name["channels"]["data"],
            "radio_general": by_name["radio-general"]["data"],
            "radio_address": by_name["radio-address"]["data"],
            "radio_channels": by_name["radio-channels"]["data"],
            "radio_down_channels": by_name["radio-down-channels"]["data"],
            "radio_slot_time": by_name["radio-slot-time"]["data"],
            "radio_network_id": by_name["radio-network-id"]["data"],
            "radio_join": by_name["radio-join"]["data"],
        },
        "storage_interval": by_name["interval"]["data"],
        "restore_capabilities": {
            "sampling": "hardware_validated_with_changed_value_and_restore",
            "channels": "hardware_validated_with_changed_value_and_restore",
            "radio_slot_time": "hardware_validated_with_changed_value_and_restore",
            "calibration": "blocked_no_write_serializer_in_scope",
            "radio": "hardware_validated_complete_post_reset_restore",
            "gateway_credentials": "hardware_validated_ack_join_and_network_id_readback",
            "factory_reset": "hardware_validated_with_full_restore_and_reboot",
            "firmware_2_81": "hardware_validated_exact_image_reinstallation",
        },
        "evidence": results,
    }
    return sign_snapshot(snapshot)


def validate_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        raise BackupError("backup must be a JSON object")
    if snapshot.get("schema") != SCHEMA:
        raise BackupError(f"unsupported backup schema: {snapshot.get('schema')!r}")
    if snapshot.get("checksum") != calculate_checksum(snapshot):
        raise BackupError("backup checksum mismatch")
    device = snapshot.get("device")
    config = snapshot.get("configuration")
    if not isinstance(device, dict) or not isinstance(config, dict):
        raise BackupError("backup is missing device or configuration")
    required_config = {
        "sampling", "calibration", "channels", "radio_general", "radio_address",
        "radio_channels", "radio_down_channels", "radio_slot_time",
        "radio_network_id", "radio_join",
    }
    if set(config) != required_config:
        raise BackupError("configuration field set is incomplete or unsupported")
    for key in ("node_id", "product_code", "serial_number"):
        if not isinstance(device.get(key), int):
            raise BackupError(f"invalid device.{key}")
    if not 0 <= device["node_id"] <= 0xFFFFF:
        raise BackupError("device.node_id must fit the protocol's 20-bit field")
    if not 0 <= device["product_code"] <= 0xFF:
        raise BackupError("device.product_code must fit one byte")
    for key in ("firmware_major", "firmware_minor", "firmware_build_time"):
        if not isinstance(device.get(key), int) or device[key] < 0:
            raise BackupError(f"invalid device.{key}")
    sampling = config.get("sampling")
    if not isinstance(sampling, int) or not 1 <= sampling <= 0xFFFFFF:
        raise BackupError("sampling must fit an unsigned 24-bit positive value")
    radio_slot_time = config.get("radio_slot_time")
    if not isinstance(radio_slot_time, int) or not 0 <= radio_slot_time <= 0xFFFF:
        raise BackupError("radio_slot_time must fit an unsigned 16-bit value")
    enabled = config.get("channels", {}).get("enabled")
    if not isinstance(enabled, dict) or set(enabled) != {"x", "y", "z"}:
        raise BackupError("channels.enabled must contain x, y, and z")
    if not all(isinstance(enabled[axis], bool) for axis in ("x", "y", "z")):
        raise BackupError("channel enable values must be booleans")
    if not any(enabled.values()):
        raise BackupError("at least one measurement axis must remain enabled")
    if "storage_interval" not in snapshot or not isinstance(snapshot["storage_interval"], (list, tuple)):
        raise BackupError("backup is missing storage_interval")
    return snapshot


def encode_sampling_write(seconds: int) -> bytes:
    if not isinstance(seconds, int) or not 1 <= seconds <= 0xFFFFFF:
        raise BackupError("sampling must fit an unsigned 24-bit positive value")
    return bytes((0x82,)) + seconds.to_bytes(3, "big")


def encode_channels_write(enabled: dict[str, bool]) -> bytes:
    if set(enabled) != {"x", "y", "z"} or not all(
        isinstance(enabled[axis], bool) for axis in ("x", "y", "z")
    ):
        raise BackupError("channels must be boolean x/y/z values")
    if not any(enabled.values()):
        raise BackupError("at least one measurement axis must remain enabled")
    flags = (int(enabled["z"]) << 2) | (int(enabled["y"]) << 1) | int(enabled["x"])
    return bytes((0x9A, flags))


def encode_radio_slot_time_write(seconds: int) -> bytes:
    if not isinstance(seconds, int) or not 1 <= seconds <= 0xFFFF:
        raise BackupError("radio slot time must fit an unsigned 16-bit positive value")
    return bytes((0x90,)) + seconds.to_bytes(2, "big")


def _plain_configuration(snapshot: dict[str, Any]) -> dict[str, Any]:
    config = deepcopy(snapshot["configuration"])
    for value in config.values():
        if isinstance(value, dict):
            value.pop("header", None)
    return config


def _walk_diff(current: Any, target: Any, path: str = "configuration") -> list[dict[str, Any]]:
    if isinstance(current, dict) and isinstance(target, dict):
        changes: list[dict[str, Any]] = []
        for key in sorted(current.keys() | target.keys()):
            child = f"{path}.{key}"
            if key not in current:
                changes.append({"path": child, "current": None, "target": target[key]})
            elif key not in target:
                changes.append({"path": child, "current": current[key], "target": None})
            else:
                changes.extend(_walk_diff(current[key], target[key], child))
        return changes
    if current != target:
        return [{"path": path, "current": current, "target": target}]
    return []


def diff_snapshots(current: dict[str, Any], target: dict[str, Any]) -> list[dict[str, Any]]:
    validate_snapshot(current)
    validate_snapshot(target)
    return _walk_diff(_plain_configuration(current), _plain_configuration(target))


def build_restore_plan(
    current: dict[str, Any],
    target: dict[str, Any],
    hardware_validated_writes: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    validate_snapshot(current)
    validate_snapshot(target)
    if current["device"]["node_id"] != target["device"]["node_id"]:
        raise BackupError("target backup belongs to a different node ID")
    if current["device"]["product_code"] != target["device"]["product_code"]:
        raise BackupError("target backup belongs to a different product code")
    if current["device"]["serial_number"] != target["device"]["serial_number"]:
        raise BackupError("target backup belongs to a different serial number")
    firmware_fields = ("firmware_major", "firmware_minor", "firmware_build_time")
    if any(current["device"].get(key) != target["device"].get(key) for key in firmware_fields):
        raise BackupError("target backup was created for a different firmware build")

    current_config = current["configuration"]
    target_config = target["configuration"]
    operations = []
    if current_config["sampling"] != target_config["sampling"]:
        body = encode_sampling_write(target_config["sampling"])
        operations.append({
            "name": "sampling",
            "current": current_config["sampling"],
            "target": target_config["sampling"],
            "request_body_hex": body.hex(" "),
            "readback_query": "sampling",
            "status": "ready" if "sampling" in hardware_validated_writes else "awaiting_hardware_write_validation",
        })
    current_enabled = current_config["channels"]["enabled"]
    target_enabled = target_config["channels"]["enabled"]
    if current_enabled != target_enabled:
        body = encode_channels_write(target_enabled)
        operations.append({
            "name": "channels",
            "current": current_enabled,
            "target": target_enabled,
            "request_body_hex": body.hex(" "),
            "readback_query": "channels",
            "status": "ready" if "channels" in hardware_validated_writes else "awaiting_hardware_write_validation",
        })
    if current_config["radio_slot_time"] != target_config["radio_slot_time"]:
        target_slot = target_config["radio_slot_time"]
        body = encode_radio_slot_time_write(target_slot)
        operations.append({
            "name": "radio_slot_time",
            "current": current_config["radio_slot_time"],
            "target": target_slot,
            "request_body_hex": body.hex(" "),
            "readback_query": "radio-slot-time",
            "status": "ready" if "radio_slot_time" in hardware_validated_writes else "awaiting_hardware_write_validation",
        })

    changes = diff_snapshots(current, target)
    restorable_prefixes = (
        "configuration.sampling",
        "configuration.channels.enabled",
        "configuration.radio_slot_time",
    )
    blocked = [change for change in changes if not change["path"].startswith(restorable_prefixes)]
    return {
        "device": current["device"],
        "created_utc": utc_now(),
        "operations": operations,
        "blocked_changes": blocked,
        "requires_confirmation": f"RESTORE {current['device']['node_id']}",
        "can_apply": bool(operations) and not blocked and all(
            operation["name"] in hardware_validated_writes for operation in operations
        ),
        "writes_hardware_validated": all(
            operation["name"] in hardware_validated_writes for operation in operations
        ),
    }
