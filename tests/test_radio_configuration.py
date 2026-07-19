from tools.firmware_service import crc16_xmodem
from tools.radio_configuration import _backup_body, encode_embedded_auth, encode_embedded_join


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
