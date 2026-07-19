# Read-only Message Formats

Last updated: 2026-07-15

Status: static-analysis draft confirmed against Java and smali. No sensor communication occurred.

All offsets below start after the six-byte protocol-v2 response header. Bit fields are read MSB-first and are not implicitly byte-aligned.

## Node health (`0x40`, `0x46`, `0x4F`)

AM `0x40` payload is 15 bytes: timestamp `u32`, uptime `u32`, battery millivolts `u16`, temperature `s8`, serial `u16`, firmware major `u8`, firmware minor `u8`.

AM `0x46` appends a `u16` time delta and is 17 bytes.

AM `0x4F` uses the newer bit layout:

```text
u32 timestamp
u2  message version
u30 uptime
u12 battery voltage / 100 V
s8  temperature °C
if message version == 1:
    u10 relative humidity / 10 %
    u9  humidity standard deviation / 10
    u10 humidity delta / 10
    u3  reserved
u20 serial number
u8  firmware major
u8  firmware minor
u16 time delta
```

Its payload is 21 bytes for message version 1 and 17 bytes without the humidity block.

## Node information (`0x03`, `0x09`)

AM `0x03` has an eight-byte payload: serial `u16`, firmware major `u8`, firmware minor `u8`, and build timestamp `u32`.

AM `0x09` has an eleven-byte payload: message version `u2`, reserved `u6`, serial `u32`, firmware major `u8`, firmware minor `u8`, and build timestamp `u32`.

## Extended node information (`0x05`)

The five-byte payload contains message version `u8`, followed by MSB and LSB bytes for board 1 and board 2 hardware versions.

## TIL90 alarm reading (`0x50`)

The payload is variable-length:

```text
u32 timestamp
u2  message version
bool Z enabled
bool Y enabled
bool X enabled
u4  error code
bool high precision
s12 temperature / 10 °C
for each enabled axis in X Y Z order:
    s21 angle / 10000°
    u20 standard deviation / 256000 G when high precision
        or standard deviation / 51200 G otherwise
bool alarm configured
bool alarm triggered in this data message
bool alarms active
if alarms active:
    bool Z alarm enabled
    bool Y alarm enabled
    bool X alarm enabled
    u3 reserved
    for each enabled alarm in X Y Z order:
        bool upper threshold broken
        s15 threshold value / 100°
```

Error codes are `0` OK, `1` sensor not responding, `2` self-test error, and `3` invalid temperature. The Android object clears invalid decoded values according to this code; the Python low-level decoder retains the raw decoded fields and exposes the error code so policy can be applied by its caller.

## Regular TIL90 reading (`0x4C`)

This format shares the timestamp, version, Z/Y/X enable flags, error code, precision flag, temperature, and conditional X/Y/Z axis fields described for `0x50`. It has no alarm block. When message version is 1, a final unsigned nine-bit azimuth is present.

## Sampling rate (`0x82`)

The payload is a single unsigned 24-bit big-endian sampling period. The application treats the value as seconds.

## Calibration (`0x98`)

The payload is 28 bytes: unsigned 32-bit Unix timestamp followed by X offset, X gain, Y offset, Y gain, Z offset, and Z gain as six big-endian IEEE-754 float32 values.

## Channel/alarm configuration (`0x9B`)

The payload is 13 bytes: three-bit version, one reserved bit, Z/Y/X data enable flags, Z/Y/X threshold enable flags, four-bit off delay, then signed 15-bit maximum/minimum pairs for X, Y, and Z scaled by `1/100°`.

## Normal G6 channel configuration (`0x9A`)

The one-byte payload contains a two-bit version, three reserved bits, then Z/Y/X enable flags. The physical product `0x4E` returned payload `07`: version 0, reserved 0, and all three axes enabled.

## Bluetooth configuration (`0xA5`)

The payload is exactly 48 bits: version `u4`, reserved `u7`, enabled, OTA enabled, TX power `u6`, advertising interval `u3`, polling interval `u3`, extended-advertisement flag, PHY rate `u2`, maximum bidirectional throughput flag, DLE/GATT size `u8`, connection length `u10`, and default-PIN-seed flag.

## LoRa configuration (`0x83`–`0x94`)

Hardware-tested decoders now cover:

- `0x83`: unsigned 32-bit LoRa address;
- `0x84`: version/MAC nibbles, radio flags, SF, TX power, RX2 configuration, and send slot;
- `0x85` and `0x8E`: version/type nibbles, eight-channel enable mask, and eight unsigned 32-bit frequencies;
- `0x8D`: unsigned 32-bit network ID;
- `0x90`: unsigned 16-bit slot time;
- `0x94`: prefix byte, DevEUI, AppEUI, retry/link parameters, activation mode, and frame-counter mode.

These responses contain no network password and no single associated gateway ID.
