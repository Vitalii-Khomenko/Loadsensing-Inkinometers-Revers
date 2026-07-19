from tools.packet_parser import encode_frame
from tools.packet_parser.messages import (
    decode_lora_address,
    decode_lora_channels_config,
    decode_lora_general_config,
    decode_lora_join_config,
    decode_lora_network_id,
    decode_lora_slot_time,
)
import json

from tools.til90_cli import QUERY_GROUPS, READ_QUERIES, main, run_history, run_query


def _header(am_type: int) -> bytes:
    return bytes.fromhex("41 4e 8d 2d 01") + bytes((am_type,))


def _pack(fields: list[tuple[int, int]]) -> bytes:
    value = "".join(f"{item & ((1 << width) - 1):0{width}b}" for item, width in fields)
    assert len(value) % 8 == 0
    return int(value, 2).to_bytes(len(value) // 8, "big")


def test_lora_general_scalar_decoders() -> None:
    payload = _pack([
        (1, 4), (2, 4), (1, 1), (1, 1), (0, 1), (1, 1), (9, 4),
        (14, 8), (0, 2), (1, 1), (1, 1), (10, 4),
        (869_525_000, 32), (30, 16),
    ])
    config = decode_lora_general_config(_header(0x84) + payload)
    assert config.message_version == 1
    assert config.radio_enabled and config.adr_enabled
    assert config.spreading_factor == 9
    assert config.rx2_frequency_hz == 869_525_000
    assert config.send_slot_time == 30
    assert decode_lora_address(_header(0x83) + bytes.fromhex("12345678")) == 0x12345678
    assert decode_lora_slot_time(_header(0x90) + bytes.fromhex("012c")) == 300
    assert decode_lora_network_id(_header(0x8D) + bytes.fromhex("89abcdef")) == 0x89ABCDEF


def test_lora_channel_decoder_zeroes_disabled_frequencies() -> None:
    payload = bytes((0x00, 0xA0)) + b"".join(
        frequency.to_bytes(4, "big") for frequency in range(100, 108)
    )
    config = decode_lora_channels_config(_header(0x85) + payload)
    assert config.enabled == (True, False, True, False, False, False, False, False)
    assert config.frequencies_hz == (100, 0, 102, 0, 0, 0, 0, 0)


def test_lora_join_decoder() -> None:
    payload = (
        bytes.fromhex("00 0102030405060708 1112131415161718 003c 04")
        + _pack([(12, 6), (2, 2), (5, 8), (1, 1), (0, 1), (0, 6)])
    )
    join = decode_lora_join_config(_header(0x94) + payload)
    assert join.dev_eui == "0102030405060708"
    assert join.app_eui == "1112131415161718"
    assert join.max_time_without_downlink_minutes == 60
    assert join.activation_mode == 1


def test_cli_exposes_only_read_allowlist() -> None:
    forbidden = ("write", "set", "reset", "reboot", "firmware", "factory", "coverage")
    assert not any(word in name for name in READ_QUERIES for word in forbidden)
    assert "radio" in QUERY_GROUPS
    assert "bluetooth" not in QUERY_GROUPS["all"]
    assert READ_QUERIES["radio-network-id"].request_body == bytes.fromhex("00 8d")
    assert READ_QUERIES["channels"].request_body == bytes.fromhex("00 9a")


class _FakeSerial:
    def __init__(self, response: bytes) -> None:
        self.response = response
        self.written = b""

    def write(self, value: bytes) -> int:
        self.written += value
        return len(value)

    def flush(self) -> None:
        pass

    def read(self, size: int) -> bytes:
        response, self.response = self.response, b""
        return response


def test_cli_transaction_records_exact_wire_bytes() -> None:
    connection = _FakeSerial(encode_frame(_header(0x8D) + bytes.fromhex("12345678")))
    result = run_query(connection, "radio-network-id", READ_QUERIES["radio-network-id"])
    assert connection.written == bytes.fromhex("10 02 00 8d 10 03")
    assert result["status"] == "ok"
    assert result["data"] == 0x12345678
    assert result["rx_body"].endswith("12 34 56 78")


def test_cli_transaction_reports_device_and_decode_errors() -> None:
    device_error = _FakeSerial(encode_frame(_header(0x00) + bytes.fromhex("00 04")))
    result = run_query(device_error, "channels", READ_QUERIES["channels"])
    assert result["status"] == "device_error"
    assert result["response_name"] == "CONFIG_NOT_PRESENT"

    short_config = _FakeSerial(encode_frame(_header(0x84) + b"\x00"))
    result = run_query(short_config, "radio-general", READ_QUERIES["radio-general"])
    assert result["status"] == "decode_error"
    assert result["error_type"] == "IncompleteFrame"


def test_cli_rejects_invalid_repetition_before_opening_port() -> None:
    assert main(["read", "health", "--count", "0"]) == 2
    assert main(["read", "health", "--delay", "-1"]) == 2


def test_cli_detect_can_save_json(tmp_path) -> None:
    output = tmp_path / "detect.json"
    assert main(["detect", "--output", str(output)]) == 0
    assert isinstance(json.loads(output.read_text(encoding="utf-8"))["ports"], list)
    assert output.stat().st_mode & 0o777 == 0o600


def test_bounded_history_transaction_unwraps_and_completes() -> None:
    inner_payload = bytes.fromhex("00000001") + bytes.fromhex(
        "3f800000 40000000 40400000 40800000 40a00000 40c00000"
    )
    wrapper = _header(0x01) + bytes((0x2A, 0x98)) + inner_payload
    end = _header(0x00) + bytes.fromhex("00 80")
    connection = _FakeSerial(encode_frame(wrapper) + encode_frame(end))
    result = run_history(connection, 1, 2, expected_node_id=0x18D2D)
    assert connection.written == encode_frame(bytes.fromhex("03 00 00000001 00000002"))
    assert result["status"] == "ok"
    assert result["complete"]
    assert result["record_count"] == 1
    assert result["records"][0]["capture_id"] == 0x2A
    assert result["records"][0]["inner_header"]["am_type"] == 0x98
    assert result["records"][0]["decode_status"] == "ok"


def test_bounded_history_rejects_oversized_range_before_write() -> None:
    connection = _FakeSerial(b"")
    try:
        run_history(connection, 1, 100, max_span_seconds=10)
    except ValueError as exc:
        assert "max_span_seconds" in str(exc)
    else:
        raise AssertionError("oversized history range was accepted")
    assert connection.written == b""
