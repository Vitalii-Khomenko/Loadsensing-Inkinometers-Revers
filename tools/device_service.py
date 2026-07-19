"""Serialized access to a TIL90 node and guarded configuration restore."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import threading
import time
from typing import Any, Callable

import serial

from tools.config_backup import (
    BackupError,
    build_restore_plan,
    create_snapshot,
    diff_snapshots,
    encode_channels_write,
    encode_radio_slot_time_write,
    encode_sampling_write,
    validate_snapshot,
)
from tools.packet_parser import ProtocolV2Header, StreamFrameParser, encode_frame
from tools.til90_cli import (
    QUERY_GROUPS,
    READ_QUERIES,
    RESPONSE_CODES,
    _open_serial,
    decode_response_code,
    discover_ports,
    run_history,
    run_query,
)
from tools.usb_diagnostics import stable_alias


BACKUP_QUERIES = (
    "health", "info", "extended", "sampling", "calibration", "channels",
    "interval", "radio-general", "radio-address", "radio-channels",
    "radio-down-channels", "radio-slot-time", "radio-network-id", "radio-join",
)
HARDWARE_VALIDATED_WRITES = frozenset({"sampling", "channels", "radio_slot_time"})


class DeviceServiceError(RuntimeError):
    pass


class DeviceService:
    """One lock and one allowlist around every serial transaction."""

    def __init__(
        self,
        port: str | None = None,
        *,
        writes_enabled: bool = False,
        hardware_validated_writes: frozenset[str] = HARDWARE_VALIDATED_WRITES,
        opener: Callable[[str], Any] = _open_serial,
        query_runner: Callable[[Any, str, Any], dict[str, Any]] = run_query,
        read_retries: int = 2,
    ) -> None:
        self.port = port
        self.writes_enabled = writes_enabled
        self.hardware_validated_writes = hardware_validated_writes
        self._opener = opener
        self._query_runner = query_runner
        self.read_retries = max(0, read_retries)
        self._lock = threading.RLock()
        self._reconnect_count = 0
        self._last_connection_error: str | None = None
        self._last_connection_success: float | None = None

    def resolve_port(self) -> str:
        if self.port:
            return stable_alias(self.port) or self.port
        ports = discover_ports()
        if len(ports) != 1:
            raise DeviceServiceError(
                f"expected exactly one CP2102N, found {len(ports)}; configure --port"
            )
        return str(ports[0])

    def status(self) -> dict[str, Any]:
        ports = [str(path) for path in discover_ports()]
        selected = self.port or (ports[0] if len(ports) == 1 else None)
        available = self._lock.acquire(blocking=False)
        if available:
            self._lock.release()
        return {
            "ports": ports,
            "selected_port": selected,
            "device_detected": selected is not None and Path(selected).exists(),
            "busy": not available,
            "writes_enabled": self.writes_enabled,
            "hardware_validated_writes": sorted(self.hardware_validated_writes),
            "stable_port": stable_alias(selected) if selected else None,
            "reconnect_count": self._reconnect_count,
            "last_connection_error": self._last_connection_error,
            "last_connection_success_epoch": self._last_connection_success,
        }

    @staticmethod
    def resolve_selection(selection: str) -> tuple[str, ...]:
        if selection in READ_QUERIES:
            return (selection,)
        if selection in QUERY_GROUPS:
            return QUERY_GROUPS[selection]
        raise DeviceServiceError(f"unknown read selection: {selection}")

    def _open(self):
        return closing(self._opener(self.resolve_port()))

    def _read_transaction(self, operation: Callable[[Any], Any]) -> Any:
        """Retry only idempotent read transactions after an OS/serial disconnect."""
        with self._lock:
            for attempt in range(self.read_retries + 1):
                try:
                    with self._open() as connection:
                        result = operation(connection)
                    self._last_connection_success = time.time()
                    self._last_connection_error = None
                    return result
                except (OSError, serial.SerialException) as exc:
                    self._last_connection_error = f"{type(exc).__name__}: {exc}"
                    if attempt >= self.read_retries:
                        raise
                    self._reconnect_count += 1
                    time.sleep(min(0.25 * (2 ** attempt), 1.0))
        raise DeviceServiceError("read transaction ended unexpectedly")

    def read(self, selection: str, *, count: int = 1, delay: float = 0.0) -> list[dict[str, Any]]:
        if not 1 <= count <= 100:
            raise DeviceServiceError("count must be between 1 and 100")
        if not 0 <= delay <= 60:
            raise DeviceServiceError("delay must be between 0 and 60 seconds")
        names = self.resolve_selection(selection)
        def transaction(connection: Any) -> list[dict[str, Any]]:
            results: list[dict[str, Any]] = []
            for iteration in range(1, count + 1):
                for name in names:
                    result = self._query_runner(connection, name, READ_QUERIES[name])
                    if count > 1:
                        result["iteration"] = iteration
                    results.append(result)
                if iteration < count and delay:
                    time.sleep(delay)
            return results
        return self._read_transaction(transaction)

    def backup(self) -> dict[str, Any]:
        def transaction(connection: Any) -> dict[str, Any]:
            results: list[dict[str, Any]] = []
            for name in BACKUP_QUERIES:
                results.append(self._query_runner(connection, name, READ_QUERIES[name]))
            return create_snapshot(results)
        return self._read_transaction(transaction)

    def history(
        self,
        start_epoch: int,
        end_epoch: int,
        *,
        max_records: int = 500,
    ) -> dict[str, Any]:
        def transaction(connection: Any) -> dict[str, Any]:
            identity = self._query_runner(connection, "health", READ_QUERIES["health"])
            if identity.get("status") != "ok":
                raise DeviceServiceError("history preflight health read failed")
            result = run_history(
                connection,
                start_epoch,
                end_epoch,
                expected_node_id=identity["header"]["node_id"],
                max_span_seconds=7 * 24 * 3600,
                max_records=max_records,
                max_bytes=2 * 1024 * 1024,
                timeout_seconds=40,
            )
            result["identity"] = identity
            return result
        return self._read_transaction(transaction)

    def preview_restore(self, target: dict[str, Any]) -> dict[str, Any]:
        validate_snapshot(target)
        plan = build_restore_plan(self.backup(), target, self.hardware_validated_writes)
        plan["writes_enabled"] = self.writes_enabled
        plan["can_apply"] = plan["can_apply"] and self.writes_enabled
        if not self.writes_enabled:
            plan["apply_block_reason"] = "restart the web service with --enable-writes"
        return plan

    @staticmethod
    def _write_and_ack(connection: Any, name: str, body: bytes, timeout: float = 5.0) -> dict[str, Any]:
        wire = encode_frame(body)
        if connection.write(wire) != len(wire):
            raise DeviceServiceError(f"short serial write during {name}")
        connection.flush()
        parser = StreamFrameParser()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for response in parser.feed(connection.read(4096)):
                header = ProtocolV2Header.parse(response)
                if header.am_type != 0x00:
                    continue
                code = decode_response_code(response)
                evidence = {
                    "operation": name,
                    "tx_wire": wire.hex(" "),
                    "rx_body": response.hex(" "),
                    "response_code": code,
                    "response_name": RESPONSE_CODES.get(code, "UNKNOWN_RESPONSE_CODE"),
                }
                if code:
                    raise DeviceServiceError(f"{name} rejected: {evidence['response_name']}")
                return evidence
        raise DeviceServiceError(f"timeout waiting for {name} acknowledgement")

    @staticmethod
    def _operation_value(snapshot: dict[str, Any], name: str) -> Any:
        if name == "sampling":
            return snapshot["configuration"]["sampling"]
        if name == "radio_slot_time":
            return snapshot["configuration"]["radio_slot_time"]
        return snapshot["configuration"]["channels"]["enabled"]

    @staticmethod
    def _encode_operation(name: str, value: Any) -> bytes:
        if name == "sampling":
            return encode_sampling_write(value)
        if name == "channels":
            return encode_channels_write(value)
        if name == "radio_slot_time":
            return encode_radio_slot_time_write(value)
        raise DeviceServiceError(f"unsupported restore operation: {name}")

    @staticmethod
    def _readback_value(result: dict[str, Any], name: str) -> Any:
        if result.get("status") != "ok":
            raise DeviceServiceError(f"{name} readback failed: {result.get('status')}")
        if name == "sampling":
            return result["data"]
        if name == "radio_slot_time":
            return result["data"]
        return result["data"]["enabled"]

    def apply_restore(self, target: dict[str, Any], confirmation: str) -> dict[str, Any]:
        validate_snapshot(target)
        if not self.writes_enabled:
            raise DeviceServiceError("hardware writes are disabled; restart with --enable-writes")

        with self._lock:
            current = self.backup()
            plan = build_restore_plan(current, target, self.hardware_validated_writes)
            if confirmation != plan["requires_confirmation"]:
                raise DeviceServiceError("confirmation text does not match")
            if not plan["can_apply"]:
                raise DeviceServiceError("restore plan is empty, blocked, or not hardware-validated")

            applied: list[str] = []
            evidence: list[dict[str, Any]] = []
            try:
                with self._open() as connection:
                    for operation in plan["operations"]:
                        name = operation["name"]
                        target_value = self._operation_value(target, name)
                        evidence.append(self._write_and_ack(
                            connection, name, self._encode_operation(name, target_value)
                        ))
                        applied.append(name)
                        query_name = "radio-slot-time" if name == "radio_slot_time" else name
                        readback = self._query_runner(connection, query_name, READ_QUERIES[query_name])
                        evidence.append({"operation": name, "readback": readback})
                        if self._readback_value(readback, name) != target_value:
                            raise DeviceServiceError(f"{name} readback does not match target")
                post_backup = self.backup()
                remaining = diff_snapshots(post_backup, target)
                if remaining:
                    raise DeviceServiceError(f"post-restore configuration differs from target: {remaining}")
            except Exception as original:
                rollback: list[dict[str, Any]] = []
                rollback_errors: list[str] = []
                if applied:
                    try:
                        with self._open() as connection:
                            for name in reversed(applied):
                                old = self._operation_value(current, name)
                                rollback.append(self._write_and_ack(
                                    connection, f"rollback-{name}", self._encode_operation(name, old)
                                ))
                                query_name = "radio-slot-time" if name == "radio_slot_time" else name
                                result = self._query_runner(connection, query_name, READ_QUERIES[query_name])
                                rollback.append({"operation": f"rollback-{name}", "readback": result})
                                if self._readback_value(result, name) != old:
                                    rollback_errors.append(f"{name} rollback readback mismatch")
                    except Exception as rollback_error:
                        rollback_errors.append(str(rollback_error))
                raise DeviceServiceError(
                    f"restore failed: {original}; rollback_errors={rollback_errors}; "
                    f"evidence={evidence}; rollback={rollback}"
                ) from original

            return {"status": "restored", "plan": plan, "evidence": evidence, "post_backup": post_backup}


def serial_error_message(exc: Exception) -> str:
    if isinstance(exc, (OSError, serial.SerialException, BackupError, DeviceServiceError)):
        return str(exc)
    return f"unexpected {type(exc).__name__}: {exc}"
