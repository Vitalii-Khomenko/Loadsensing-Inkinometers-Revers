"""Explicitly confirmed, bounded maintenance operations for a connected TIL90."""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

import serial

from tools.device_service import DeviceService, DeviceServiceError
from tools.config_backup import (
    diff_snapshots,
    encode_channels_write,
    encode_radio_slot_time_write,
)
from tools.packet_parser import ProtocolV2Header, StreamFrameParser, encode_frame
from tools.til90_cli import READ_QUERIES, _open_serial, discover_ports, run_query
from tools.firmware_service import FirmwareError, flash_g6_til90


class MaintenanceError(RuntimeError):
    pass


FACTORY_RESET_BODY = bytes.fromhex("08 75 b5 44 a2")


def factory_reset(port: str, confirmation: str, *, timeout: float = 30.0) -> dict[str, Any]:
    """Perform the APK factory-reset flow and rediscover the node without assuming its ID."""
    service = DeviceService(port)
    before = service.backup()
    old_node_id = before["device"]["node_id"]
    required = f"FACTORY RESET {old_node_id}"
    if confirmation != required:
        raise MaintenanceError(f"confirmation must be exactly: {required}")
    with service._lock, service._open() as connection:
        acknowledgement = service._write_and_ack(
            connection, "factory-reset", FACTORY_RESET_BODY, timeout=5.0
        )

    deadline = time.monotonic() + timeout
    health = after = None
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            health = service.read("health")[0]
            if health.get("status") == "ok":
                after = service.backup()
                break
        except Exception as exc:
            last_error = exc
        time.sleep(1)
    if health is None or after is None:
        raise MaintenanceError(f"factory reset acknowledged but node did not recover: {last_error}")
    try:
        changes = diff_snapshots(before, after)
    except Exception as exc:
        changes = [{"path": "configuration", "comparison_error": str(exc)}]
    return {
        "status": "factory-reset-and-rediscovered",
        "old_node_id": old_node_id,
        "new_node_id": after["device"]["node_id"],
        "acknowledgement": acknowledgement,
        "post_reset_health": health,
        "configuration_changes": changes,
        "before_backup": before,
        "after_backup": after,
    }


def _wait_for_health(connection: Any, expected_node_id: int, timeout: float) -> dict[str, Any]:
    parser = StreamFrameParser()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for body in parser.feed(connection.read(4096)):
            header = ProtocolV2Header.parse(body)
            if header.node_id != expected_node_id:
                raise MaintenanceError(
                    f"identity changed while rebooting: {header.node_id} != {expected_node_id}"
                )
            if header.am_type in {0x40, 0x46, 0x4F}:
                # Decode using the ordinary, already tested health path without a second write.
                result = READ_QUERIES["health"].decoder(body)
                return {
                    "status": "ok",
                    "header": {
                        "version": header.version,
                        "product_code": header.product_code,
                        "node_id": header.node_id,
                        "sequence_number": header.sequence_number,
                        "am_type": header.am_type,
                    },
                    "data": {
                        "timestamp": result.timestamp,
                        "uptime": result.uptime,
                        "firmware_major": result.firmware_major,
                        "firmware_minor": result.firmware_minor,
                        "battery_v": result.battery_v,
                    },
                    "rx_body": body.hex(" "),
                }
    raise MaintenanceError("timeout waiting for post-reboot health")


def reboot(port: str, confirmation: str, *, timeout: float = 20.0) -> dict[str, Any]:
    service = DeviceService(port)
    before_backup = service.backup()
    node_id = before_backup["device"]["node_id"]
    required = f"REBOOT {node_id}"
    if confirmation != required:
        raise MaintenanceError(f"confirmation must be exactly: {required}")

    before_health = next(
        item for item in before_backup["evidence"] if item.get("query") == "health"
    )
    before_uptime = before_health["data"]["uptime"]
    wire = encode_frame(b"\x09")
    sent_at = time.time()
    with _open_serial(port) as connection:
        if connection.write(wire) != len(wire):
            raise MaintenanceError("short serial write during reboot")
        connection.flush()
        health = _wait_for_health(connection, node_id, timeout)

    # A full backup proves identity and persistent configuration after reconnect.
    after_backup = service.backup()
    after_health = next(
        item for item in after_backup["evidence"] if item.get("query") == "health"
    )
    after_uptime = after_health["data"]["uptime"]
    if after_backup["device"]["node_id"] != node_id:
        raise MaintenanceError("post-reboot backup returned another node")
    configuration_changes = diff_snapshots(before_backup, after_backup)
    if configuration_changes:
        raise MaintenanceError(
            f"persistent configuration changed across reboot: {configuration_changes}"
        )
    if after_uptime >= before_uptime:
        raise MaintenanceError(
            f"uptime did not reset: before={before_uptime}, after={after_uptime}"
        )
    return {
        "status": "rebooted",
        "node_id": node_id,
        "tx_wire": wire.hex(" "),
        "sent_unix": sent_at,
        "before_uptime": before_uptime,
        "post_reboot_health": health,
        "after_uptime": after_uptime,
        "configuration_unchanged": True,
        "before_backup": before_backup,
        "after_backup": after_backup,
    }


