"""Local-only FastAPI application for the directly attached TIL90 sensor."""

from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
from copy import deepcopy
import ipaddress
import json
import csv
import io
from pathlib import Path
import secrets
import time
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, SecretStr
import uvicorn

from tools.config_backup import (
    BackupError,
    build_restore_plan,
    sign_snapshot,
    validate_snapshot,
)
from tools.device_service import DeviceService, DeviceServiceError, serial_error_message
from tools.til90_cli import QUERY_GROUPS, READ_QUERIES
from tools.history_manager import HistoryManager
from tools.monitoring_service import MonitoringService
from tools.monitoring_store import MonitoringStore
from tools.usb_diagnostics import diagnose
from tools.recovery_check import run_recovery_check
from tools.deep_diagnostics import diagnostic_report_csv, run_deep_diagnostics
from tools.radio_configuration import (
    RadioConfigurationError,
    apply_regional_profile,
    change_gateway_credentials,
)


ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"


class ReadRequest(BaseModel):
    selection: str
    count: int = Field(default=1, ge=1, le=100)
    delay: float = Field(default=0.0, ge=0, le=60)


class BackupRequest(BaseModel):
    backup: dict[str, Any]


class RestoreRequest(BackupRequest):
    confirmation: str


class ConfigurationValues(BaseModel):
    sampling_seconds: int = Field(ge=1, le=0xFFFFFF)
    gateway_slot_seconds: int = Field(ge=1, le=0xFFFF)
    axis_x: bool = True
    axis_y: bool = True
    axis_z: bool = True


class ConfigurationApplyRequest(BaseModel):
    plan_id: str
    confirmation: str


class HistoryRequest(BaseModel):
    start_epoch: int = Field(ge=0, le=0xFFFFFFFF)
    end_epoch: int = Field(ge=0, le=0xFFFFFFFF)
    max_records: int = Field(default=500, ge=1, le=2000)


class RebootRequest(BaseModel):
    confirmation: str


class AlertValues(BaseModel):
    x_absolute_deg: float | None = Field(default=None, ge=0)
    y_absolute_deg: float | None = Field(default=None, ge=0)
    z_absolute_deg: float | None = Field(default=None, ge=0)
    rate_deg_per_minute: float | None = Field(default=None, ge=0)
    low_battery_v: float | None = Field(default=3.0, ge=0)
    missing_data_seconds: int | None = Field(default=300, ge=10)
    sensor_error: bool = True


class MonitorValues(BaseModel):
    enabled: bool = False
    measurement_interval_seconds: int = Field(default=60, ge=10, le=86400)
    health_interval_seconds: int = Field(default=300, ge=30, le=86400)
    retention_days: int = Field(default=365, ge=1, le=3650)
    alerts: AlertValues = Field(default_factory=AlertValues)


class HistoryJobRequest(BaseModel):
    start_epoch: int = Field(ge=0, le=0xFFFFFFFF)
    end_epoch: int = Field(ge=0, le=0xFFFFFFFF)
    chunk_seconds: int = Field(default=21600, ge=300, le=7 * 86400)
    max_records_per_chunk: int = Field(default=1000, ge=1, le=2000)


class GatewayCredentialsRequest(BaseModel):
    network_id: int = Field(ge=1, le=0xFFFFFFFF)
    password: SecretStr
    confirmation: str


class RegionalProfileRequest(BaseModel):
    profile: str = Field(min_length=1, max_length=40)
    confirmation: str


class FirmwareRequest(BaseModel):
    confirmation: str


class FactoryResetRestoreRequest(BackupRequest):
    network_id: int = Field(ge=1, le=0xFFFFFFFF)
    password: SecretStr
    confirmation: str


def _is_loopback_host(value: str) -> bool:
    host = value.rsplit(":", 1)[0].strip("[]").lower()
    if host in {"localhost", "testserver"}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _is_safe_bind_host(value: str) -> bool:
    """Allow loopback locally and wildcard binding behind a loopback Docker port."""
    if value in {"0.0.0.0", "::", "[::]"}:
        return True
    return _is_loopback_host(value)


