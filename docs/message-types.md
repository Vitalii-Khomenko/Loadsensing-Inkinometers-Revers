# Message Type Registry

Last updated: 2026-07-15

Status: complete registry of the 60 AM types accepted by the Android response dispatcher. The detailed machine-readable table is `analysis/protocol/message_registry.csv`.

## Evidence and method

The registry was recovered from `analysis/apktool/smali_classes2/g7/d.smali`. Its synthetic factories are implemented by `g7/b.smali` and `g7/c.smali`. Smali was required because JADX substituted unrelated Mapbox constants for several numeric AM types.

The dispatcher validates protocol version 4, reads AM type from response-header byte 5, and selects one registered response constructor. Unknown AM types cause a runtime parsing error.

Confirmed registry size:

```text
60 unique AM types
minimum: 0x00
maximum: 0xA5
```

## TIL90 read-only command paths

The following paths are confirmed statically:

| Operation | Request body | Expected response AM type/class |
|---|---|---|
| Node health | `01` | `0x40`, `0x46`, or `0x4F` / `C8912o` |
| Node information | `43 69 00 00` | `0x03` or `0x09` / `C8924t` |
| Extended node information | `0E` | `0x05` / `C8910n` |
| Take live reading | `02` | `0x4C` / `C8880b0` or `0x50` / `C8877a0` |
| Sampling rate | `00 82` | `0x82` / `C8916p0` |
| TIL90 calibration | `00 98` | `0x98` / `C8919r` |
| G6 normal TIL90 channels | `00 9A` | `0x9A` / `C8922s` |
| Alarm/G7 TIL90 channel config | `00 9B` | `0x9B` / `C8917q` |
| Bluetooth config | `00 A5` | `0xA5` / `C9026a` |
| Stored-data interval | `04` | `0x02` / `C8926u` |
| Historical records | `03 FILTER START END` | `0x01` wrappers, then `0x00` / code `0x0080` |

The node-information request is four bytes because `C8513a` extends `C8407e`: AM type `0x43`, backward-compatibility first byte `0x69`, and a zeroed 16-bit compatibility field.

Hardware validation on product `0x4E` confirmed the G6 normal path `00 9A → 0x9A`. Sending `00 9B` to that node returned response code `0x0004` (`CONFIG_NOT_PRESENT`).

These byte strings are documentation derived from serializers. They have not been transmitted by the independent implementation.

AM type `0x01` is the historical recovered-message wrapper, not a generic unused response. AM type `0x02` reports the oldest and newest stored-data timestamps as two unsigned big-endian 32-bit values. AM type `0x00` is shared by ordinary command acknowledgements and stream termination, so it is relevant to both read and write control flows.

## TIL90 reading classes

`Til90Node` registers two valid reading classes:

- `C8880b0`, AM type `0x4C`: INC360-style X/Y/Z angle reading with standard deviation and temperature;
- `C8877a0`, AM type `0x50`: INC360 Alarm-style X/Y/Z reading with alarm state and thresholds.

The request used by both single and multiple live-reading methods is AM type `0x02`. The response type identifies the actual reading variant.

`C8880b0` confirms the following decoded values:

- 32-bit Unix timestamp in UTC;
- enabled X/Y/Z channel flags;
- four-bit error code;
- high-precision flag;
- signed 12-bit temperature scaled by `1/10 °C`;
- enabled-axis angles as signed 21-bit values scaled by `1/10000°`;
- enabled-axis standard deviations as unsigned 20-bit values with precision-dependent scale.

The complete variable-length alarm-reading layout is documented in `docs/read-only-message-formats.md` and implemented in `tools/packet_parser/messages.py`.

## Calibration response

AM type `0x98` (`C8919r`) contains:

- a 32-bit Unix calibration timestamp;
- X offset and gain;
- Y offset and gain;
- Z offset and gain;
- each coefficient encoded as a 32-bit IEEE-754 float in big-endian bit order.

After the six-byte protocol header the calibration payload is 28 bytes, making the decoded response body 34 bytes before DLE escaping.

## Channel/alarm configuration response

AM type `0x9B` (`C8917q`) contains a 13-byte bit-packed payload after the six-byte response header:

- three-bit configuration version; currently only version 0 is accepted;
- one reserved bit;
- three data-channel enable flags;
- three absolute-threshold enable flags;
- four-bit threshold-off delay;
- six signed 15-bit minimum/maximum thresholds scaled by `1/100`.

The decoded response body is therefore 19 bytes before DLE escaping.

## Remaining validation work

The TIL90 read-only subset is implemented and its core paths are physically captured. Product mapping and upper node-ID bits are hardware-confirmed. Response sequence-number semantics and comparison with the official application's displayed scale factors remain open.
