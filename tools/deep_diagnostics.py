"""Read-only layered diagnostics for responsive and damaged TIL90 sensors."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import io
import math
import statistics
import time
from typing import Any, Callable

from tools.device_service import BACKUP_QUERIES
from tools.packet_parser import ProtocolV2Header, StreamFrameParser, encode_frame
from tools.packet_parser.frame import FrameError
from tools.til90_cli import READ_QUERIES
from tools.usb_diagnostics import diagnose


HEALTH_ATTEMPTS = 5
IDENTITY_ATTEMPTS = 5
MEASUREMENT_ATTEMPTS = 5
REFERENCE_PRODUCT = 0x4E
REFERENCE_FIRMWARE = (2, 81)
REFERENCE_EUROPE_UPLINKS = [
    868_100_000, 868_300_000, 868_500_000,
    868_850_000, 869_050_000, 869_525_000, 0, 0,
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _step(name: str, status: str, detail: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def _attempt(device: Any, query: str) -> dict[str, Any]:
    started = time.monotonic()
    try:
        result = device.read(query)[0]
        return {
            "query": query,
            "latency_ms": round((time.monotonic() - started) * 1000, 1),
            "status": result.get("status", "unknown"),
            "result": result,
        }
    except Exception as exc:
        return {
            "query": query,
            "latency_ms": round((time.monotonic() - started) * 1000, 1),
            "status": "exception",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def _passive_bootloader_probe(device: Any, duration_seconds: float = 1.5) -> dict[str, Any]:
    """Listen without transmitting and report only known XMODEM control-byte hints."""
    if not hasattr(device, "_read_transaction"):
        return {"status": "unavailable", "detail": "Raw serial probing is unavailable."}

    def transaction(connection: Any) -> dict[str, Any]:
        deadline = time.monotonic() + duration_seconds
        raw = bytearray()
        while time.monotonic() < deadline and len(raw) < 4096:
            chunk = connection.read(4096)
            if chunk:
                raw.extend(chunk)
        controls = {
            "xmodem_crc_requests": raw.count(0x43),
            "xmodem_nak": raw.count(0x15),
            "xmodem_cancel": raw.count(0x18),
            "xmodem_ack": raw.count(0x06),
        }
        control_count = sum(controls.values())
        framed_protocol_marker = bytes((0x10, 0x02)) in raw
        signal_detected = (
            not framed_protocol_marker
            and control_count >= 2
            and control_count / max(1, len(raw)) >= 0.8
        )
        return {
            "status": "signal-detected" if signal_detected else "quiet",
            "bytes_received": len(raw),
            "control_bytes": controls,
            "framed_protocol_marker": framed_protocol_marker,
            "raw_prefix_hex": bytes(raw[:128]).hex(" "),
            "detail": (
                "Possible bootloader/XMODEM control bytes were observed without transmitting."
                if signal_detected
                else "No passive bootloader signal was observed; this does not prove that the bootloader is absent."
            ),
        }

    try:
        return device._read_transaction(transaction)
    except Exception as exc:
        return {
            "status": "exception",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "detail": "The passive serial listen could not be completed.",
        }


def _framed_health_probe(device: Any, timeout_seconds: float = 5.0) -> dict[str, Any]:
    """Send one read-only health request while counting bytes, frames, and framing errors."""
    if not hasattr(device, "_read_transaction"):
        return {"status": "unavailable", "detail": "Raw framing diagnostics are unavailable."}

    def transaction(connection: Any) -> dict[str, Any]:
        request = encode_frame(READ_QUERIES["health"].request_body)
        started = time.monotonic()
        written = connection.write(request)
        connection.flush()
        parser = StreamFrameParser()
        byte_count = frame_count = framing_errors = 0
        raw_prefix = bytearray()
        headers: list[dict[str, int]] = []
        error_messages: list[str] = []
        deadline = started + timeout_seconds
        while time.monotonic() < deadline:
            chunk = connection.read(4096)
            if not chunk:
                continue
            byte_count += len(chunk)
            raw_prefix.extend(chunk[: max(0, 256 - len(raw_prefix))])
            try:
                frames = parser.feed(chunk)
            except FrameError as exc:
                framing_errors += 1
                error_messages.append(f"{type(exc).__name__}: {exc}")
                parser = StreamFrameParser()
                continue
            for body in frames:
                frame_count += 1
                try:
                    header = ProtocolV2Header.parse(body)
                    headers.append({
                        "node_id": header.node_id,
                        "product_code": header.product_code,
                        "am_type": header.am_type,
                    })
                except Exception as exc:
                    error_messages.append(f"{type(exc).__name__}: {exc}")
                if headers:
                    deadline = time.monotonic()
                    break
        return {
            "status": "framed-response" if headers else (
                "malformed-data" if byte_count else "no-bytes"
            ),
            "request_bytes_written": written,
            "bytes_received": byte_count,
            "frames_decoded": frame_count,
            "framing_errors": framing_errors,
            "headers": headers,
            "errors": error_messages,
            "latency_ms": round((time.monotonic() - started) * 1000, 1),
            "raw_prefix_hex": bytes(raw_prefix).hex(" "),
        }

    try:
        return device._read_transaction(transaction)
    except Exception as exc:
        return {
            "status": "exception",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "bytes_received": 0,
            "frames_decoded": 0,
            "framing_errors": 0,
        }


def _valid(attempts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in attempts if item.get("status") == "ok"]


def _health_analysis(attempts: list[dict[str, Any]], recent: list[dict[str, Any]]) -> dict[str, Any]:
    valid = _valid(attempts)
    data = [item["result"].get("data", {}) for item in valid]
    node_ids = [item["result"].get("header", {}).get("node_id") for item in valid]
    batteries = [item.get("battery_v") for item in data if item.get("battery_v") is not None]
    temperatures = [item.get("temperature_c") for item in data if item.get("temperature_c") is not None]
    uptimes = [item.get("uptime") for item in data if item.get("uptime") is not None]
    stored_uptimes = [item.get("uptime") for item in reversed(recent) if item.get("uptime") is not None]
    uptime_resets = sum(
        later < earlier for earlier, later in zip(stored_uptimes, stored_uptimes[1:])
    )
    return {
        "successful_attempts": len(valid),
        "consistent_node_id": len(set(node_ids)) <= 1,
        "node_ids": node_ids,
        "battery_v": batteries[-1] if batteries else None,
        "temperature_c": temperatures[-1] if temperatures else None,
        "uptime_seconds": uptimes[-1] if uptimes else None,
        "uptime_resets_in_stored_records": uptime_resets,
        "latency_ms": [item["latency_ms"] for item in attempts],
    }


def _measurement_analysis(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    valid = _valid(attempts)
    rows = [item["result"].get("data", {}) for item in valid]
    axis_values: dict[str, list[float]] = {axis: [] for axis in "xyz"}
    stddev_values: dict[str, list[float]] = {axis: [] for axis in "xyz"}
    timestamps: list[int] = []
    error_codes: list[int] = []
    gravity_norms: list[float] = []
    for row in rows:
        if row.get("timestamp") is not None:
            timestamps.append(int(row["timestamp"]))
        error_codes.append(int(row.get("error_code", 0)))
        axes = row.get("axes") or {}
        angles = []
        for axis in "xyz":
            reading = axes.get(axis)
            if not reading:
                continue
            angle = float(reading["angle_deg"])
            axis_values[axis].append(angle)
            stddev_values[axis].append(float(reading.get("stddev_g", 0)))
            angles.append(angle)
        if angles:
            gravity_norms.append(sum(math.sin(math.radians(value)) ** 2 for value in angles))
    ranges = {
        axis: (max(values) - min(values) if values else None)
        for axis, values in axis_values.items()
    }
    repeated_timestamps = len(timestamps) - len(set(timestamps))
    enabled_axes = [axis.upper() for axis, values in axis_values.items() if values]
    stuck_candidates = [
        axis.upper() for axis, values in axis_values.items()
        if len(values) >= 3 and max(values) - min(values) < 0.0001
    ]
    high_noise_axes = [
        axis.upper() for axis, values in stddev_values.items()
        if values and max(values) > 0.02
    ]
    impossible_angles = any(
        abs(value) > 90.5 for values in axis_values.values() for value in values
    )
    return {
        "successful_attempts": len(valid),
        "enabled_axes": enabled_axes,
        "error_codes": error_codes,
        "nonzero_error_codes": sorted({value for value in error_codes if value}),
        "timestamps": timestamps,
        "repeated_timestamps": repeated_timestamps,
        "axis_ranges_deg": ranges,
        "stuck_axis_candidates": stuck_candidates,
        "high_noise_axes": high_noise_axes,
        "impossible_angle_detected": impossible_angles,
        "gravity_vector_norm_min": min(gravity_norms) if gravity_norms else None,
        "gravity_vector_norm_max": max(gravity_norms) if gravity_norms else None,
        "mean_latency_ms": (
            round(statistics.mean(item["latency_ms"] for item in attempts), 1)
            if attempts else None
        ),
    }


def _configuration_analysis(matrix: list[dict[str, Any]]) -> dict[str, Any]:
    by_name = {
        item["query"]: item["result"].get("data", {})
        for item in matrix if item.get("status") == "ok"
    }
    info = by_name.get("info", {})
    general = by_name.get("radio-general", {})
    uplink = by_name.get("radio-channels", {})
    channels = by_name.get("channels", {})
    address = by_name.get("radio-address")
    network_id = by_name.get("radio-network-id")
    europe_match = (
        general.get("mac_version") == 0
        and general.get("spreading_factor") == 11
        and general.get("tx_power") == 14
        and general.get("etsi_enabled") is True
        and general.get("adr_enabled") is True
        and list(uplink.get("frequencies_hz", [])) == REFERENCE_EUROPE_UPLINKS
    )
    return {
        "queries_ok": sum(item.get("status") == "ok" for item in matrix),
        "queries_total": len(matrix),
        "failed_queries": [item["query"] for item in matrix if item.get("status") != "ok"],
        "product_matches_reference": (
            next((item["result"].get("header", {}).get("product_code") for item in matrix
                  if item.get("status") == "ok" and item.get("result")), None)
            == REFERENCE_PRODUCT
        ),
        "firmware_matches_reference": (
            info.get("firmware_major"), info.get("firmware_minor")
        ) == REFERENCE_FIRMWARE,
        "firmware": (
            f"{info.get('firmware_major')}.{info.get('firmware_minor')}"
            if info.get("firmware_major") is not None else None
        ),
        "enabled_axes": channels.get("enabled"),
        "factory_reset_address": address == 0xFFFFFFFF,
        "network_id_present": isinstance(network_id, int) and network_id > 0,
        "embedded_europe_match": europe_match,
    }


def _history_check(device: Any, health_attempts: list[dict[str, Any]]) -> dict[str, Any]:
    valid = _valid(health_attempts)
    if not valid:
        return {"status": "skipped", "detail": "History requires a valid health identity."}
    timestamp = valid[-1]["result"].get("data", {}).get("timestamp")
    if not isinstance(timestamp, int) or timestamp <= 0:
        return {"status": "skipped", "detail": "Health did not contain a usable sensor timestamp."}
    started = time.monotonic()
    try:
        result = device.history(max(0, timestamp - 900), timestamp, max_records=200)
        return {
            "status": result.get("status", "unknown"),
            "complete": bool(result.get("complete")),
            "records": len(result.get("records", [])),
            "completion_code": result.get("completion_code"),
            "latency_ms": round((time.monotonic() - started) * 1000, 1),
            "detail": "A bounded 15-minute, 200-record read-only history request was used.",
        }
    except Exception as exc:
        return {
            "status": "exception",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "latency_ms": round((time.monotonic() - started) * 1000, 1),
        }


def _classify(
    usb: dict[str, Any], serial_probe: dict[str, Any], bootloader: dict[str, Any],
    health: dict[str, Any], identity_ok: int, config: dict[str, Any],
    measurement: dict[str, Any], history: dict[str, Any],
) -> tuple[str, str, str]:
    if not usb.get("exists"):
        return "failed", "usb_not_enumerated", "The USB adapter is not visible to Linux."
    if not usb.get("readable") or not usb.get("writable"):
        return "failed", "usb_access_denied", "Linux cannot open the serial adapter with read/write access."
    if bootloader.get("status") == "signal-detected":
        return "failed", "possible_bootloader_mode", "Passive XMODEM control bytes suggest bootloader or recovery mode."
    if not health["successful_attempts"]:
        if serial_probe.get("bytes_received", 0):
            return "failed", "serial_framing_or_firmware", "The UART produced bytes but no valid health response."
        return "failed", "sensor_power_mcu_or_uart", "CP2102N opens, but the sensor MCU returned no bytes."
    if not health["consistent_node_id"]:
        return "failed", "unstable_identity", "Repeated health replies reported inconsistent node identities."
    if health.get("battery_v") is not None and health["battery_v"] < 3.0:
        return "warning", "power_problem", "The sensor responds but reports a low supply voltage."
    if health["uptime_resets_in_stored_records"]:
        return "warning", "repeated_sensor_resets", "Stored health records show uptime decreasing across observations."
    if identity_ok < IDENTITY_ATTEMPTS:
        return "warning", "identity_or_firmware_instability", "Health works, but repeated identity reads are unreliable."
    if config["failed_queries"]:
        return "warning", "configuration_or_firmware_problem", "One or more read-only configuration families failed."
    if not measurement["successful_attempts"] or measurement["nonzero_error_codes"]:
        return "failed", "measurement_hardware_or_firmware", "Identity works, but live measurement is missing or reports an error."
    if measurement["impossible_angle_detected"]:
        return "warning", "measurement_plausibility_problem", "At least one reported angle is outside the expected range."
    if history.get("status") not in {"ok", "skipped"} or history.get("complete") is False:
        return "warning", "history_or_storage_problem", "Live operation works, but the bounded history check did not complete."
    return "ready", "sensor_responsive_phone_or_app_likely", "USB diagnostics passed; a phone-only failure is likely Android, OTG, permission, cable, or app state."


def run_deep_diagnostics(
    device: Any,
    store: Any | None = None,
    *,
    usb_probe: Callable[[str | None], dict[str, Any]] = diagnose,
) -> dict[str, Any]:
    """Run a bounded diagnostic suite that never writes persistent sensor state."""
    started_utc = _utc_now()
    started = time.monotonic()
    status = device.status()
    usb = usb_probe(status.get("selected_port"))
    report: dict[str, Any] = {
        "schema": "til90-deep-diagnostics/v1",
        "started_utc": started_utc,
        "completed_utc": None,
        "duration_seconds": None,
        "read_only": True,
        "persistent_writes_sent": 0,
        "host": {"device_status": status, "usb": usb},
        "steps": [],
        "recommendations": [],
    }
    if not usb.get("exists") or not usb.get("readable") or not usb.get("writable"):
        overall, classification, headline = _classify(
            usb, {}, {}, {"successful_attempts": 0, "consistent_node_id": True,
                          "uptime_resets_in_stored_records": 0},
            0, {"failed_queries": []}, {"successful_attempts": 0,
                                         "nonzero_error_codes": [],
                                         "impossible_angle_detected": False},
            {"status": "skipped"},
        )
        report["summary"] = {"overall": overall, "classification": classification, "headline": headline}
        report["steps"] = [_step("USB and permissions", overall, headline)]
        report["recommendations"] = usb.get("recommendations", [])
        report["completed_utc"] = _utc_now()
        report["duration_seconds"] = round(time.monotonic() - started, 2)
        return report

    bootloader = _passive_bootloader_probe(device)
    serial_probe = _framed_health_probe(device)
    health_attempts = [_attempt(device, "health") for _ in range(HEALTH_ATTEMPTS)]
    identity_attempts = [_attempt(device, "info") for _ in range(IDENTITY_ATTEMPTS)]
    health_node_ids = [
        item["result"].get("header", {}).get("node_id") for item in _valid(health_attempts)
    ]
    health_node_id = health_node_ids[-1] if health_node_ids else None
    recent = (
        store.recent_health(node_id=health_node_id, limit=50)
        if store and hasattr(store, "recent_health") else []
    )
    health_analysis = _health_analysis(health_attempts, recent)

    matrix_names = tuple(name for name in BACKUP_QUERIES if name not in {"health", "info"})
    query_matrix = [_attempt(device, name) for name in matrix_names]
    configuration_analysis = _configuration_analysis(identity_attempts[:1] + query_matrix)
    measurement_attempts = [_attempt(device, "live") for _ in range(MEASUREMENT_ATTEMPTS)]
    measurement_analysis = _measurement_analysis(measurement_attempts)
    history = _history_check(device, health_attempts)
    identity_ok = len(_valid(identity_attempts))

    overall, classification, headline = _classify(
        usb, serial_probe, bootloader, health_analysis, identity_ok,
        configuration_analysis, measurement_analysis, history,
    )
    steps = [
        _step("USB and permissions", "passed", "The CP2102N path exists and is accessible."),
        _step(
            "Passive bootloader listen",
            "warning" if bootloader.get("status") == "signal-detected" else "passed",
            bootloader.get("detail", bootloader.get("status", "unknown")),
        ),
        _step(
            "UART framing",
            "passed" if serial_probe.get("status") == "framed-response" else "failed",
            f"{serial_probe.get('bytes_received', 0)} bytes, "
            f"{serial_probe.get('frames_decoded', 0)} frames, "
            f"{serial_probe.get('framing_errors', 0)} framing errors.",
        ),
        _step(
            "Repeated health",
            "passed" if health_analysis["successful_attempts"] == HEALTH_ATTEMPTS else "failed",
            f"{health_analysis['successful_attempts']}/{HEALTH_ATTEMPTS} successful replies.",
        ),
        _step(
            "Repeated identity",
            "passed" if identity_ok == IDENTITY_ATTEMPTS else "warning",
            f"{identity_ok}/{IDENTITY_ATTEMPTS} successful replies.",
        ),
        _step(
            "Configuration families",
            "passed" if not configuration_analysis["failed_queries"] else "warning",
            f"{configuration_analysis['queries_ok']}/{configuration_analysis['queries_total']} readable groups passed; "
            f"failed: {', '.join(configuration_analysis['failed_queries']) or 'none'}.",
        ),
        _step(
            "Live measurement series",
            "passed" if measurement_analysis["successful_attempts"] == MEASUREMENT_ATTEMPTS
            and not measurement_analysis["nonzero_error_codes"] else "failed",
            f"{measurement_analysis['successful_attempts']}/{MEASUREMENT_ATTEMPTS} readings; "
            f"error codes: {measurement_analysis['nonzero_error_codes'] or 'none'}.",
        ),
        _step(
            "History and storage",
            "passed" if history.get("status") == "ok" and history.get("complete") else "warning",
            history.get("detail", history.get("error", history.get("status", "unknown"))),
        ),
    ]
    recommendations = []
    if classification == "sensor_responsive_phone_or_app_likely":
        recommendations.extend([
            "Check Android USB permission, OTG host mode, cable data lines, app state, and phone compatibility.",
            "The sensor protocol is responsive in Linux; do not reset or reflash it solely because the phone app fails.",
        ])
    elif classification == "sensor_power_mcu_or_uart":
        recommendations.extend([
            "Check sensor power, internal battery path, connector pins, and CP2102N-to-MCU UART continuity.",
            "Do not factory-reset a node that cannot return identity or a readable backup.",
        ])
    elif classification == "possible_bootloader_mode":
        recommendations.extend([
            "Preserve this report and confirm product identity before any firmware transfer.",
            "Passive detection alone is not authorization to flash an unidentified board.",
        ])
    else:
        recommendations.extend([
            "Preserve the JSON report and compare failed query names with a known-good TIL90 2.81.",
            "Create a checksummed backup before any guarded repair operation if identity remains readable.",
        ])
    if measurement_analysis["stuck_axis_candidates"]:
        recommendations.append(
            "Repeat the measurement series while physically changing orientation; low variation while stationary is not by itself a fault."
        )
    if configuration_analysis["factory_reset_address"]:
        recommendations.append("The LoRa address is 0xFFFFFFFF; use the guarded backup-driven factory recovery workflow only after identity checks.")

    report.update({
        "summary": {"overall": overall, "classification": classification, "headline": headline},
        "steps": steps,
        "recommendations": list(dict.fromkeys(recommendations)),
        "serial_probe": serial_probe,
        "passive_bootloader_probe": bootloader,
        "health": health_analysis,
        "configuration": configuration_analysis,
        "measurements": measurement_analysis,
        "history": history,
        "attempts": {
            "health": health_attempts,
            "identity": identity_attempts,
            "configuration": query_matrix,
            "measurements": measurement_attempts,
        },
        "completed_utc": _utc_now(),
        "duration_seconds": round(time.monotonic() - started, 2),
    })
    return report


def diagnostic_report_csv(report: dict[str, Any]) -> str:
    """Render a compact, spreadsheet-friendly summary without losing the JSON evidence."""
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["category", "name", "status", "detail"])
    summary = report.get("summary", {})
    writer.writerow(["summary", summary.get("classification"), summary.get("overall"), summary.get("headline")])
    for step in report.get("steps", []):
        writer.writerow(["step", step.get("name"), step.get("status"), step.get("detail")])
    for group, attempts in report.get("attempts", {}).items():
        for index, attempt in enumerate(attempts, start=1):
            detail = attempt.get("error") or f"latency_ms={attempt.get('latency_ms')}"
            writer.writerow([group, f"{attempt.get('query')} #{index}", attempt.get("status"), detail])
    for recommendation in report.get("recommendations", []):
        writer.writerow(["recommendation", "next action", "", recommendation])
    return stream.getvalue()
