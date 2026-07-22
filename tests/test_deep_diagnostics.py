from tools.deep_diagnostics import (
    _framed_health_probe,
    _passive_bootloader_probe,
    diagnostic_report_csv,
    run_deep_diagnostics,
)
from tools.packet_parser import encode_frame


def accessible_usb(_port):
    return {
        "exists": True,
        "readable": True,
        "writable": True,
        "selected_port": "/dev/fake",
        "stable_alias": "/dev/serial/by-id/fake",
        "recommendations": [],
    }


class HealthyDevice:
    def __init__(self, live_error=0):
        self.live_error = live_error
        self.calls = []
        self.timestamp = 1_784_700_000

    def status(self):
        return {
            "selected_port": "/dev/fake", "device_detected": True,
            "reconnect_count": 0, "writes_enabled": True,
        }

    def read(self, query):
        self.calls.append(query)
        header = {"node_id": 101677, "product_code": 0x4E}
        data = {}
        if query == "health":
            data = {
                "timestamp": self.timestamp, "uptime": 1000,
                "battery_v": 3.33, "temperature_c": 24.5,
                "firmware_major": 2, "firmware_minor": 81,
            }
        elif query == "info":
            data = {
                "serial_number": 101677, "firmware_major": 2,
                "firmware_minor": 81, "firmware_build_time": 0,
            }
        elif query == "live":
            self.timestamp += 1
            data = {
                "timestamp": self.timestamp, "error_code": self.live_error,
                "temperature_c": 24.5,
                "axes": {
                    "x": {"angle_deg": -2.0 + self.timestamp % 3 * 0.001, "stddev_g": 0.0001},
                    "y": {"angle_deg": 1.0 + self.timestamp % 2 * 0.001, "stddev_g": 0.0002},
                    "z": {"angle_deg": 87.0, "stddev_g": 0.0001},
                },
            }
        elif query == "radio-general":
            data = {
                "mac_version": 0, "spreading_factor": 11, "tx_power": 14,
                "etsi_enabled": True, "adr_enabled": True,
            }
        elif query == "radio-channels":
            data = {
                "enabled": [True, True, True, True, True, True, False, False],
                "frequencies_hz": [
                    868_100_000, 868_300_000, 868_500_000,
                    868_850_000, 869_050_000, 869_525_000, 0, 0,
                ],
            }
        elif query == "channels":
            data = {"enabled": {"x": True, "y": True, "z": True}}
        elif query == "radio-address":
            data = 81_890_605
        elif query == "radio-network-id":
            data = 27_484
        return [{"query": query, "status": "ok", "header": header, "data": data}]

    def history(self, start_epoch, end_epoch, max_records=200):
        assert end_epoch - start_epoch == 900
        assert max_records == 200
        return {"status": "ok", "complete": True, "completion_code": 0x80, "records": []}


class StoredHealth:
    def recent_health(self, node_id=None, limit=50):
        assert node_id == 101677
        return [
            {"node_id": node_id, "timestamp": 2, "uptime": 1000},
            {"node_id": node_id, "timestamp": 1, "uptime": 999},
        ]


def test_deep_diagnostics_classifies_healthy_sensor_and_runs_full_matrix():
    device = HealthyDevice()
    report = run_deep_diagnostics(device, StoredHealth(), usb_probe=accessible_usb)
    assert report["read_only"]
    assert report["persistent_writes_sent"] == 0
    assert report["summary"]["overall"] == "ready"
    assert report["summary"]["classification"] == "sensor_responsive_phone_or_app_likely"
    assert report["health"]["successful_attempts"] == 5
    assert report["configuration"]["failed_queries"] == []
    assert report["configuration"]["embedded_europe_match"]
    assert report["measurements"]["successful_attempts"] == 5
    assert device.calls.count("health") == 5
    assert device.calls.count("info") == 5
    assert device.calls.count("live") == 5
    csv_report = diagnostic_report_csv(report)
    assert "sensor_responsive_phone_or_app_likely" in csv_report
    assert "Persistent" not in csv_report


def test_deep_diagnostics_identifies_measurement_error_code():
    report = run_deep_diagnostics(
        HealthyDevice(live_error=3), StoredHealth(), usb_probe=accessible_usb
    )
    assert report["summary"]["overall"] == "failed"
    assert report["summary"]["classification"] == "measurement_hardware_or_firmware"
    assert report["measurements"]["nonzero_error_codes"] == [3]


def test_deep_diagnostics_stops_before_serial_when_usb_is_missing():
    device = HealthyDevice()
    report = run_deep_diagnostics(
        device,
        usb_probe=lambda _port: {
            "exists": False, "readable": False, "writable": False,
            "recommendations": ["Reconnect USB."],
        },
    )
    assert report["summary"]["classification"] == "usb_not_enumerated"
    assert device.calls == []
    assert report["recommendations"] == ["Reconnect USB."]


class RawDevice:
    def __init__(self, chunks):
        self.connection = RawConnection(chunks)

    def _read_transaction(self, operation):
        return operation(self.connection)


class RawConnection:
    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.writes = []

    def read(self, _size):
        return self.chunks.pop(0) if self.chunks else b""

    def write(self, payload):
        self.writes.append(payload)
        return len(payload)

    def flush(self):
        pass


def test_passive_bootloader_probe_never_writes_and_detects_xmodem_crc_request():
    device = RawDevice([b"CCC"])
    result = _passive_bootloader_probe(device, duration_seconds=0.001)
    assert result["status"] == "signal-detected"
    assert result["control_bytes"]["xmodem_crc_requests"] == 3
    assert device.connection.writes == []


def test_passive_bootloader_probe_ignores_control_byte_inside_protocol_frame():
    device = RawDevice([encode_frame(bytes.fromhex("41 4e 8d 2d 01 43"))])
    result = _passive_bootloader_probe(device, duration_seconds=0.001)
    assert result["status"] == "quiet"
    assert result["framed_protocol_marker"]


def test_raw_health_probe_counts_valid_protocol_frames():
    response = encode_frame(bytes.fromhex("41 4e 8d 2d 01 4f"))
    device = RawDevice([response])
    result = _framed_health_probe(device, timeout_seconds=0.01)
    assert result["status"] == "framed-response"
    assert result["frames_decoded"] == 1
    assert result["framing_errors"] == 0
    assert result["headers"][0]["node_id"] == 101677
    assert device.connection.writes == [encode_frame(b"\x01")]
