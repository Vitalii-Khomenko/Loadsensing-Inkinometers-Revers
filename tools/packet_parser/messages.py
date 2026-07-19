"""Confirmed read-only response payload decoders.

Input to these functions is the complete unescaped protocol-v2 body, including
the six-byte response header. Bit fields are consumed MSB-first, matching the
Android ``DefaultBitInput`` implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
import struct

from .frame import IncompleteFrame, MalformedFrame, ProtocolV2Header


class _Bits:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.offset = 0

    def unsigned(self, width: int) -> int:
        if width <= 0 or self.offset + width > len(self.data) * 8:
            raise IncompleteFrame(f"need {width} bits at payload bit {self.offset}")
        value = 0
        for _ in range(width):
            byte, bit = divmod(self.offset, 8)
            value = (value << 1) | ((self.data[byte] >> (7 - bit)) & 1)
            self.offset += 1
        return value

    def signed(self, width: int) -> int:
        value = self.unsigned(width)
        sign = 1 << (width - 1)
        return value - (1 << width) if value & sign else value

    def boolean(self) -> bool:
        return bool(self.unsigned(1))


def _payload(body: bytes, allowed_types: set[int]) -> tuple[ProtocolV2Header, _Bits]:
    header = ProtocolV2Header.parse(body)
    if header.am_type not in allowed_types:
        expected = ", ".join(f"0x{x:02X}" for x in sorted(allowed_types))
        raise MalformedFrame(f"expected AM type {expected}; got 0x{header.am_type:02X}")
    return header, _Bits(body[ProtocolV2Header.SIZE :])


@dataclass(frozen=True, slots=True)
class NodeHealth:
    header: ProtocolV2Header
    timestamp: int
    uptime: int
    battery_v: float
    temperature_c: int
    serial_number: int
    firmware_major: int
    firmware_minor: int
    time_delta: int | None
    message_version: int | None = None
    humidity_percent: float | None = None
    humidity_std: float | None = None
    humidity_delta: float | None = None
    humidity_reserved: int | None = None


def decode_node_health(body: bytes) -> NodeHealth:
    header, bits = _payload(body, {0x40, 0x46, 0x4F})
    timestamp = bits.unsigned(32)

    if header.am_type != 0x4F:
        uptime = bits.unsigned(32)
        battery = bits.unsigned(16) / 1000.0
        temperature = bits.signed(8)
        serial = bits.unsigned(16)
        major = bits.unsigned(8)
        minor = bits.unsigned(8)
        delta = bits.unsigned(16) if header.am_type == 0x46 else None
        return NodeHealth(
            header, timestamp, uptime, battery, temperature, serial, major, minor, delta
        )

    message_version = bits.unsigned(2)
    uptime = bits.unsigned(30)
    battery = bits.unsigned(12) / 100.0
    temperature = bits.signed(8)
    humidity = humidity_std = humidity_delta = None
    humidity_reserved = None
    if message_version == 1:
        humidity = bits.unsigned(10) / 10.0
        humidity_std = bits.unsigned(9) / 10.0
        humidity_delta = bits.unsigned(10) / 10.0
        humidity_reserved = bits.unsigned(3)
    serial = bits.unsigned(20)
    major = bits.unsigned(8)
    minor = bits.unsigned(8)
    delta = bits.unsigned(16)
    return NodeHealth(
        header,
        timestamp,
        uptime,
        battery,
        temperature,
        serial,
        major,
        minor,
        delta,
        message_version,
        humidity,
        humidity_std,
        humidity_delta,
        humidity_reserved,
    )


@dataclass(frozen=True, slots=True)
class NodeInfo:
    header: ProtocolV2Header
    message_version: int | None
    serial_number: int
    firmware_major: int
    firmware_minor: int
    firmware_build_time: int


def decode_node_info(body: bytes) -> NodeInfo:
    header, bits = _payload(body, {0x03, 0x09})
    message_version = None
    if header.am_type == 0x03:
        serial = bits.unsigned(16)
    else:
        message_version = bits.unsigned(2)
        bits.unsigned(6)  # reserved
        serial = bits.unsigned(32)
    return NodeInfo(
        header,
        message_version,
        serial,
        bits.unsigned(8),
        bits.unsigned(8),
        bits.unsigned(32),
    )


@dataclass(frozen=True, slots=True)
class ExtendedNodeInfo:
    header: ProtocolV2Header
    message_version: int
    board1_msb: int
    board1_lsb: int
    board2_msb: int
    board2_lsb: int


def decode_extended_node_info(body: bytes) -> ExtendedNodeInfo:
    header, bits = _payload(body, {0x05})
    return ExtendedNodeInfo(
        header,
        bits.unsigned(8),
        bits.unsigned(8),
        bits.unsigned(8),
        bits.unsigned(8),
        bits.unsigned(8),
    )


@dataclass(frozen=True, slots=True)
class AxisReading:
    angle_deg: float
    stddev_g: float


@dataclass(frozen=True, slots=True)
class AlarmEvent:
    upper_threshold: bool
    threshold_deg: float


@dataclass(frozen=True, slots=True)
class Til90AlarmReading:
    header: ProtocolV2Header
    timestamp: int
    message_version: int
    error_code: int
    high_precision: bool
    temperature_c: float
    axes: dict[str, AxisReading]
    alarm_configured: bool
    alarm_triggered: bool
    alarm_active: bool
    alarm_reserved: int | None
    alarms: dict[str, AlarmEvent]


def decode_til90_alarm_reading(body: bytes) -> Til90AlarmReading:
    header, bits = _payload(body, {0x50})
    timestamp = bits.unsigned(32)
    version = bits.unsigned(2)
    enabled = {
        "z": bits.boolean(),
        "y": bits.boolean(),
        "x": bits.boolean(),
    }
    error = bits.unsigned(4)
    high_precision = bits.boolean()
    temperature = bits.signed(12) / 10.0
    axes: dict[str, AxisReading] = {}
    for axis in ("x", "y", "z"):
        if enabled[axis]:
            angle = bits.signed(21) / 10000.0
            raw_stddev = bits.unsigned(20)
            scale = 256000.0 if high_precision else 51200.0
            axes[axis] = AxisReading(angle, raw_stddev / scale)

    configured = bits.boolean()
    triggered = bits.boolean()
    active = bits.boolean()
    alarms: dict[str, AlarmEvent] = {}
    reserved = None
    if active:
        alarm_enabled = {
            "z": bits.boolean(),
            "y": bits.boolean(),
            "x": bits.boolean(),
        }
        reserved = bits.unsigned(3)
        for axis in ("x", "y", "z"):
            if alarm_enabled[axis]:
                alarms[axis] = AlarmEvent(bits.boolean(), bits.signed(15) / 100.0)

    return Til90AlarmReading(
        header,
        timestamp,
        version,
        error,
        high_precision,
        temperature,
        axes,
        configured,
        triggered,
        active,
        reserved,
        alarms,
    )


@dataclass(frozen=True, slots=True)
class Til90Reading:
    header: ProtocolV2Header
    timestamp: int
    message_version: int
    error_code: int
    high_precision: bool
    temperature_c: float
    axes: dict[str, AxisReading]
    azimuth: int | None


def decode_til90_reading(body: bytes) -> Til90Reading:
    header, bits = _payload(body, {0x4C})
    timestamp = bits.unsigned(32)
    version = bits.unsigned(2)
    enabled = {"z": bits.boolean(), "y": bits.boolean(), "x": bits.boolean()}
    error = bits.unsigned(4)
    precise = bits.boolean()
    temperature = bits.signed(12) / 10.0
    axes: dict[str, AxisReading] = {}
    for axis in ("x", "y", "z"):
        if enabled[axis]:
            angle = bits.signed(21) / 10000.0
            stddev = bits.unsigned(20) / (256000.0 if precise else 51200.0)
            axes[axis] = AxisReading(angle, stddev)
    azimuth = bits.unsigned(9) if version == 1 else None
    return Til90Reading(header, timestamp, version, error, precise, temperature, axes, azimuth)


def decode_sampling_rate(body: bytes) -> int:
    _, bits = _payload(body, {0x82})
    return bits.unsigned(24)


@dataclass(frozen=True, slots=True)
class Til90Calibration:
    header: ProtocolV2Header
    timestamp: int
    coefficients: dict[str, float]


def decode_til90_calibration(body: bytes) -> Til90Calibration:
    header, bits = _payload(body, {0x98})
    timestamp = bits.unsigned(32)
    raw = body[ProtocolV2Header.SIZE + 4 :]
    if len(raw) < 24:
        raise IncompleteFrame("calibration payload needs six float32 coefficients")
    values = struct.unpack(">6f", raw[:24])
    names = ("x_offset", "x_gain", "y_offset", "y_gain", "z_offset", "z_gain")
    return Til90Calibration(header, timestamp, dict(zip(names, values)))


@dataclass(frozen=True, slots=True)
class Til90ChannelConfig:
    header: ProtocolV2Header
    version: int
    data_enabled: dict[str, bool]
    threshold_enabled: dict[str, bool]
    off_delay: int
    thresholds: dict[str, tuple[float, float]]


@dataclass(frozen=True, slots=True)
class Inc360ChannelConfig:
    """Normal G6 TIL90/INC360 enabled-axis configuration (AM 0x9A)."""

    header: ProtocolV2Header
    version: int
    reserved: int
    enabled: dict[str, bool]


def decode_inc360_channel_config(body: bytes) -> Inc360ChannelConfig:
    header, bits = _payload(body, {0x9A})
    return Inc360ChannelConfig(
        header,
        bits.unsigned(2),
        bits.unsigned(3),
        {"z": bits.boolean(), "y": bits.boolean(), "x": bits.boolean()},
    )


def decode_til90_channel_config(body: bytes) -> Til90ChannelConfig:
    header, bits = _payload(body, {0x9B})
    version = bits.unsigned(3)
    bits.unsigned(1)
    data = {"z": bits.boolean(), "y": bits.boolean(), "x": bits.boolean()}
    alarms = {"z": bits.boolean(), "y": bits.boolean(), "x": bits.boolean()}
    delay = bits.unsigned(4)
    thresholds = {}
    for axis in ("x", "y", "z"):
        maximum = bits.signed(15) / 100.0
        minimum = bits.signed(15) / 100.0
        thresholds[axis] = (minimum, maximum)
    return Til90ChannelConfig(header, version, data, alarms, delay, thresholds)


@dataclass(frozen=True, slots=True)
class BluetoothConfiguration:
    header: ProtocolV2Header
    version: int
    reserved: int
    enabled: bool
    ota_enabled: bool
    tx_power: int
    advertising_interval: int
    polling_interval: int
    extended_advertisements: bool
    phy_rate: int
    max_bidirectional_throughput: bool
    dle_gatt_size: int
    connection_length: int
    use_default_pin_seed: bool


def decode_bluetooth_config(body: bytes) -> BluetoothConfiguration:
    header, b = _payload(body, {0xA5})
    return BluetoothConfiguration(
        header, b.unsigned(4), b.unsigned(7), b.boolean(), b.boolean(),
        b.unsigned(6), b.unsigned(3), b.unsigned(3), b.boolean(),
        b.unsigned(2), b.boolean(), b.unsigned(8), b.unsigned(10), b.boolean(),
    )


@dataclass(frozen=True, slots=True)
class LoraGeneralConfig:
    header: ProtocolV2Header
    message_version: int
    mac_version: int
    channel_500khz_enabled: bool
    radio_enabled: bool
    etsi_enabled: bool
    adr_enabled: bool
    spreading_factor: int
    tx_power: int
    channel_duty_cycle_enabled: bool
    use_custom_rx2: bool
    rx2_spreading_factor: int
    rx2_frequency_hz: int
    send_slot_time: int


def decode_lora_general_config(body: bytes) -> LoraGeneralConfig:
    header, bits = _payload(body, {0x84})
    message_version = bits.unsigned(4)
    mac_version = bits.unsigned(4)
    channel_500khz_enabled = bits.boolean()
    radio_enabled = bits.boolean()
    etsi_enabled = bits.boolean()
    adr_enabled = bits.boolean()
    spreading_factor = bits.unsigned(4)
    tx_power = bits.unsigned(8)
    bits.unsigned(2)  # reserved
    channel_duty_cycle_enabled = bits.boolean()
    use_custom_rx2 = bits.boolean()
    rx2_spreading_factor = bits.unsigned(4)
    return LoraGeneralConfig(
        header,
        message_version,
        mac_version,
        channel_500khz_enabled,
        radio_enabled,
        etsi_enabled,
        adr_enabled,
        spreading_factor,
        tx_power,
        channel_duty_cycle_enabled,
        use_custom_rx2,
        rx2_spreading_factor,
        bits.unsigned(32),
        bits.unsigned(16),
    )


def decode_lora_address(body: bytes) -> int:
    _, bits = _payload(body, {0x83})
    return bits.unsigned(32)


@dataclass(frozen=True, slots=True)
class LoraChannelsConfig:
    header: ProtocolV2Header
    message_version: int
    channels_type: int
    enabled: tuple[bool, ...]
    frequencies_hz: tuple[int, ...]


def decode_lora_channels_config(body: bytes) -> LoraChannelsConfig:
    header, bits = _payload(body, {0x85, 0x8E})
    version = bits.unsigned(4)
    channels_type = bits.unsigned(4)
    mask = bits.unsigned(8)
    enabled = tuple(bool(mask & (1 << (7 - index))) for index in range(8))
    frequencies = tuple(bits.unsigned(32) for _ in range(8))
    frequencies = tuple(
        frequency if enabled[index] else 0
        for index, frequency in enumerate(frequencies)
    )
    return LoraChannelsConfig(header, version, channels_type, enabled, frequencies)


def decode_lora_slot_time(body: bytes) -> int:
    _, bits = _payload(body, {0x90})
    return bits.unsigned(16)


def decode_lora_network_id(body: bytes) -> int:
    _, bits = _payload(body, {0x8D})
    return bits.unsigned(32)


@dataclass(frozen=True, slots=True)
class LoraJoinConfig:
    header: ProtocolV2Header
    reserved_prefix: int
    dev_eui: str
    app_eui: str
    max_time_without_downlink_minutes: int
    join_retry_max_time_divisor: int
    join_retry_min_time_multiplier: int
    join_retry_multiplier_on_failure: int
    max_link_checks_before_reconnect: int
    activation_mode: int
    frame_counter_mode: int
    reserved_suffix: int


def decode_lora_join_config(body: bytes) -> LoraJoinConfig:
    header, bits = _payload(body, {0x94})
    reserved_prefix = bits.unsigned(8)
    dev_eui = bytes(bits.unsigned(8) for _ in range(8)).hex().upper()
    app_eui = bytes(bits.unsigned(8) for _ in range(8)).hex().upper()
    max_time_without_downlink = bits.unsigned(16)
    retry_divisor = bits.unsigned(8)
    retry_min_multiplier = bits.unsigned(6)
    retry_failure_multiplier = bits.unsigned(2)
    max_link_checks = bits.unsigned(8)
    activation_mode = bits.unsigned(1)
    frame_counter_mode = bits.unsigned(1)
    reserved_suffix = bits.unsigned(6)
    return LoraJoinConfig(
        header,
        reserved_prefix,
        dev_eui,
        app_eui,
        max_time_without_downlink,
        retry_divisor,
        retry_min_multiplier,
        retry_failure_multiplier,
        max_link_checks,
        activation_mode,
        frame_counter_mode,
        reserved_suffix,
    )


def encode_history_request(start_epoch: int, end_epoch: int, *, raw_only: bool = False) -> bytes:
    for name, value in (("start_epoch", start_epoch), ("end_epoch", end_epoch)):
        if not 0 <= value <= 0xFFFFFFFF:
            raise ValueError(f"{name} must fit in an unsigned 32-bit field")
    return bytes((0x03, 0x56 if raw_only else 0x00)) + start_epoch.to_bytes(
        4, "big"
    ) + end_epoch.to_bytes(4, "big")


def unwrap_recovered_message(body: bytes) -> tuple[int, bytes]:
    """Return ``(capture_id, reconstructed_inner_body)`` for outer AM 0x01."""

    header = ProtocolV2Header.parse(body)
    if header.am_type != 0x01:
        raise MalformedFrame(f"expected recovery wrapper AM 0x01; got 0x{header.am_type:02X}")
    if len(body) < 8:
        raise IncompleteFrame("recovery wrapper needs capture ID and inner AM type")
    return body[6], body[:5] + body[7:]


def decode_response_code(body: bytes) -> int:
    _, bits = _payload(body, {0x00})
    return bits.unsigned(16)


def decode_stored_data_interval(body: bytes) -> tuple[int, int]:
    """Return ``(oldest_epoch, newest_epoch)`` from response AM 0x02."""

    _, bits = _payload(body, {0x02})
    return bits.unsigned(32), bits.unsigned(32)
