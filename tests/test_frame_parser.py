import pytest

from tools.packet_parser.frame import (
    DLE,
    FrameTooLarge,
    IncompleteFrame,
    MalformedFrame,
    ProtocolV2Header,
    StreamFrameParser,
    decode_frame,
    encode_frame,
    encode_request_body,
)


def test_encode_and_decode_duplicate_dle_bytes() -> None:
    body = bytes.fromhex("40 2a 00 01 10 05")

    framed = encode_frame(body)

    assert framed == bytes.fromhex("10 02 40 2a 00 01 10 10 05 10 03")
    assert decode_frame(framed) == body


def test_stream_parser_preserves_partial_frame_between_chunks() -> None:
    parser = StreamFrameParser()

    assert parser.feed(bytes.fromhex("99 10")) == []
    assert parser.feed(bytes.fromhex("02 40 2a 00")) == []
    assert parser.has_partial_frame
    assert parser.feed(bytes.fromhex("01 00 05 10 03")) == [
        bytes.fromhex("40 2a 00 01 00 05")
    ]
    assert not parser.has_partial_frame


def test_stream_parser_returns_multiple_frames_from_one_read() -> None:
    first = bytes.fromhex("01")
    second = bytes.fromhex("02 10 03")

    assert StreamFrameParser().feed(encode_frame(first) + encode_frame(second)) == [
        first,
        second,
    ]


def test_malformed_escape_is_rejected() -> None:
    with pytest.raises(MalformedFrame, match="invalid byte"):
        decode_frame(bytes.fromhex("10 02 01 10 04 10 03"))


def test_incomplete_frame_is_rejected_by_one_shot_decoder() -> None:
    with pytest.raises(IncompleteFrame):
        decode_frame(bytes.fromhex("10 02 01 02"))


def test_decoded_body_limit_matches_android_buffer_safely() -> None:
    parser = StreamFrameParser(max_body_size=3)

    with pytest.raises(FrameTooLarge):
        parser.feed(encode_frame(b"1234"))


def test_protocol_v2_header_uses_big_endian_20_bit_node_id() -> None:
    # version=4, high node nibble=A, product=0x2B, low node bits=0xCDEF
    body = bytes.fromhex("4a 2b cd ef 7c 98 de ad")

    header = ProtocolV2Header.parse(body)

    assert header.version == 4
    assert header.node_id_high == 0xA
    assert header.product_code == 0x2B
    assert header.node_id == 0xACDEF
    assert header.generated_reserved == 0xA
    assert header.generated_mote_id == 0xCDEF
    assert header.sequence_number == 0x7C
    assert header.am_type == 0x98
    assert body[ProtocolV2Header.SIZE :] == bytes.fromhex("de ad")


def test_protocol_v2_header_rejects_short_and_wrong_version() -> None:
    with pytest.raises(IncompleteFrame):
        ProtocolV2Header.parse(b"\x40" * 5)
    with pytest.raises(MalformedFrame, match="version"):
        ProtocolV2Header.parse(bytes.fromhex("30 01 00 02 00 05"))


def test_request_body_is_am_type_followed_by_command_payload() -> None:
    assert encode_request_body(0x98, bytes.fromhex("01 02")) == bytes.fromhex(
        "98 01 02"
    )
    with pytest.raises(ValueError):
        encode_request_body(0x100)
