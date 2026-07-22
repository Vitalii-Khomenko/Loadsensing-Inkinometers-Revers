from tools.firmware_service import crc16_xmodem
import pytest

from tools.radio_configuration import (
    EUROPE_GENERAL_BODY,
    RadioConfigurationError,
    _backup_body,
    apply_regional_profile,
    encode_embedded_auth,
    encode_embedded_join,
    encode_lora_channels,
    load_regional_profile,
)


def test_embedded_join_matches_physical_current_identifiers():
    body = encode_embedded_join(101677, 27484)
    assert body == bytes.fromhex(
        "94 00 70b3d52c70118d2d 70b3d52c70106b5c 2760 00 01 18 00"
    )


def test_backup_write_body_retains_configuration_type():
    snapshot = {"evidence": [{
        "query": "radio-general",
        "rx_body": "41 4e 8d 2d 4e 84 10 7b 0e",
    }]}
    assert _backup_body(snapshot, "radio-general") == bytes.fromhex("84 10 7b 0e")


def test_embedded_auth_has_apk_key_order_network_id_and_crc():
    body = encode_embedded_auth(27484, "temporary-test-password")
    assert len(body) == 39 and body[0] == 0x8D
    assert body[33:37] == (27484).to_bytes(4, "big")
    assert int.from_bytes(body[-2:], "big") == crc16_xmodem(body[1:-2])
    assert body == encode_embedded_auth(27484, "temporary-test-password")
    assert body != encode_embedded_auth(27484, "another-password")


def test_hardware_validated_europe_profile_write_bodies():
    profile = load_regional_profile("EUROPE")
    assert EUROPE_GENERAL_BODY == bytes.fromhex(
        "84 10 7b 0e 0c 3c cb f7 00 00 00"
    )
    assert encode_lora_channels(
        0x85, profile["uplink_hz"][profile["default_group"]]
    ) == bytes.fromhex(
        "85 00 fc 33be27a0 33c134e0 33c44220 33c99950 "
        "33cca690 33d3e608 00000000 00000000"
    )


def test_unvalidated_regional_profiles_remain_blocked():
    with pytest.raises(RadioConfigurationError, match="only for the embedded EUROPE"):
        load_regional_profile("FCC")
    with pytest.raises(RadioConfigurationError, match="unknown original-app profile"):
        load_regional_profile("NOT_A_PROFILE")


def test_europe_profile_skips_serial_writes_when_already_configured():
    profile = load_regional_profile("EUROPE")
    snapshot = {
        "device": {"node_id": 101677, "product_code": 0x4E},
        "configuration": {
            "radio_general": {
                "mac_version": 0,
                "channel_500khz_enabled": False,
                "radio_enabled": True,
                "etsi_enabled": True,
                "adr_enabled": True,
                "spreading_factor": 11,
                "tx_power": 14,
            },
            "radio_channels": {
                "frequencies_hz": profile["uplink_hz"][0],
                "enabled": [True, True, True, True, True, True, False, False],
            },
        },
    }

    class AlreadyEuropeService:
        writes_enabled = True

        @staticmethod
        def backup():
            return snapshot

    result = apply_regional_profile(
        AlreadyEuropeService(), "EUROPE", "APPLY PROFILE 101677 EUROPE"
    )
    assert result["status"] == "regional-profile-already-configured"
    assert result["operations"] == 0
