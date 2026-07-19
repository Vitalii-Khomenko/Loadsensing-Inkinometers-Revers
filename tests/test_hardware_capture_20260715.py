from datetime import datetime, timezone

import pytest

from tools.packet_parser import decode_frame
from tools.packet_parser.messages import (
    decode_extended_node_info,
    decode_inc360_channel_config,
    decode_lora_address,
    decode_lora_channels_config,
    decode_lora_general_config,
    decode_lora_join_config,
    decode_lora_network_id,
    decode_lora_slot_time,
    decode_node_health,
    decode_node_info,
    decode_sampling_rate,
    decode_stored_data_interval,
    decode_til90_calibration,
    decode_til90_reading,
)


def _wire(value: str) -> bytes:
    return bytes.fromhex(value)


def _body(value: str) -> bytes:
    return bytes.fromhex(value)


def test_real_health_info_and_hardware_frames() -> None:
    health = decode_node_health(decode_frame(_wire(
        "10 02 41 4e 8d 2d 47 4f 6a 57 61 ec 00 00 32 17 14 f1 "
        "b1 8d 2d 02 51 00 00 10 03"
    )))
    assert health.header.node_id == 101677
    assert health.header.node_id_high == 1
    assert health.header.product_code == 0x4E
    assert health.battery_v == 3.35
    assert health.temperature_c == 27
    assert (health.firmware_major, health.firmware_minor) == (2, 81)

    info = decode_node_info(decode_frame(_wire(
        "10 02 41 4e 8d 2d 48 09 00 00 01 8d 2d 02 51 65 67 0c 56 10 03"
    )))
    assert info.serial_number == 101677
    assert datetime.fromtimestamp(info.firmware_build_time, timezone.utc) == datetime(
        2023, 11, 29, 10, 3, 2, tzinfo=timezone.utc
    )

    extended = decode_extended_node_info(decode_frame(_wire(
        "10 02 41 4e 8d 2d 49 05 00 00 00 00 00 10 03"
    )))
    assert (extended.board1_msb, extended.board1_lsb) == (0, 0)
    assert (extended.board2_msb, extended.board2_lsb) == (0, 0)


def test_real_live_reading_frame() -> None:
    reading = decode_til90_reading(decode_frame(_wire(
        "10 02 41 4e 8d 2d 4b 4c 6a 57 62 2c 38 04 5b f4 0c e0 "
        "00 08 06 fa 50 00 05 69 44 c0 00 01 80 10 03"
    )))
    assert reading.error_code == 0
    assert reading.temperature_c == 27.8
    assert reading.axes["x"].angle_deg == -2.4473
    assert reading.axes["y"].angle_deg == 2.8581
    assert reading.axes["z"].angle_deg == 86.236


def test_real_read_only_configuration_frames() -> None:
    sampling = decode_sampling_rate(decode_frame(_wire(
        "10 02 41 4e 8d 2d 4c 82 00 01 2c 10 03"
    )))
    assert sampling == 300

    calibration = decode_til90_calibration(decode_frame(_wire(
        "10 02 41 4e 8d 2d 4d 98 64 83 4c 9d c5 19 72 2d 3f 80 "
        "92 8a 44 d2 5d 85 3f 7e 34 22 45 47 c0 4b 3f 7e fd fc 10 03"
    )))
    assert calibration.coefficients["x_offset"] == pytest.approx(-2455.135986)
    assert calibration.coefficients["z_gain"] == pytest.approx(0.996063)

    channels = decode_inc360_channel_config(decode_frame(_wire(
        "10 02 41 4e 8d 2d 52 9a 07 10 03"
    )))
    assert channels.version == 0
    assert channels.reserved == 0
    assert channels.enabled == {"z": True, "y": True, "x": True}

    interval = decode_stored_data_interval(decode_frame(_wire(
        "10 02 41 4e 8d 2d 50 02 00 00 00 01 6a 57 62 2c 10 03"
    )))
    assert interval == (1, 1784111660)