def create_app(
    device: DeviceService | None = None,
    *,
    database_path: str | Path | None = None,
    auto_monitor: bool = False,
    measurement_interval_seconds: int = 10,
    health_interval_seconds: int = 60,
) -> FastAPI:
    service = device or DeviceService()
    store = MonitoringStore(
        database_path or (":memory:" if device is not None else ROOT / "data" / "til90.sqlite3")
    )
    monitor = MonitoringService(service, store)
    history_manager = HistoryManager(service, store)
    token = secrets.token_urlsafe(32)

    if auto_monitor:
        automatic_config = monitor.config()
        automatic_config.update({
            "enabled": True,
            "measurement_interval_seconds": measurement_interval_seconds,
            "health_interval_seconds": health_interval_seconds,
        })
        store.set_monitor_config(MonitoringService.validate_config(automatic_config))

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if monitor.config()["enabled"]:
            monitor.start()
        try:
            yield
        finally:
            monitor.stop()
            history_manager.stop()
            store.close()

    app = FastAPI(
        title="TIL90 Local Console", docs_url=None, redoc_url=None,
        openapi_url=None, lifespan=lifespan,
    )
    configuration_plans: dict[str, tuple[float, dict[str, Any]]] = {}
    latest_deep_report: dict[str, Any] | None = None

    def compact_configuration(snapshot: dict[str, Any]) -> dict[str, Any]:
        config = snapshot["configuration"]
        radio = config["radio_general"]
        return {
            "device": snapshot["device"],
            "created_utc": snapshot["created_utc"],
            "sampling_seconds": config["sampling"],
            "gateway_slot_seconds": config["radio_slot_time"],
            "axes": config["channels"]["enabled"],
            "radio": {
                "enabled": radio.get("radio_enabled", False),
                "mac_version": radio.get("mac_version"),
                "spreading_factor": radio.get("spreading_factor"),
                "tx_power_dbm": radio.get("tx_power"),
                "etsi_enabled": radio.get("etsi_enabled", False),
                "adr_enabled": radio.get("adr_enabled", False),
                "network_id": config["radio_network_id"],
                "address": config["radio_address"],
                "dev_eui": config["radio_join"].get("dev_eui"),
                "app_eui": config["radio_join"].get("app_eui"),
                "uplink_channels_hz": config["radio_channels"].get("frequencies_hz", [0] * 8),
                "uplink_enabled": config["radio_channels"]["enabled"],
            },
            "calibration": config["calibration"],
            "storage_interval": snapshot["storage_interval"],
        }

    @app.middleware("http")
    async def local_only_and_headers(request: Request, call_next):
        if not _is_loopback_host(request.headers.get("host", "")):
            return JSONResponse({"detail": "non-loopback Host is not allowed"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    def require_token(value: str | None) -> None:
        if value is None or not secrets.compare_digest(value, token):
            raise HTTPException(status_code=403, detail="missing or invalid session token")

    def handle_error(exc: Exception) -> HTTPException:
        status = 400 if isinstance(
            exc, (BackupError, DeviceServiceError, RadioConfigurationError, ValueError)
        ) else 503
        return HTTPException(status_code=status, detail=serial_error_message(exc))

    @app.get("/api/session")
    def session() -> dict[str, str]:
        return {"token": token}

    @app.get("/api/status")
    def status() -> dict[str, Any]:
        return service.status()

    @app.post("/api/monitor/status")
    def monitor_status(x_til90_token: str | None = Header(default=None)):
        require_token(x_til90_token)
        return monitor.status()

    @app.post("/api/monitor/config")
    def monitor_config(
        body: MonitorValues, x_til90_token: str | None = Header(default=None)
    ):
        require_token(x_til90_token)
        try:
            return monitor.update_config(body.model_dump())
        except Exception as exc:
            raise handle_error(exc) from exc

    @app.post("/api/data/measurements")
    def stored_measurements(
        body: HistoryRequest, x_til90_token: str | None = Header(default=None)
    ):
        require_token(x_til90_token)
        return {
            "summary": store.summary(),
            "measurements": store.measurements(
                body.start_epoch, body.end_epoch, body.max_records
            ),
        }

    @app.post("/api/alerts")
    def stored_alerts(x_til90_token: str | None = Header(default=None)):
        require_token(x_til90_token)
        return {"alerts": store.alerts()}

    @app.post("/api/alerts/{alert_id}/acknowledge")
    def acknowledge_alert(alert_id: int, x_til90_token: str | None = Header(default=None)):
        require_token(x_til90_token)
        if not store.acknowledge_alert(alert_id):
            raise HTTPException(status_code=404, detail="alert does not exist")
        return {"acknowledged": True}

    @app.post("/api/usb/diagnostics")
    def usb_diagnostics(x_til90_token: str | None = Header(default=None)):
        require_token(x_til90_token)
        return diagnose(service.status().get("selected_port"))

    @app.post("/api/recovery/check")
    def recovery_check(x_til90_token: str | None = Header(default=None)):
        require_token(x_til90_token)
        return run_recovery_check(service)

    @app.post("/api/diagnostics/deep")
    def deep_diagnostics(x_til90_token: str | None = Header(default=None)):
        nonlocal latest_deep_report
        require_token(x_til90_token)
        latest_deep_report = run_deep_diagnostics(service, store)
        return latest_deep_report

    @app.get("/api/diagnostics/deep/report.json")
    def deep_diagnostics_json(x_til90_token: str | None = Header(default=None)):
        require_token(x_til90_token)
        if latest_deep_report is None:
            raise HTTPException(status_code=404, detail="no deep diagnostic report is available")
        node_ids = latest_deep_report.get("health", {}).get("node_ids", [])
        node_id = node_ids[-1] if node_ids else "unknown"
        return JSONResponse(
            latest_deep_report,
            headers={"Content-Disposition": f'attachment; filename="til90-{node_id}-diagnostics.json"'},
        )

    @app.get("/api/diagnostics/deep/report.csv")
    def deep_diagnostics_csv(x_til90_token: str | None = Header(default=None)):
        require_token(x_til90_token)
        if latest_deep_report is None:
            raise HTTPException(status_code=404, detail="no deep diagnostic report is available")
        node_ids = latest_deep_report.get("health", {}).get("node_ids", [])
        node_id = node_ids[-1] if node_ids else "unknown"
        return StreamingResponse(
            iter([diagnostic_report_csv(latest_deep_report)]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="til90-{node_id}-diagnostics.csv"'},
        )

    @app.get("/api/capabilities")
    def capabilities() -> dict[str, Any]:
        return {
            "queries": sorted(READ_QUERIES),
            "groups": {name: list(items) for name, items in QUERY_GROUPS.items()},
            "restore": {
                "implemented": [
                    "sampling", "channels", "radio_slot_time", "gateway_credentials",
                    "regional_profile_europe", "reboot", "factory_reset_and_restore",
                    "firmware_2.81_recovery",
                ],
                "hardware_validated_workflows": [
                    "sampling", "channels", "radio_slot_time", "gateway_credentials",
                    "regional_profile_europe", "reboot", "factory_reset_and_restore",
                    "firmware_2.81_recovery",
                ],
                "hardware_validated": sorted(service.hardware_validated_writes),
                "writes_enabled": service.writes_enabled,
                "blocked": ["calibration_write", "node_identity_write", "newer_firmware"],
            },
        }

    @app.get("/api/radio-profiles")
    def radio_profiles() -> dict[str, Any]:
        return json.loads((ROOT / "analysis" / "protocol" / "radio_profiles.json").read_text())

    @app.post("/api/radio/profile")
    def regional_profile(
        body: RegionalProfileRequest,
        x_til90_token: str | None = Header(default=None),
    ):
        require_token(x_til90_token)
        if not service.writes_enabled:
            raise HTTPException(status_code=400, detail="hardware writes are disabled")
        try:
            result = apply_regional_profile(service, body.profile, body.confirmation)
            return {
                "status": result["status"],
                "node_id": result["node_id"],
                "profile": result["profile"],
                "operations": result["operations"],
            }
        except (RadioConfigurationError, DeviceServiceError) as exc:
            raise handle_error(exc) from exc

    @app.post("/api/radio/gateway-credentials")
    def gateway_credentials(
        body: GatewayCredentialsRequest,
        x_til90_token: str | None = Header(default=None),
    ):
        require_token(x_til90_token)
        if not service.writes_enabled:
            raise HTTPException(status_code=400, detail="hardware writes are disabled")
        try:
            result = change_gateway_credentials(
                service, body.network_id, body.password.get_secret_value(), body.confirmation
            )
            return {
                "status": result["status"], "node_id": result["node_id"],
                "network_id": result["network_id"],
                "password_written_but_not_readable": True,
            }
        except (RadioConfigurationError, DeviceServiceError) as exc:
            raise handle_error(exc) from exc

    @app.post("/api/config/current")
    def current_configuration(x_til90_token: str | None = Header(default=None)):
        require_token(x_til90_token)
        try:
            return compact_configuration(service.backup())
        except Exception as exc:
            raise handle_error(exc) from exc

    @app.post("/api/config/preview")
    def preview_configuration(
        body: ConfigurationValues,
        x_til90_token: str | None = Header(default=None),
    ):
        require_token(x_til90_token)
        if not any((body.axis_x, body.axis_y, body.axis_z)):
            raise HTTPException(status_code=400, detail="at least one axis must remain enabled")
        try:
            current = service.backup()
            target = deepcopy(current)
            target["configuration"]["sampling"] = body.sampling_seconds
            target["configuration"]["radio_slot_time"] = body.gateway_slot_seconds
            target["configuration"]["channels"]["enabled"] = {
                "x": body.axis_x, "y": body.axis_y, "z": body.axis_z,
            }
            target = sign_snapshot(target)
            plan = build_restore_plan(current, target, service.hardware_validated_writes)
            plan["writes_enabled"] = service.writes_enabled
            plan["can_apply"] = plan["can_apply"] and service.writes_enabled
            if not service.writes_enabled:
                plan["apply_block_reason"] = "restart the web service with --enable-writes"
            plan_id = secrets.token_urlsafe(24)
            configuration_plans.clear()
            configuration_plans[plan_id] = (time.monotonic() + 600, target)
            return {
                "plan_id": plan_id,
                "plan": plan,
                "current": compact_configuration(current),
                "target": compact_configuration(target),
            }
        except Exception as exc:
            raise handle_error(exc) from exc

    @app.post("/api/config/apply")
    def apply_configuration(
        body: ConfigurationApplyRequest,
        x_til90_token: str | None = Header(default=None),
    ):
        require_token(x_til90_token)
        stored = configuration_plans.pop(body.plan_id, None)
        if stored is None or stored[0] < time.monotonic():
            raise HTTPException(status_code=400, detail="configuration preview expired; preview again")
        try:
            result = service.apply_restore(stored[1], body.confirmation)
            return {
                "status": result["status"],
                "configuration": compact_configuration(result["post_backup"]),
                "operations": result["plan"]["operations"],
            }
        except Exception as exc:
            raise handle_error(exc) from exc

    @app.post("/api/history")
    def history(body: HistoryRequest, x_til90_token: str | None = Header(default=None)):
        require_token(x_til90_token)
        if body.end_epoch < body.start_epoch:
            raise HTTPException(status_code=400, detail="history end must not precede start")
        try:
            return service.history(
                body.start_epoch, body.end_epoch, max_records=body.max_records
            )
        except Exception as exc:
            raise handle_error(exc) from exc

    @app.post("/api/history/jobs")
    def create_history_job(
        body: HistoryJobRequest, x_til90_token: str | None = Header(default=None)
    ):
        require_token(x_til90_token)
        try:
            return history_manager.create(
                body.start_epoch, body.end_epoch, chunk_seconds=body.chunk_seconds,
                max_records_per_chunk=body.max_records_per_chunk,
            )
        except Exception as exc:
            raise handle_error(exc) from exc

    @app.post("/api/history/jobs/list")
    def list_history_jobs(x_til90_token: str | None = Header(default=None)):
        require_token(x_til90_token)
        return {"jobs": store.history_jobs()}

    @app.post("/api/history/jobs/{job_id}/resume")
    def resume_history_job(job_id: int, x_til90_token: str | None = Header(default=None)):
        require_token(x_til90_token)
        try:
            return history_manager.resume(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise handle_error(exc) from exc

    @app.post("/api/history/jobs/{job_id}/cancel")
    def cancel_history_job(job_id: int, x_til90_token: str | None = Header(default=None)):
        require_token(x_til90_token)
        try:
            return history_manager.cancel(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/reboot")
    def reboot_node(body: RebootRequest, x_til90_token: str | None = Header(default=None)):
        require_token(x_til90_token)
        if not service.writes_enabled:
            raise HTTPException(status_code=400, detail="maintenance operations are disabled")
        try:
            from tools.maintenance_cli import reboot
            with service._lock:
                result = reboot(service.resolve_port(), body.confirmation)
            return {
                "status": result["status"],
                "node_id": result["node_id"],
                "before_uptime": result["before_uptime"],
                "after_uptime": result["after_uptime"],
                "configuration_unchanged": result["configuration_unchanged"],
            }
        except Exception as exc:
            raise handle_error(exc) from exc

    @app.post("/api/firmware/manifest")
    def firmware_manifest(x_til90_token: str | None = Header(default=None)):
        require_token(x_til90_token)
        try:
            from tools.firmware_service import G6_TIL90_FIRMWARE, validate_firmware
            return validate_firmware(ROOT / G6_TIL90_FIRMWARE, service.backup()["device"])
        except Exception as exc:
            raise handle_error(exc) from exc

    @app.post("/api/firmware/flash")
    def flash_firmware(
        body: FirmwareRequest, x_til90_token: str | None = Header(default=None)
    ):
        require_token(x_til90_token)
        if not service.writes_enabled:
            raise HTTPException(status_code=400, detail="maintenance operations are disabled")
        try:
            from tools.firmware_service import G6_TIL90_FIRMWARE, flash_g6_til90
            with service._lock:
                result = flash_g6_til90(
                    service.resolve_port(), body.confirmation,
                    firmware_path=ROOT / G6_TIL90_FIRMWARE, timeout=60,
                )
            return {
                "status": result["status"], "device": result["device"],
                "firmware": result["firmware"], "transfer": result["transfer"],
                "configuration_unchanged": not result["configuration_changes"],
            }
        except Exception as exc:
            raise handle_error(exc) from exc

    @app.post("/api/recovery/factory-reset-restore")
    def factory_reset_restore(
        body: FactoryResetRestoreRequest,
        x_til90_token: str | None = Header(default=None),
    ):
        require_token(x_til90_token)
        if not service.writes_enabled:
            raise HTTPException(status_code=400, detail="maintenance operations are disabled")
        try:
            from tools.config_backup import diff_snapshots
            from tools.maintenance_cli import factory_reset, reboot
            from tools.radio_configuration import restore_after_factory_reset
            validate_snapshot(body.backup)
            current = service.backup()
            node_id = current["device"]["node_id"]
            required = f"RESET AND RESTORE {node_id}"
            if body.confirmation != required:
                raise RadioConfigurationError(f"confirmation must be exactly: {required}")
            if current["device"] != body.backup["device"]:
                raise BackupError("backup device identity and firmware do not match the connected node")
            with service._lock:
                reset = factory_reset(
                    service.resolve_port(), f"FACTORY RESET {node_id}", timeout=45
                )
                restored = restore_after_factory_reset(
                    service, body.backup, body.network_id,
                    body.password.get_secret_value(), f"RESTORE AFTER RESET {node_id}",
                )
                restarted = reboot(service.resolve_port(), f"REBOOT {node_id}", timeout=30)
            final_backup = restarted["after_backup"]
            changes = diff_snapshots(final_backup, body.backup)
            if changes:
                raise RadioConfigurationError(
                    f"post-reset configuration does not match the backup: {changes}"
                )
            return {
                "status": "factory-reset-restored-and-rebooted", "node_id": node_id,
                "network_id": body.network_id,
                "reset_changes": reset["configuration_changes"],
                "restore_operations": len(restored["evidence"]),
                "configuration_unchanged_from_backup": True,
                "password_written_but_not_readable": True,
                "post_reboot_uptime": restarted["after_uptime"],
            }
        except Exception as exc:
            raise handle_error(exc) from exc

    @app.post("/api/read")
    def read(body: ReadRequest, x_til90_token: str | None = Header(default=None)):
        require_token(x_til90_token)
        try:
            results = service.read(body.selection, count=body.count, delay=body.delay)
            monitor.ingest(results)
            return {"results": results}
        except Exception as exc:
            raise handle_error(exc) from exc

    @app.post("/api/backup")
    def backup(x_til90_token: str | None = Header(default=None)):
        require_token(x_til90_token)
        try:
            return service.backup()
        except Exception as exc:
            raise handle_error(exc) from exc

    @app.post("/api/backup/validate")
    def validate(body: BackupRequest, x_til90_token: str | None = Header(default=None)):
        require_token(x_til90_token)
        try:
            validate_snapshot(body.backup)
            return {"valid": True, "device": body.backup["device"], "checksum": body.backup["checksum"]}
        except Exception as exc:
            raise handle_error(exc) from exc

    @app.post("/api/restore/preview")
    def preview(body: BackupRequest, x_til90_token: str | None = Header(default=None)):
        require_token(x_til90_token)
        try:
            return service.preview_restore(body.backup)
        except Exception as exc:
            raise handle_error(exc) from exc

    @app.post("/api/restore/apply")
    def apply(body: RestoreRequest, x_til90_token: str | None = Header(default=None)):
        require_token(x_til90_token)
        try:
            return service.apply_restore(body.backup, body.confirmation)
        except Exception as exc:
            raise handle_error(exc) from exc

    @app.get("/")
    def index():
        return FileResponse(WEB_ROOT / "index.html")

    @app.get("/api/data/export.csv")
    def export_csv(
        request: Request, start_epoch: int | None = None, end_epoch: int | None = None,
        x_til90_token: str | None = Header(default=None),
    ):
        require_token(x_til90_token)
        output = io.StringIO()
        columns = [
            "node_id", "timestamp", "source", "x_deg", "y_deg", "z_deg",
            "x_stddev_g", "y_stddev_g", "z_stddev_g", "temperature_c", "error_code",
        ]
        writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(store.measurements(start_epoch, end_epoch, 10000))
        return StreamingResponse(
            iter([output.getvalue()]), media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=til90-measurements.csv"},
        )

    app.mount("/assets", StaticFiles(directory=WEB_ROOT), name="assets")
    return app


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local browser console for a USB-attached TIL90")
    parser.add_argument("--host", default="127.0.0.1", help="loopback address only")
    parser.add_argument("--port", type=int, default=8765, help="HTTP port (default: 8765)")
    parser.add_argument("--serial-port", help="serial path; auto-detected by default")
    parser.add_argument(
        "--database", default=str(ROOT / "data" / "til90.sqlite3"),
        help="SQLite monitoring database",
    )
    parser.add_argument(
        "--enable-writes", action="store_true",
        help="enable only hardware-validated restore operations; still requires exact confirmation",
    )
    parser.add_argument(
        "--auto-monitor", action="store_true",
        help="start persistent monitoring and reconnect automatically when USB appears",
    )
    parser.add_argument(
        "--measurement-interval", type=int, default=10,
        help="automatic live-reading interval in seconds (default: 10)",
    )
    parser.add_argument(
        "--health-interval", type=int, default=60,
        help="automatic health-reading interval in seconds (default: 60)",
    )
    parser.add_argument(
        "--require-validated-firmware", action="store_true",
        help="refuse startup unless the exact mapped firmware 2.81 file is mounted",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not _is_safe_bind_host(args.host):
        raise SystemExit("--host must be loopback or a wildcard Docker bind address")
    if args.require_validated_firmware:
        from tools.firmware_service import G6_TIL90_FIRMWARE, validate_firmware_file
        try:
            validate_firmware_file(ROOT / G6_TIL90_FIRMWARE)
        except Exception as exc:
            raise SystemExit(f"required firmware validation failed: {exc}") from exc
    app = create_app(
        DeviceService(args.serial_port, writes_enabled=args.enable_writes),
        database_path=args.database,
        auto_monitor=args.auto_monitor,
        measurement_interval_seconds=args.measurement_interval,
        health_interval_seconds=args.health_interval,
    )
    uvicorn.run(app, host=args.host, port=args.port, access_log=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
