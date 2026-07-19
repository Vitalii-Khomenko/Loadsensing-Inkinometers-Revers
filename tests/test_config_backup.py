from copy import deepcopy

import pytest

from tools.config_backup import (
    BackupError,
    build_restore_plan,
    create_snapshot,
    diff_snapshots,
    encode_channels_write,
    encode_sampling_write,
    encode_radio_slot_time_write,
    sign_snapshot,
    validate_snapshot,
)


def sample_results() -> list[dict]:
    header = {"node_id": 101677, "product_code": 0x4E}
    values = {
        "health": {},
        "info": {"serial_number": 101677, "firmware_major": 2, "firmware_minor": 81, "firmware_build_time": 0},
        "extended": {"name": "LS-G6-TIL90-I"},
        "sampling": 300,
        "calibration": {"x": 0.0, "y": 0.0, "z": 0.0},
        "channels": {"version": 0, "reserved": 0, "enabled": {"x": True, "y": True, "z": True}},
        "interval": [0, 0],
        "radio-general": {"radio_enabled": False, "tx_power": 20},
        "radio-address": 0,
        "radio-channels": {"enabled": [False] * 8},
        "radio-down-channels": {"enabled": [False] * 8},
        "radio-slot-time": 0,
        "radio-network-id": 0,
        "radio-join": {"dev_eui": "0000000000000000", "app_eui": "0000000000000000"},
    }
    return [
        {"query": name, "status": "ok", "header": header, "data": data, "tx_wire": "10 02", "rx_body": "41 4e"}
        for name, data in values.items()
    ]


def sample_snapshot() -> dict:
    return create_snapshot(sample_results())


def changed(snapshot: dict, path: tuple[str, ...], value) -> dict:
    result = deepcopy(snapshot)
    cursor = result
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = value
    return sign_snapshot(result)


def test_snapshot_checksum_detects_any_tampering() -> None:
    snapshot = sample_snapshot()
    assert validate_snapshot(snapshot) is snapshot
    snapshot["configuration"]["sampling"] = 301
    with pytest.raises(BackupError, match="checksum mismatch"):
        validate_snapshot(snapshot)


def test_snapshot_rejects_incomplete_capture() -> None:
    with pytest.raises(BackupError, match="missing=.*radio-join"):
        create_snapshot(sample_results()[:-1])


def test_snapshot_rejects_recomputed_but_structurally_incomplete_config() -> None:
    snapshot = sample_snapshot()
    del snapshot["configuration"]["radio_join"]
    snapshot = sign_snapshot(snapshot)
    with pytest.raises(BackupError, match="field set"):
        validate_snapshot(snapshot)


def test_confirmed_write_serializers() -> None:
    assert encode_sampling_write(300) == bytes.fromhex("82 00 01 2c")
    assert encode_channels_write({"x": True, "y": True, "z": True}) == bytes.fromhex("9a 07")
    assert encode_channels_write({"x": True, "y": False, "z": True}) == bytes.fromhex("9a 05")
    assert encode_radio_slot_time_write(3000) == bytes.fromhex("90 0b b8")
    with pytest.raises(BackupError):
        encode_sampling_write(0)
    with pytest.raises(BackupError):
        encode_channels_write({"x": False, "y": False, "z": False})
    with pytest.raises(BackupError):
        encode_radio_slot_time_write(0)


def test_restore_plan_requires_hardware_validation_and_exact_device() -> None:
    current = sample_snapshot()
    target = changed(current, ("configuration", "sampling"), 301)
    pending = build_restore_plan(current, target)
    assert pending["operations"][0]["request_body_hex"] == "82 00 01 2d"
    assert not pending["can_apply"]
    ready = build_restore_plan(current, target, frozenset({"sampling"}))
    assert ready["can_apply"]
    assert ready["requires_confirmation"] == "RESTORE 101677"

    other = changed(target, ("device", "node_id"), 42)
    with pytest.raises(BackupError, match="different node ID"):
        build_restore_plan(current, other, frozenset({"sampling"}))


def test_radio_change_is_visible_but_blocked() -> None:
    current = sample_snapshot()
    target = changed(current, ("configuration", "radio_general", "tx_power"), 14)
    changes = diff_snapshots(current, target)
    assert changes == [{"path": "configuration.radio_general.tx_power", "current": 20, "target": 14}]
    plan = build_restore_plan(current, target, frozenset({"sampling", "channels"}))
    assert plan["blocked_changes"] == changes
    assert not plan["can_apply"]


def test_radio_slot_time_has_a_separate_guarded_restore_operation() -> None:
    current = sample_snapshot()
    target = changed(current, ("configuration", "radio_slot_time"), 3000)
    pending = build_restore_plan(current, target, frozenset({"sampling", "channels"}))
    assert pending["operations"][0]["name"] == "radio_slot_time"
    assert pending["operations"][0]["request_body_hex"] == "90 0b b8"
    assert not pending["can_apply"]
    ready = build_restore_plan(
        current, target, frozenset({"sampling", "channels", "radio_slot_time"})
    )
    assert ready["can_apply"]