def test_real_radio_configuration_frames() -> None:
    general = decode_lora_general_config(decode_frame(_wire(
        "10 02 41 4e 8d 2d 55 84 12 19 14 0c 33 d3 e6 08 00 00 10 03"
    )))
    assert not general.radio_enabled
    assert general.adr_enabled
    assert general.spreading_factor == 9
    assert general.tx_power == 20
    assert general.rx2_frequency_hz == 869_525_000

    address = decode_lora_address(decode_frame(_wire(
        "10 02 41 4e 8d 2d 56 83 04 e1 8d 2d 10 03"
    )))
    assert address == 81_890_605

    uplink = decode_lora_channels_config(decode_frame(_wire(
        "10 02 41 4e 8d 2d 57 85 00 ff 35 c8 01 60 35 cb 0e a0 "
        "35 ce 1b e0 35 d1 29 20 35 d4 36 60 35 d7 43 a0 35 da "
        "50 e0 35 dd 5e 20 10 03"
    )))
    assert uplink.frequencies_hz[0] == 902_300_000
    assert uplink.frequencies_hz[-1] == 903_700_000
    assert all(uplink.enabled)

    downlink = decode_lora_channels_config(decode_frame(_wire(
        "10 02 41 4e 8d 2d 58 8e 00 ff 37 08 70 a0 37 11 98 60 "
        "37 1a c0 20 37 23 e7 e0 37 2d 0f a0 37 36 37 60 37 3f "
        "5f 20 37 48 86 e0 10 03"
    )))
    assert downlink.frequencies_hz[0] == 923_300_000
    assert downlink.frequencies_hz[-1] == 927_500_000

    assert decode_lora_slot_time(decode_frame(_wire(
        "10 02 41 4e 8d 2d 59 90 01 2c 10 03"
    ))) == 300
    assert decode_lora_network_id(decode_frame(_wire(
        "10 02 41 4e 8d 2d 5a 8d 00 00 00 00 10 03"
    ))) == 0

    join = decode_lora_join_config(decode_frame(_wire(
        "10 02 41 4e 8d 2d 5b 94 00 00 00 00 00 00 00 00 00 00 "
        "00 00 00 00 00 00 00 00 3c 00 01 03 00 10 03"
    )))
    assert join.dev_eui == "0000000000000000"
    assert join.app_eui == "0000000000000000"
    assert join.max_time_without_downlink_minutes == 60


def test_post_gateway_programming_radio_frames() -> None:
    general = decode_lora_general_config(_body(
        "41 4e 8d 2d f9 84 10 7b 0e 0c 3c cb f7 00 00 00"
    ))
    assert general.mac_version == 0
    assert general.radio_enabled
    assert general.etsi_enabled
    assert general.adr_enabled
    assert general.spreading_factor == 11
    assert general.tx_power == 14
    assert not general.use_custom_rx2

    uplink = decode_lora_channels_config(_body(
        "41 4e 8d 2d fb 85 00 fc 33 be 27 a0 33 c1 34 e0 33 c4 42 20 "
        "33 c9 99 50 33 cc a6 90 33 d3 e6 08 00 00 00 00 00 00 00 00"
    ))
    assert uplink.frequencies_hz == (
        868_100_000, 868_300_000, 868_500_000, 868_850_000,
        869_050_000, 869_525_000, 0, 0,
    )
    assert uplink.enabled == (True, True, True, True, True, True, False, False)

    assert decode_lora_slot_time(_body(
        "41 4e 8d 2d fd 90 0b b8"
    )) == 3000
    assert decode_lora_network_id(_body(
        "41 4e 8d 2d fe 8d 00 00 6b 5c"
    )) == 27484

    join = decode_lora_join_config(_body(
        "41 4e 8d 2d ff 94 00 70 b3 d5 2c 70 11 8d 2d 70 b3 d5 2c "
        "70 10 6b 5c 27 60 00 01 18 00"
    ))
    assert join.dev_eui == "70B3D52C70118D2D"
    assert join.app_eui == "70B3D52C70106B5C"
    assert join.max_time_without_downlink_minutes == 10080
