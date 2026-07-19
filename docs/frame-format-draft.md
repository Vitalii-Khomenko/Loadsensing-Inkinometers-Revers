# Worldsensing UART frame format — draft

Last updated: 2026-07-15

Status: static reconstruction validated by direct read-only traffic from the physical G6 sensor.

## Scope and evidence

This document describes the framing recovered from application version 2.17.1. The primary target was `analysis/jadx/sources/p367g7/C7580a.java`, checked against `analysis/apktool/smali_classes2/g7/a.smali`.

Direct dependencies and consumers were also checked:

- `C7584d` / `g7/d.smali`: response type dispatch and protocol-v2 validation;
- `C0392a`, `AbstractC0566b`, and `C0565a`: generated six-byte header and big-endian bit access;
- `AbstractC7694S` / `h7/S.smali`: request serialization;
- `AbstractC8885d` / `o7/d.smali`: active response-header parser;
- `C7596n` / `g7/n.smali`: partial and multiple-frame handling;
- `InterfaceC2963b`, `InterfaceC7693Q`, and `InterfaceC8882c`: transport and message boundaries.

Where JADX and smali differ, this draft follows smali.

## UART envelope

The serial stream uses DLE byte stuffing:

```text
10 02 | escaped body | 10 03
 DLE STX                DLE ETX
```

Every `10` byte in the unescaped body is serialized as `10 10`. No other byte is escaped.

Example:

```text
unescaped body:  40 2A 00 01 10 05
wire bytes:      10 02 40 2A 00 01 10 10 05 10 03
```

There is no explicit body length, checksum, or CRC in `C7580a`. Frame length is determined solely by the unescaped `DLE ETX` delimiter. Message-specific payloads could still contain their own integrity fields; none is added or checked by this framing layer.

The Android decoder allocates a 1024-byte decoded-body buffer. It does not perform an explicit bounds check before writing, so bodies over 1024 bytes would fail with an array bounds error. The Python parser treats 1024 as a safe default maximum and raises a specific error.

## Request body: host to node

Outgoing request classes inherit `AbstractC7694S`. Its constructor writes the AM type as the first byte, after which each subclass writes command-specific fields:

```text
offset  size  field
0       1     AM type
1       N     command-specific payload
```

`C7580a.send()` calls `request.getPayload()` and applies only the DLE envelope. It does not add a node ID, sequence number, length, or CRC. Any addressing required by a particular request must therefore be part of that request's command-specific payload or implicit in the connected node.

## Response body: node to host

`C7584d` accepts only bodies of at least six bytes whose first version nibble is `4`. The active parser in `AbstractC8885d.parseHeader`, confirmed from `o7/d.smali`, consumes the following header:

```text
byte  bits   field
0     7..4   protocol version (must be 4)
0     3..0   high four bits of node ID
1     7..0   product code
2..3  15..0  low 16 bits of node ID, big-endian
4     7..0   sequence number
5     7..0   AM type
6..N         message-specific payload
```

The node ID used by the active response objects is therefore a 20-bit unsigned value:

```text
node_id = ((body[0] & 0x0F) << 16) | (body[2] << 8) | body[3]
```

All multibyte header values are read most-significant-bit/byte first. The AM type is an unsigned byte and selects the response class in `C7584d.f20513b`. The sequence number is also an unsigned byte; static analysis shows it is exposed by response objects, but `C7580a` itself does not correlate requests and responses with it.

### Header naming conflict

The generated `C0392a` (`ProtocolHeaderV2`) helper labels byte 0's low nibble as `reserved` and exposes only bytes 2–3 as a 16-bit `moteId`. In contrast, the response parser actually used by all `AbstractC8885d` messages reads that nibble, shifts it left by 16, and combines it with bytes 2–3. The implementation and CSV preserve both interpretations, but the Python `node_id` follows the active smali behavior: 20 bits.

The physical G6 response begins with `0x41`, and its low nibble contributes bit 16 of node ID `0x18D2D` (`101677`). The active 20-bit interpretation is therefore hardware-confirmed for this G6. G7 remains untested.

## Streaming and incomplete messages

`C7580a` retains its state and decoded-body buffer across calls. If a USB read ends before `DLE ETX`, it throws `LsIncompleteMessage`, but does not reset the state. `C7596n` catches that exception and waits for the next receive callback.

When a single USB read contains multiple frames, `C7580a` stops after the first terminator and records the number of consumed input bytes. `C7596n` slices the remaining bytes and invokes the parser again. Thus the protocol supports:

- frames split across arbitrary USB reads;
- multiple complete frames in one USB read;
- noise before a `DLE STX` start marker.

Inside a body, `DLE` must be followed by either another `DLE` (escaped data) or `ETX` (end marker). Any other following byte moves the Android state machine to an error state and discards the malformed frame.

## Answers established by this phase

- Frame preamble/header at UART layer: `DLE STX` (`10 02`).
- Frame terminator: `DLE ETX` (`10 03`).
- Escaping: duplicate each body byte `10`.
- Explicit length: absent.
- Frame checksum/CRC: absent at this layer.
- Minimum framed request: five wire bytes for a one-byte AM type (`10 02 TT 10 03`).
- Minimum accepted framed response: ten wire bytes when its six-byte header contains no escaped DLE.
- Response protocol version: high nibble `4`.
- Response AM type: byte 5 of the unescaped body.
- Response node ID: active parser uses 20-bit big-endian composition; generated helper documents a conflicting 16-bit view.
- Response sequence number: one byte at offset 4.
- Partial/multiple reads: state is retained; consumed-byte count enables repeated parsing.

## Still unconfirmed

- Whether G7 nodes use the upper four bits in the same way.
- Whether any message-specific payload embeds a CRC or length.
- Exact semantic relationship between request and response sequence numbers.
- Whether malformed-frame recovery on real traffic has additional transport-level behavior.

The first G6 frames are preserved under `captures/reference_sessions/2026-07-15T103257Z/` and exercised by `tests/test_hardware_capture_20260715.py`.