def validate_channels(port: str, confirmation: str, *, axis: str = "z") -> dict[str, Any]:
    if axis not in {"x", "y", "z"}:
        raise MaintenanceError("axis must be x, y, or z")
    service = DeviceService(port)
    before = service.backup()
    node_id = before["device"]["node_id"]
    required = f"VALIDATE CHANNELS {node_id}"
    if confirmation != required:
        raise MaintenanceError(f"confirmation must be exactly: {required}")
    original = dict(before["configuration"]["channels"]["enabled"])
    if not original[axis]:
        raise MaintenanceError(f"selected axis {axis} is already disabled")
    changed = dict(original)
    changed[axis] = False
    if not any(changed.values()):
        raise MaintenanceError("validation may not disable every axis")

    evidence: list[dict[str, Any]] = []
    changed_attempted = False
    restore_error: Exception | None = None
    try:
        with service._open() as connection:
            evidence.append(service._write_and_ack(
                connection, "channels-identical", encode_channels_write(original)
            ))
            identical = run_query(connection, "channels", READ_QUERIES["channels"])
            evidence.append({"operation": "identical-readback", "result": identical})
            if identical.get("data", {}).get("enabled") != original:
                raise MaintenanceError("identical-value write changed the channel state")

            changed_attempted = True
            evidence.append(service._write_and_ack(
                connection, f"disable-{axis}", encode_channels_write(changed)
            ))
            changed_readback = run_query(connection, "channels", READ_QUERIES["channels"])
            evidence.append({"operation": "changed-readback", "result": changed_readback})
            if changed_readback.get("data", {}).get("enabled") != changed:
                raise MaintenanceError("changed channel state did not read back")
            live = run_query(connection, "live", READ_QUERIES["live"])
            evidence.append({"operation": "live-with-axis-disabled", "result": live})
            if live.get("status") != "ok" or axis in live.get("data", {}).get("axes", {}):
                raise MaintenanceError(f"live result still contains disabled axis {axis}")
    finally:
        if changed_attempted:
            try:
                with service._open() as connection:
                    evidence.append(service._write_and_ack(
                        connection, "restore-channels", encode_channels_write(original)
                    ))
                    restored = run_query(connection, "channels", READ_QUERIES["channels"])
                    evidence.append({"operation": "restore-readback", "result": restored})
                    if restored.get("data", {}).get("enabled") != original:
                        raise MaintenanceError("channel restore readback mismatch")
            except Exception as exc:
                restore_error = exc
    if restore_error is not None:
        raise MaintenanceError(f"mandatory channel restore failed: {restore_error}")

    after = service.backup()
    changes = diff_snapshots(before, after)
    if changes:
        raise MaintenanceError(f"configuration differs after channel restore: {changes}")
    return {
        "status": "validated-and-restored",
        "node_id": node_id,
        "temporarily_disabled_axis": axis,
        "original": original,
        "temporary": changed,
        "configuration_unchanged_after_restore": True,
        "evidence": evidence,
        "before_backup": before,
        "after_backup": after,
    }


def encode_local_sampling(duration_seconds: int, period_seconds: int) -> bytes:
    if not 1 <= duration_seconds <= 15:
        raise MaintenanceError("local sampling duration must be 1..15 seconds")
    if not 1 <= period_seconds <= duration_seconds:
        raise MaintenanceError("local sampling period must be 1..duration seconds")
    packed = (period_seconds << 28) | (duration_seconds << 4)
    return b"\x15\x00\x02" + packed.to_bytes(7, "big")


