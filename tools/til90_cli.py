"""Safe read-only Linux CLI for a directly attached TIL90/INC360 node."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from typing import Any, Callable

import serial

try:
    from tools.packet_parser import ProtocolV2Header, StreamFrameParser, encode_frame
    from tools.packet_parser import messages as _messages
except ModuleNotFoundError:  # Support ``python tools/til90_cli.py`` from repo root.
    from packet_parser import ProtocolV2Header, StreamFrameParser, encode_frame
    from packet_parser import messages as _messages

decode_bluetooth_config = _messages.decode_bluetooth_config
decode_extended_node_info = _messages.decode_extended_node_info
decode_inc360_channel_config = _messages.decode_inc360_channel_config
decode_lora_address = _messages.decode_lora_address
decode_lora_channels_config = _messages.decode_lora_channels_config
decode_lora_general_config = _messages.decode_lora_general_config
decode_lora_join_config = _messages.decode_lora_join_config
decode_lora_network_id = _messages.decode_lora_network_id
decode_lora_slot_time = _messages.decode_lora_slot_time
decode_node_health = _messages.decode_node_health
decode_node_info = _messages.decode_node_info
decode_response_code = _messages.decode_response_code
decode_sampling_rate = _messages.decode_sampling_rate
decode_stored_data_interval = _messages.decode_stored_data_interval
decode_til90_calibration = _messages.decode_til90_calibration
decode_til90_reading = _messages.decode_til90_reading
encode_history_request = _messages.encode_history_request
unwrap_recovered_message = _messages.unwrap_recovered_message


Decoder = Callable[[bytes], Any]


@dataclass(frozen=True, slots=True)
class Query:
    request_body: bytes
    expected_am_types: frozenset[int]
    decoder: Decoder
    timeout_seconds: float = 5.0


READ_QUERIES: dict[str, Query] = {
    "health": Query(b"\x01", frozenset({0x40, 0x46, 0x4F}), decode_node_health),
    "info": Query(bytes.fromhex("43 69 00 00"), frozenset({0x03, 0x09}), decode_node_info),
    "extended": Query(b"\x0e", frozenset({0x05}), decode_extended_node_info),
    "live": Query(b"\x02", frozenset({0x4C}), decode_til90_reading, 15.0),
    "sampling": Query(bytes.fromhex("00 82"), frozenset({0x82}), decode_sampling_rate),
    "calibration": Query(bytes.fromhex("00 98"), frozenset({0x98}), decode_til90_calibration),
    "channels": Query(bytes.fromhex("00 9a"), frozenset({0x9A}), decode_inc360_channel_config),
    "bluetooth": Query(bytes.fromhex("00 a5"), frozenset({0xA5}), decode_bluetooth_config),
    "interval": Query(b"\x04", frozenset({0x02}), decode_stored_data_interval),
    "radio-general": Query(bytes.fromhex("00 84"), frozenset({0x84}), decode_lora_general_config),
    "radio-address": Query(bytes.fromhex("00 83"), frozenset({0x83}), decode_lora_address),
    "radio-channels": Query(bytes.fromhex("00 85"), frozenset({0x85}), decode_lora_channels_config),
    "radio-down-channels": Query(bytes.fromhex("00 8e"), frozenset({0x8E}), decode_lora_channels_config),
    "radio-slot-time": Query(bytes.fromhex("00 90"), frozenset({0x90}), decode_lora_slot_time),
    "radio-network-id": Query(bytes.fromhex("00 8d"), frozenset({0x8D}), decode_lora_network_id),
    "radio-join": Query(bytes.fromhex("00 94"), frozenset({0x94}), decode_lora_join_config),
}

HISTORY_DECODERS: dict[int, Decoder] = {
    0x03: decode_node_info,
    0x05: decode_extended_node_info,
    0x09: decode_node_info,
    0x40: decode_node_health,
    0x46: decode_node_health,
    0x4C: decode_til90_reading,
    0x4F: decode_node_health,
    0x82: decode_sampling_rate,
    0x98: decode_til90_calibration,
    0x9A: decode_inc360_channel_config,
}

QUERY_GROUPS: dict[str, tuple[str, ...]] = {
    "identity": ("health", "info", "extended"),
    "measurement": ("live",),
    "configuration": ("sampling", "calibration", "channels", "interval"),
    "radio": (
        "radio-general",
        "radio-address",
        "radio-channels",
        "radio-down-channels",
        "radio-slot-time",
        "radio-network-id",
        "radio-join",
    ),
    "all": (
        "health",
        "info",
        "extended",
        "live",
        "sampling",
        "calibration",
        "channels",
        "interval",
        "radio-general",
        "radio-address",
        "radio-channels",
        "radio-down-channels",
        "radio-slot-time",
        "radio-network-id",
        "radio-join",
    ),
}

RESPONSE_CODES = {
    0x0000: "OK",
    0x0001: "INVALID_SIZE",
    0x0002: "INVALID_INPUT_PARAM",
    0x0003: "RESET_UNSUCCESSFUL",
    0x0004: "CONFIG_NOT_PRESENT",
    0x0005: "UNKNOWN_CMD",
    0x0006: "UNSUPPORTED_CMD",
    0x0007: "FAILED_CMD",
    0x0080: "END_OF_RECOVER_DATA",
    0x0081: "END_OF_LORA_COVERAGE_TEST",
}


def discover_ports() -> list[Path]:
    return sorted(Path("/dev/serial/by-id").glob("*CP2102N*"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _save_json(path: str, rendered: str) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(rendered + "\n", encoding="utf-8")
    destination.chmod(0o600)


def _open_serial(port: str) -> serial.Serial:
    connection = serial.Serial()
    connection.port = port
    connection.baudrate = 115200
    connection.bytesize = serial.EIGHTBITS
    connection.parity = serial.PARITY_NONE
    connection.stopbits = serial.STOPBITS_ONE
    connection.timeout = 0.1
    connection.write_timeout = 1
    connection.xonxoff = False
    connection.rtscts = False
    connection.dsrdtr = False
    connection.dtr = False
    connection.rts = False
    connection.exclusive = True
    connection.open()
    return connection


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, bytes):
        return value.hex(" ")
    return value


def run_query(connection: serial.Serial, name: str, query: Query) -> dict[str, Any]:
    request = encode_frame(query.request_body)
    tx_time = _utc_now()
    written = connection.write(request)
    connection.flush()
    if written != len(request):
        raise RuntimeError(f"short serial write: {written}/{len(request)}")

    parser = StreamFrameParser()
    deadline = time.monotonic() + query.timeout_seconds
    unexpected: list[str] = []
    while time.monotonic() < deadline:
        chunk = connection.read(4096)
        if not chunk:
            continue
        for body in parser.feed(chunk):
            rx_time = _utc_now()
            header = ProtocolV2Header.parse(body)
            if header.am_type == 0x00:
                code = decode_response_code(body)
                return {
                    "query": name,
                    "status": "device_error" if code else "ok",
                    "response_code": code,
                    "response_name": RESPONSE_CODES.get(code, "UNKNOWN_RESPONSE_CODE"),
                    "header": _jsonable(header),
                    "tx_utc": tx_time,
                    "rx_utc": rx_time,
                    "tx_wire": request.hex(" "),
                    "rx_body": body.hex(" "),
                }
            if header.am_type not in query.expected_am_types:
                unexpected.append(body.hex(" "))
                continue
            try:
                decoded = query.decoder(body)
            except Exception as exc:
                return {
                    "query": name,
                    "status": "decode_error",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "header": _jsonable(header),
                    "tx_utc": tx_time,
                    "rx_utc": rx_time,
                    "tx_wire": request.hex(" "),
                    "rx_body": body.hex(" "),
                }
            return {
                "query": name,
                "status": "ok",
                "header": _jsonable(header),
                "data": _jsonable(decoded),
                "tx_utc": tx_time,
                "rx_utc": rx_time,
                "tx_wire": request.hex(" "),
                "rx_body": body.hex(" "),
            }
    return {
        "query": name,
        "status": "timeout",
        "timeout_seconds": query.timeout_seconds,
        "tx_utc": tx_time,
        "tx_wire": request.hex(" "),
        "unexpected_frames": unexpected,
    }


def run_history(
    connection: serial.Serial,
    start_epoch: int,
    end_epoch: int,
    *,
    raw_only: bool = False,
    expected_node_id: int | None = None,
    timeout_seconds: float = 40.0,
    max_span_seconds: int = 86_400,
    max_records: int = 100,
    max_bytes: int = 262_144,
) -> dict[str, Any]:
    if not 0 <= start_epoch <= end_epoch <= 0xFFFFFFFF:
        raise ValueError("history epochs must be ordered unsigned 32-bit values")
    if end_epoch - start_epoch > max_span_seconds:
        raise ValueError("history range exceeds max_span_seconds")
    if timeout_seconds <= 0 or max_span_seconds < 0 or max_records < 1 or max_bytes < 1:
        raise ValueError("history limits must be positive")

    request = encode_frame(encode_history_request(start_epoch, end_epoch, raw_only=raw_only))
    tx_time = _utc_now()
    if connection.write(request) != len(request):
        raise RuntimeError("short serial write during history request")
    connection.flush()

    parser = StreamFrameParser()
    records: list[dict[str, Any]] = []
    unexpected: list[str] = []
    total_rx_bytes = 0
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        chunk = connection.read(4096)
        if not chunk:
            continue
        total_rx_bytes += len(chunk)
        if total_rx_bytes > max_bytes:
            return {
                "query": "history", "status": "limit_error", "limit": "max_bytes",
                "tx_utc": tx_time, "tx_wire": request.hex(" "), "records": records,
                "total_rx_bytes": total_rx_bytes, "unexpected_frames": unexpected,
            }
        for body in parser.feed(chunk):
            rx_time = _utc_now()
            header = ProtocolV2Header.parse(body)
            if expected_node_id is not None and header.node_id != expected_node_id:
                return {
                    "query": "history", "status": "identity_error",
                    "expected_node_id": expected_node_id, "actual_node_id": header.node_id,
                    "tx_utc": tx_time, "rx_utc": rx_time,
                    "tx_wire": request.hex(" "), "rx_body": body.hex(" "),
                    "records": records, "total_rx_bytes": total_rx_bytes,
                }
            if header.am_type == 0x00:
                code = decode_response_code(body)
                return {
                    "query": "history",
                    "status": "ok" if code == 0x80 else "device_error",
                    "complete": code == 0x80,
                    "response_code": code,
                    "response_name": RESPONSE_CODES.get(code, "UNKNOWN_RESPONSE_CODE"),
                    "header": _jsonable(header),
                    "start_epoch": start_epoch,
                    "end_epoch": end_epoch,
                    "raw_only": raw_only,
                    "tx_utc": tx_time,
                    "rx_utc": rx_time,
                    "tx_wire": request.hex(" "),
                    "rx_body": body.hex(" "),
                    "records": records,
                    "record_count": len(records),
                    "total_rx_bytes": total_rx_bytes,
                    "unexpected_frames": unexpected,
                }
            if header.am_type != 0x01:
                unexpected.append(body.hex(" "))
                continue
            if len(records) >= max_records:
                return {
                    "query": "history", "status": "limit_error", "limit": "max_records",
                    "tx_utc": tx_time, "tx_wire": request.hex(" "), "records": records,
                    "record_count": len(records), "total_rx_bytes": total_rx_bytes,
                    "unexpected_frames": unexpected,
                }
            capture_id, inner = unwrap_recovered_message(body)
            inner_header = ProtocolV2Header.parse(inner)
            record: dict[str, Any] = {
                "capture_id": capture_id,
                "outer_header": _jsonable(header),
                "inner_header": _jsonable(inner_header),
                "rx_utc": rx_time,
                "outer_body": body.hex(" "),
                "inner_body": inner.hex(" "),
            }
            decoder = HISTORY_DECODERS.get(inner_header.am_type)
            if decoder is None:
                record["decode_status"] = "unsupported_am_type"
            else:
                try:
                    record["data"] = _jsonable(decoder(inner))
                    record["decode_status"] = "ok"
                except Exception as exc:
                    record["decode_status"] = "decode_error"
                    record["error_type"] = type(exc).__name__
                    record["error"] = str(exc)
            records.append(record)
    return {
        "query": "history", "status": "timeout", "complete": False,
        "timeout_seconds": timeout_seconds, "start_epoch": start_epoch,
        "end_epoch": end_epoch, "raw_only": raw_only, "tx_utc": tx_time,
        "tx_wire": request.hex(" "), "records": records,
        "record_count": len(records), "total_rx_bytes": total_rx_bytes,
        "unexpected_frames": unexpected,
    }


def _resolve_names(selection: str) -> tuple[str, ...]:
    if selection in READ_QUERIES:
        return (selection,)
    return QUERY_GROUPS[selection]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only TIL90 CLI. It contains no write/reset/firmware commands."
    )
    parser.add_argument("--port", help="serial device; auto-detected when exactly one CP2102N exists")
    parser.add_argument("--pretty", action="store_true", help="pretty-print JSON")
    parser.add_argument("--output", help="also save the JSON result to this file")
    subparsers = parser.add_subparsers(dest="command", required=True)
    detect_parser = subparsers.add_parser("detect", help="list matching serial devices without opening them")
    read_parser = subparsers.add_parser("read", help="perform an allowlisted read-only query")
    read_parser.add_argument("selection", choices=sorted((*READ_QUERIES, *QUERY_GROUPS)))
    read_parser.add_argument("--count", type=int, default=1, help="repeat the selection (default: 1)")
    read_parser.add_argument("--delay", type=float, default=0.0, help="seconds between repetitions")
    history_parser = subparsers.add_parser("history", help="recover a strictly bounded read-only history range")
    history_parser.add_argument("--start-epoch", type=int, required=True)
    history_parser.add_argument("--end-epoch", type=int, required=True)
    history_parser.add_argument("--raw-only", action="store_true")
    history_parser.add_argument("--max-span-seconds", type=int, default=86_400)
    history_parser.add_argument("--max-records", type=int, default=100)
    history_parser.add_argument("--max-bytes", type=int, default=262_144)
    history_parser.add_argument("--timeout", type=float, default=40.0)
    for command_parser in (detect_parser, read_parser, history_parser):
        command_parser.add_argument(
            "--port", default=argparse.SUPPRESS,
            help="serial device (accepted before or after the subcommand)",
        )
        command_parser.add_argument(
            "--pretty", action="store_true", default=argparse.SUPPRESS,
            help="pretty-print JSON (accepted before or after the subcommand)",
        )
        command_parser.add_argument(
            "--output", default=argparse.SUPPRESS,
            help="save JSON (accepted before or after the subcommand)",
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "detect":
        rendered = json.dumps({"ports": [str(path) for path in discover_ports()]}, indent=2)
        if args.output:
            _save_json(args.output, rendered)
        print(rendered)
        return 0

    port = args.port
    if args.command == "read" and (args.count < 1 or args.delay < 0):
        print("--count must be at least 1 and --delay cannot be negative", file=sys.stderr)
        return 2
    if port is None:
        ports = discover_ports()
        if len(ports) != 1:
            print(f"expected exactly one CP2102N, found {len(ports)}; use --port", file=sys.stderr)
            return 2
        port = str(ports[0])

    if args.command == "history":
        try:
            with _open_serial(port) as connection:
                identity = run_query(connection, "health", READ_QUERIES["health"])
                if identity["status"] != "ok":
                    output = {"query": "history", "status": "preflight_error", "identity": identity}
                else:
                    output = run_history(
                        connection, args.start_epoch, args.end_epoch,
                        raw_only=args.raw_only,
                        expected_node_id=identity["header"]["node_id"],
                        timeout_seconds=args.timeout,
                        max_span_seconds=args.max_span_seconds,
                        max_records=args.max_records,
                        max_bytes=args.max_bytes,
                    )
                    output["identity"] = identity
        except (ValueError, OSError, serial.SerialException, RuntimeError) as exc:
            print(json.dumps({"status": "host_error", "error": str(exc)}), file=sys.stderr)
            return 2
        rendered = json.dumps(output, indent=2 if args.pretty else None, sort_keys=args.pretty)
        if args.output:
            _save_json(args.output, rendered)
        print(rendered)
        return 0 if output["status"] == "ok" else 1

    results: list[dict[str, Any]] = []
    try:
        with _open_serial(port) as connection:
            for iteration in range(1, args.count + 1):
                for name in _resolve_names(args.selection):
                    result = run_query(connection, name, READ_QUERIES[name])
                    if args.count > 1:
                        result["iteration"] = iteration
                    results.append(result)
                if iteration < args.count and args.delay:
                    time.sleep(args.delay)
    except (OSError, serial.SerialException) as exc:
        print(json.dumps({"status": "host_error", "error": str(exc)}), file=sys.stderr)
        return 2

    output: Any = results[0] if len(results) == 1 else results
    rendered = json.dumps(output, indent=2 if args.pretty else None, sort_keys=args.pretty)
    if args.output:
        _save_json(args.output, rendered)
    print(rendered)
    return 1 if any(result["status"] != "ok" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
