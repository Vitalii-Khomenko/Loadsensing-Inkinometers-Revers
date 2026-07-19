import struct

from tools.packet_parser.messages import (
    decode_bluetooth_config,
    decode_sampling_rate,
    decode_til90_calibration,
    decode_til90_channel_config,
    decode_til90_reading,
    encode_history_request,
    unwrap_recovered_message,
    decode_response_code,
    decode_stored_data_interval,
)


def _header(am: int) -> bytes:
    return bytes.fromhex("40 2a 12 34 07") + bytes((am,))


def _pack(fields):
    value = "".join(f"{v & ((1 << n) - 1):0{n}b}" for v, n in fields)
    value += "0" * (-len(value) % 8)
    return int(value, 2).to_bytes(len(value) // 8, "big")


def test_regular_til90_reading() -> None:
    payload = _pack([(1,32),(1,2),(0,1),(0,1),(1,1),(0,4),(1,1),(200,12),
                     (10000,21),(256,20),(90,9)])
    reading = decode_til90_reading(_header(0x4C) + payload)
    assert reading.temperature_c == 20.0
    assert reading.axes["x"].angle_deg == 1.0
    assert reading.axes["x"].stddev_g == 0.001
    assert reading.azimuth == 90


def test_sampling_calibration_and_channel_config() -> None:
    assert decode_sampling_rate(_header(0x82) + bytes.fromhex("00 0e 10")) == 3600
    cal = decode_til90_calibration(
        _header(0x98) + bytes.fromhex("00 00 00 01") + struct.pack(">6f", 1,2,3,4,5,6)
    )
    assert cal.coefficients["z_gain"] == 6.0
    fields = [(0,3),(0,1),(0,1),(1,1),(1,1),(0,1),(0,1),(1,1),(4,4),
              (100,15),(-100,15),(200,15),(-200,15),(300,15),(-300,15)]
    cfg = decode_til90_channel_config(_header(0x9B) + _pack(fields))
    assert cfg.data_enabled == {"z": False, "y": True, "x": True}
    assert cfg.thresholds["y"] == (-2.0, 2.0)


def test_bluetooth_config_is_exactly_48_bits() -> None:
    payload = _pack([(1,4),(3,7),(1,1),(0,1),(20,6),(4,3),(5,3),(1,1),
                     (2,2),(1,1),(120,8),(500,10),(1,1)])
    cfg = decode_bluetooth_config(_header(0xA5) + payload)
    assert len(payload) == 6
    assert cfg.enabled and not cfg.ota_enabled
    assert cfg.tx_power == 20
    assert cfg.connection_length == 500


def test_history_request_wrapper_and_end_marker() -> None:
    assert encode_history_request(1, 2) == bytes.fromhex("03 00 00000001 00000002")
    assert encode_history_request(1, 2, raw_only=True)[1] == 0x56
    outer = _header(0x01) + bytes.fromhex("2A 4C DE AD")
    capture_id, inner = unwrap_recovered_message(outer)
    assert capture_id == 0x2A
    assert inner == outer[:5] + bytes.fromhex("4C DE AD")
    assert decode_response_code(_header(0x00) + bytes.fromhex("00 80")) == 0x80
    assert decode_stored_data_interval(
        _header(0x02) + bytes.fromhex("00000001 00000009")
    ) == (1, 9)
