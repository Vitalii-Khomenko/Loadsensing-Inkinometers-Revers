from tools.packet_parser.messages import (
    decode_extended_node_info,
    decode_node_health,
    decode_node_info,
    decode_til90_alarm_reading,
)


def _header(am_type: int) -> bytes:
    return bytes.fromhex("40 2a 12 34 07") + bytes((am_type,))


def _pack(fields: list[tuple[int, int]]) -> bytes:
    bits = "".join(f"{value & ((1 << width) - 1):0{width}b}" for value, width in fields)
    bits += "0" * (-len(bits) % 8)
    return int(bits, 2).to_bytes(len(bits) // 8, "big")


def test_decode_health_v1_and_v2() -> None:
    common = bytes.fromhex("65 00 00 01 00 00 00 02 0e a6 fb 12 34 03 0d")
    v1 = decode_node_health(_header(0x40) + common)
    v2 = decode_node_health(_header(0x46) + common + bytes.fromhex("00 09"))

    assert (v1.timestamp, v1.uptime) == (0x65000001, 2)
    assert v1.battery_v == 3.75
    assert v1.temperature_c == -5
    assert v1.serial_number == 0x1234
    assert (v1.firmware_major, v1.firmware_minor) == (3, 13)
    assert v1.time_delta is None
    assert v2.time_delta == 9


def test_decode_health_v3_with_humidity() -> None:
    payload = _pack(
        [
            (100, 32), (1, 2), (50, 30), (375, 12), (-2, 8),
            (654, 10), (12, 9), (34, 10), (5, 3),
            (0xABCDE, 20), (3, 8), (13, 8), (7, 16),
        ]
    )
    health = decode_node_health(_header(0x4F) + payload)

    assert health.message_version == 1
    assert health.battery_v == 3.75
    assert health.temperature_c == -2
    assert health.humidity_percent == 65.4
    assert health.humidity_std == 1.2
    assert health.humidity_delta == 3.4
    assert health.humidity_reserved == 5
    assert health.serial_number == 0xABCDE


def test_decode_node_info_versions() -> None:
    v1 = decode_node_info(_header(0x03) + bytes.fromhex("12 34 03 0d 65 00 00 01"))
    v2 = decode_node_info(
        _header(0x09) + bytes.fromhex("40 12 34 56 78 03 0d 65 00 00 01")
    )

    assert v1.message_version is None
    assert v1.serial_number == 0x1234
    assert v2.message_version == 1
    assert v2.serial_number == 0x12345678
    assert v2.firmware_build_time == 0x65000001


def test_decode_extended_node_info() -> None:
    info = decode_extended_node_info(_header(0x05) + bytes.fromhex("01 02 03 04 05"))

    assert info.message_version == 1
    assert (info.board1_msb, info.board1_lsb) == (2, 3)
    assert (info.board2_msb, info.board2_lsb) == (4, 5)


def test_decode_til90_alarm_reading_variable_fields() -> None:
    payload = _pack(
        [
            (1000, 32), (1, 2),
            (0, 1), (1, 1), (1, 1),  # Z/Y/X enabled
            (0, 4), (1, 1), (235, 12),
            (12345, 21), (256, 20),   # X
            (-5000, 21), (512, 20),   # Y
            (1, 1), (1, 1), (1, 1),  # configured/triggered/active
            (0, 1), (1, 1), (1, 1), (3, 3),  # alarm Z/Y/X + reserved
            (1, 1), (125, 15),        # X upper +1.25 deg
            (0, 1), (-250, 15),       # Y lower -2.50 deg
        ]
    )
    reading = decode_til90_alarm_reading(_header(0x50) + payload)

    assert reading.timestamp == 1000
    assert reading.temperature_c == 23.5
    assert set(reading.axes) == {"x", "y"}
    assert reading.axes["x"].angle_deg == 1.2345
    assert reading.axes["x"].stddev_g == 0.001
    assert reading.axes["y"].angle_deg == -0.5
    assert reading.alarm_reserved == 3
    assert reading.alarms["x"].upper_threshold
    assert reading.alarms["x"].threshold_deg == 1.25
    assert not reading.alarms["y"].upper_threshold
    assert reading.alarms["y"].threshold_deg == -2.5
