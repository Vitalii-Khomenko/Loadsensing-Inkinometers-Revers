"""Read-only recovery assessment for a connected TIL90 sensor."""

from __future__ import annotations

from typing import Any

from tools.usb_diagnostics import diagnose


def _step(name: str, status: str, detail: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def run_recovery_check(device: Any) -> dict[str, Any]:
    """Check host USB, protocol identity, and configuration without writing."""
    steps: list[dict[str, str]] = []
    recommendations: list[str] = []
    usb = diagnose(device.status().get("selected_port"))
    if not usb.get("exists"):
        steps.append(_step("USB enumeration", "failed", "The CP2102N serial device is absent."))
        recommendations.extend(usb["recommendations"])
        return _result("failed", steps, recommendations, usb=usb)
    steps.append(_step(
        "USB enumeration", "passed",
        f"Adapter found at {usb.get('stable_alias') or usb['selected_port']}.",
    ))
    access = bool(usb.get("readable") and usb.get("writable"))
    steps.append(_step(
        "Linux access", "passed" if access else "failed",
        "Current process has read/write serial access." if access else "Serial access is denied.",
    ))
    if not access:
        recommendations.extend(usb["recommendations"])
        return _result("failed", steps, recommendations, usb=usb)

    try:
        health = device.read("health")[0]
        if health.get("status") != "ok":
            raise RuntimeError(f"health returned {health.get('status')}")
        header, data = health["header"], health["data"]
        steps.append(_step(
            "Protocol response", "passed",
            f"Node {header['node_id']} returned health data at 115200 8N1.",
        ))
    except Exception as exc:
        steps.append(_step("Protocol response", "failed", f"No valid health response: {exc}"))
        recommendations.extend([
            "Disconnect the sensor from every other USB host and reconnect it directly.",
            "Confirm a data-capable cable, USB host/OTG mode, connector condition, and sensor power.",
            "Retry the read after a full USB disconnect; do not factory-reset a node that cannot answer health.",
            "If Linux still enumerates CP2102N but no protocol request succeeds, preserve diagnostics and escalate for hardware or firmware recovery.",
        ])
        return _result("failed", steps, recommendations, usb=usb)

    try:
        snapshot = device.backup()
        config = snapshot["configuration"]
        identity = snapshot["device"]
        steps.append(_step(
            "Identity", "passed",
            f"Product 0x{identity['product_code']:02X}, node {identity['node_id']}, "
            f"firmware {identity['firmware_major']}.{identity['firmware_minor']}.",
        ))
        steps.append(_step("Configuration read", "passed", "All backup read groups decoded."))
    except Exception as exc:
        steps.append(_step("Configuration read", "failed", f"Complete read failed: {exc}"))
        recommendations.append(
            "Save the successful health result and retry a complete configuration read before any restore or reboot."
        )
        return _result(
            "failed", steps, recommendations, usb=usb,
            device={"node_id": header["node_id"], "product_code": header["product_code"]},
        )

    enabled_axes = [
        axis.upper() for axis in "xyz" if config["channels"]["enabled"].get(axis)
    ]
    sampling = int(config["sampling"])
    steps.append(_step(
        "Sensor acquisition", "passed" if enabled_axes and sampling > 0 else "warning",
        f"Sampling is {sampling} seconds; enabled axes: {', '.join(enabled_axes) or 'none'}.",
    ))
    if not enabled_axes:
        recommendations.append("Restore at least one hardware-validated axis from a known-good backup.")

    address = int(config["radio_address"])
    radio = config["radio_general"]
    channels = config["radio_channels"].get("enabled", [])
    network_id = int(config["radio_network_id"])
    factory_reset_indicated = address == 0xFFFFFFFF
    if factory_reset_indicated:
        radio_status = "failed"
        radio_detail = "LoRa address is 0xFFFFFFFF; the Android app explicitly marks this as factory-reset-required."
        recommendations.append(
            "Do not reset automatically. Create a backup, confirm the unit and gateway credentials, and use the official recovery workflow with a rollback plan."
        )
    elif radio.get("radio_enabled") and network_id and any(channels):
        radio_status = "passed"
        radio_detail = f"Radio enabled, address {address}, network ID {network_id}, active uplinks present."
    else:
        radio_status = "warning"
        radio_detail = (
            f"Radio enabled={bool(radio.get('radio_enabled'))}, address={address}, "
            f"network ID={network_id}, active uplinks={sum(bool(item) for item in channels)}."
        )
        recommendations.append(
            "Compare radio values with a known working node and gateway project before changing them."
        )
    steps.append(_step("Radio configuration", radio_status, radio_detail))

    battery = data.get("battery_v")
    if battery is not None:
        steps.append(_step(
            "Power report", "warning" if battery < 3.0 else "passed",
            f"Sensor reports {battery:.2f} V and uptime {data.get('uptime', 'unknown')} seconds.",
        ))
        if battery < 3.0:
            recommendations.append("Check the internal battery/power path before firmware or reset work.")

    reconnects = device.status().get("reconnect_count", 0)
    steps.append(_step(
        "Connection stability", "warning" if reconnects else "passed",
        f"Automatic read reconnects in this service process: {reconnects}.",
    ))
    overall = "failed" if any(item["status"] == "failed" for item in steps) else (
        "warning" if any(item["status"] == "warning" for item in steps) else "ready"
    )
    if not recommendations:
        recommendations.append("The node answers and its readable configuration is internally plausible.")
    return _result(
        overall, steps, recommendations, usb=usb, device=identity,
        configuration={
            "sampling_seconds": sampling,
            "enabled_axes": enabled_axes,
            "radio_enabled": bool(radio.get("radio_enabled")),
            "radio_address": address,
            "network_id": network_id,
            "active_uplink_count": sum(bool(item) for item in channels),
            "factory_reset_indicated_by_apk_rule": factory_reset_indicated,
        },
        actions={
            "read_only_diagnostics": "available",
            "checksummed_backup": "available",
            "validated_field_restore": "available_only_with_write_mode_and_confirmation",
            "guarded_reboot": "available_only_after_identity_and_backup",
            "factory_reset": "blocked_destructive_and_not_hardware_validated",
            "firmware_recovery": "blocked_requires_bootloader_and_image_recovery_validation",
        },
    )


def _result(
    overall: str, steps: list[dict[str, str]], recommendations: list[str], **details: Any
) -> dict[str, Any]:
    return {
        "overall": overall, "steps": steps,
        "recommendations": list(dict.fromkeys(recommendations)), **details,
    }