LOCAL_SAMPLING_STOP = b"\x15\x00\x02" + bytes(7)


def validate_local_sampling(
    port: str,
    confirmation: str,
    *,
    duration: int = 6,
    period: int = 2,
) -> dict[str, Any]:
    service = DeviceService(port)
    before = service.backup()
    node_id = before["device"]["node_id"]
    required = f"VALIDATE LOCAL SAMPLING {node_id}"
    if confirmation != required:
        raise MaintenanceError(f"confirmation must be exactly: {required}")
    start_body = encode_local_sampling(duration, period)
    evidence: list[dict[str, Any]] = []
    readings: list[dict[str, Any]] = []
    started = False
    rejected_error: str | None = None
    restore_error: Exception | None = None
    try:
        with service._open() as connection:
            try:
                evidence.append(service._write_and_ack(
                    connection, "start-local-sampling", start_body, timeout=5.0
                ))
            except DeviceServiceError as exc:
                if "rejected:" in str(exc):
                    rejected_error = str(exc)
                else:
                    # The node may have accepted the start even if its ACK was lost.
                    started = True
                    raise
            if rejected_error is None:
                started = True
            parser = StreamFrameParser()
            deadline = time.monotonic() + duration + 2 if started else time.monotonic()
            while started and time.monotonic() < deadline:
                for body in parser.feed(connection.read(4096)):
                    header = ProtocolV2Header.parse(body)
                    if header.node_id != node_id:
                        raise MaintenanceError("another node replied during local sampling")
                    if header.am_type in READ_QUERIES["live"].expected_am_types:
                        decoded = READ_QUERIES["live"].decoder(body)
                        readings.append({
                            "header": {
                                "node_id": header.node_id,
                                "sequence_number": header.sequence_number,
                                "am_type": header.am_type,
                            },
                            "timestamp": decoded.timestamp,
                            "temperature_c": decoded.temperature_c,
                            "axes": {
                                name: {
                                    "angle_deg": value.angle_deg,
                                    "stddev_g": value.stddev_g,
                                }
                                for name, value in decoded.axes.items()
                            },
                            "rx_body": body.hex(" "),
                        })
                    elif header.am_type != 0x00:
                        evidence.append({"operation": "unexpected-local-frame", "rx_body": body.hex(" ")})
    finally:
        if started:
            try:
                with service._open() as connection:
                    evidence.append(service._write_and_ack(
                        connection, "stop-local-sampling", LOCAL_SAMPLING_STOP, timeout=5.0
                    ))
            except Exception as exc:
                restore_error = exc
    if restore_error is not None:
        raise MaintenanceError(f"mandatory local-sampling stop failed: {restore_error}")
    if rejected_error is not None:
        after = service.backup()
        changes = diff_snapshots(before, after)
        return {
            "status": "rejected",
            "node_id": node_id,
            "operation": "local-sampling",
            "error": rejected_error,
            "tx_body": start_body.hex(" "),
            "configuration_unchanged": not changes,
            "configuration_changes": changes,
            "before_backup": before,
            "after_backup": after,
        }
    expected_minimum = duration // period
    if len(readings) < expected_minimum:
        raise MaintenanceError(
            f"local sampling returned {len(readings)} readings; expected at least {expected_minimum}"
        )

    # The watchdog stop must be followed by an ordinary one-shot reading and full backup.
    normal_live = service.read("live")[0]
    after = service.backup()
    changes = diff_snapshots(before, after)
    if changes:
        raise MaintenanceError(f"configuration differs after local sampling: {changes}")
    return {
        "status": "validated-and-stopped",
        "node_id": node_id,
        "duration_seconds": duration,
        "period_seconds": period,
        "reading_count": len(readings),
        "readings": readings,
        "normal_live_after_stop": normal_live,
        "configuration_unchanged_after_stop": True,
        "evidence": evidence,
        "before_backup": before,
        "after_backup": after,
    }


