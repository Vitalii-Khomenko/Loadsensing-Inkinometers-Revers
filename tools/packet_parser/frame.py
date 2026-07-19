"""Worldsensing UART framing and the confirmed protocol-v2 response header.

The implementation mirrors ``g7/a`` (JADX name ``p367g7.C7580a``): a frame is
delimited by DLE/STX and DLE/ETX, and every DLE in the body is duplicated.
There is no length or checksum field at this layer.

The six-byte response header is decoded from ``o7/d.parseHeader``.  Requests
do not use that header: ``h7/S`` serializes them as AM type followed directly
by command-specific bytes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

DLE = 0x10
STX = 0x02
ETX = 0x03
APP_DECODED_BODY_LIMIT = 1024


class FrameError(ValueError):
    """Base class for framing errors."""


class IncompleteFrame(FrameError):
    """The supplied bytes end before a complete frame is available."""


class MalformedFrame(FrameError):
    """A DLE inside a frame is followed by neither DLE nor ETX."""


class FrameTooLarge(FrameError):
    """The decoded frame body exceeds the configured safety limit."""


@dataclass(frozen=True, slots=True)
class ProtocolV2Header:
    """Confirmed six-byte header used by incoming protocol-v2 messages.

    Android's response parser treats the low nibble of byte 0 as the high
    four bits of a 20-bit node ID.  The older generated ``B7/a`` helper calls
    that nibble ``reserved`` and exposes only the low 16 bits as ``moteId``;
    both views are retained here for evidence-preserving analysis.
    """

    version: int
    node_id_high: int
    product_code: int
    node_id: int
    sequence_number: int
    am_type: int

    SIZE = 6
    REQUIRED_VERSION = 4

    @property
    def generated_reserved(self) -> int:
        """Name used for ``node_id_high`` by the generated header helper."""

        return self.node_id_high

    @property
    def generated_mote_id(self) -> int:
        """The 16-bit mote ID exposed by the generated header helper."""

        return self.node_id & 0xFFFF

    @classmethod
    def parse(cls, body: bytes, *, require_version: bool = True) -> "ProtocolV2Header":
        if len(body) < cls.SIZE:
            raise IncompleteFrame(
                f"protocol-v2 body needs at least {cls.SIZE} bytes; got {len(body)}"
            )

        version = body[0] >> 4
        if require_version and version != cls.REQUIRED_VERSION:
            raise MalformedFrame(
                f"expected protocol version {cls.REQUIRED_VERSION}; got {version}"
            )

        node_id_high = body[0] & 0x0F
        node_id = (node_id_high << 16) | int.from_bytes(body[2:4], "big")
        return cls(
            version=version,
            node_id_high=node_id_high,
            product_code=body[1],
            node_id=node_id,
            sequence_number=body[4],
            am_type=body[5],
        )


class _State(Enum):
    WAIT_DLE = auto()
    WAIT_STX = auto()
    IN_BODY = auto()
    AFTER_BODY_DLE = auto()


class StreamFrameParser:
    """Incrementally extract zero or more unescaped bodies from byte chunks."""

    def __init__(self, *, max_body_size: int = APP_DECODED_BODY_LIMIT) -> None:
        if max_body_size <= 0:
            raise ValueError("max_body_size must be positive")
        self.max_body_size = max_body_size
        self._state = _State.WAIT_DLE
        self._body = bytearray()

    @property
    def has_partial_frame(self) -> bool:
        return self._state is not _State.WAIT_DLE

    def reset(self) -> None:
        self._state = _State.WAIT_DLE
        self._body.clear()

    def _append(self, value: int) -> None:
        if len(self._body) >= self.max_body_size:
            self.reset()
            raise FrameTooLarge(
                f"decoded body exceeds {self.max_body_size}-byte safety limit"
            )
        self._body.append(value)

    def feed(self, data: bytes) -> list[bytes]:
        frames: list[bytes] = []

        for value in data:
            if self._state is _State.WAIT_DLE:
                if value == DLE:
                    self._state = _State.WAIT_STX
                continue

            if self._state is _State.WAIT_STX:
                if value == STX:
                    self._body.clear()
                    self._state = _State.IN_BODY
                else:
                    self._state = _State.WAIT_DLE
                continue

            if self._state is _State.IN_BODY:
                if value == DLE:
                    self._state = _State.AFTER_BODY_DLE
                else:
                    self._append(value)
                continue

            if value == DLE:
                self._append(DLE)
                self._state = _State.IN_BODY
            elif value == ETX:
                frames.append(bytes(self._body))
                self._body.clear()
                self._state = _State.WAIT_DLE
            else:
                self.reset()
                raise MalformedFrame(
                    f"DLE in frame body followed by invalid byte 0x{value:02x}"
                )

        return frames


def encode_frame(body: bytes) -> bytes:
    """Add DLE delimiters and duplicate every DLE byte in ``body``."""

    escaped = body.replace(bytes((DLE,)), bytes((DLE, DLE)))
    return bytes((DLE, STX)) + escaped + bytes((DLE, ETX))


def decode_frame(frame: bytes, *, max_body_size: int = APP_DECODED_BODY_LIMIT) -> bytes:
    """Decode exactly one complete frame, ignoring out-of-frame noise."""

    parser = StreamFrameParser(max_body_size=max_body_size)
    frames = parser.feed(frame)
    if parser.has_partial_frame:
        raise IncompleteFrame("input ends in a partial frame")
    if len(frames) != 1:
        raise MalformedFrame(f"expected exactly one frame; decoded {len(frames)}")
    return frames[0]


def encode_request_body(am_type: int, command_payload: bytes = b"") -> bytes:
    """Build the unframed request body used by ``h7/S`` request classes."""

    if not 0 <= am_type <= 0xFF:
        raise ValueError("am_type must fit in one byte")
    return bytes((am_type,)) + command_payload