def validate_gateway_slot(port: str, confirmation: str) -> dict[str, Any]:
    service = DeviceService(port)
    before = service.backup()
    node_id = before["device"]["node_id"]
    required = f"VALIDATE GATEWAY SLOT {node_id}"
    if confirmation != required:
        raise MaintenanceError(f"confirmation must be exactly: {required}")
    original = before["configuration"]["radio_slot_time"]
    changed = original + 1 if original < 0xFFFF else original - 1
    if changed < 1:
        changed = 1
    evidence: list[dict[str, Any]] = []
    write_attempted = False
    restore_error: Exception | None = None
    try:
        with service._open() as connection:
            evidence.append(service._write_and_ack(
                connection, "gateway-slot-identical", encode_radio_slot_time_write(original)
            ))
            identical = run_query(
                connection, "radio-slot-time", READ_QUERIES["radio-slot-time"]
            )
            evidence.append({"operation": "identical-readback", "result": identical})
            if identical.get("data") != original:
                raise MaintenanceError("identical gateway slot write did not read back")

            write_attempted = True
            evidence.append(service._write_and_ack(
                connection, "gateway-slot-change", encode_radio_slot_time_write(changed)
            ))
            readback = run_query(
                connection, "radio-slot-time", READ_QUERIES["radio-slot-time"]
            )
            evidence.append({"operation": "changed-readback", "result": readback})
            if readback.get("data") != changed:
                raise MaintenanceError("changed gateway slot did not read back")
    finally:
        if write_attempted:
            try:
                with service._open() as connection:
                    evidence.append(service._write_and_ack(
                        connection,
                        "restore-gateway-slot",
                        encode_radio_slot_time_write(original),
                    ))
                    restored = run_query(
                        connection, "radio-slot-time", READ_QUERIES["radio-slot-time"]
                    )
                    evidence.append({"operation": "restore-readback", "result": restored})
                    if restored.get("data") != original:
                        raise MaintenanceError("gateway slot restore readback mismatch")
            except Exception as exc:
                restore_error = exc
    if restore_error is not None:
        raise MaintenanceError(f"mandatory gateway slot restore failed: {restore_error}")
    after = service.backup()
    changes = diff_snapshots(before, after)
    if changes:
        raise MaintenanceError(f"configuration differs after gateway slot restore: {changes}")
    return {
        "status": "validated-and-restored",
        "node_id": node_id,
        "original_seconds": original,
        "temporary_seconds": changed,
        "configuration_unchanged_after_restore": True,
        "evidence": evidence,
        "before_backup": before,
        "after_backup": after,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation",
        choices=(
            "reboot", "validate-channels", "validate-local-sampling",
            "validate-gateway-slot", "factory-reset", "flash-firmware",
        ),
    )
    parser.add_argument("--port")
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--axis", choices=("x", "y", "z"), default="z")
    parser.add_argument("--duration", type=int, default=6)
    parser.add_argument("--period", type=int, default=2)
    parser.add_argument("--firmware", help="firmware image path; APK-mapped image by default")
    parser.add_argument("--output")
    parser.add_argument("--pretty", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    port = args.port
    if port is None:
        ports = discover_ports()
        if len(ports) != 1:
            print(f"expected exactly one CP2102N, found {len(ports)}; use --port", file=sys.stderr)
            return 2
        port = str(ports[0])
    try:
        if args.operation == "reboot":
            result = reboot(port, args.confirm, timeout=args.timeout)
        elif args.operation == "factory-reset":
            result = factory_reset(port, args.confirm, timeout=args.timeout)
        elif args.operation == "flash-firmware":
            kwargs = {"timeout": args.timeout, "progress": lambda done, total: print(
                f"firmware {done}/{total} blocks ({done * 100 // total}%)", file=sys.stderr
            ) if done == total or done % 50 == 0 else None}
            if args.firmware:
                kwargs["firmware_path"] = args.firmware
            result = flash_g6_til90(port, args.confirm, **kwargs)
        elif args.operation == "validate-channels":
            result = validate_channels(port, args.confirm, axis=args.axis)
        elif args.operation == "validate-local-sampling":
            result = validate_local_sampling(
                port, args.confirm, duration=args.duration, period=args.period
            )
        else:
            result = validate_gateway_slot(port, args.confirm)
    except (
        MaintenanceError, FirmwareError, DeviceServiceError, OSError, serial.SerialException
    ) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 1
    rendered = json.dumps(result, indent=2 if args.pretty else None, sort_keys=args.pretty)
    if args.output:
        from tools.til90_cli import _save_json
        _save_json(args.output, rendered)
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
