# Configuration IDs

Last updated: 2026-07-15

Status: confirmed by static analysis of `h7/o.smali`. No sensor traffic was generated.

All configuration reads use request AM type `0x00` (`InGetCfgMsg`). The second request byte selects the configuration. A successful response uses the selected configuration ID as its AM type.

| Configuration | Decimal | Hex | Response class |
|---|---:|---:|---|
| LORA_GENERAL | 132 | `0x84` | `C8829A` |
| LORA_ADDR | 131 | `0x83` | `C8930w` |
| LORA_CHANNEL_GROUP_0 | 133 | `0x85` | `C8931x` |
| LORA_DOWN_CHANNELS | 142 | `0x8E` | `C8933z` |
| LORA_SLOT_TIME | 144 | `0x90` | `C8835F` |
| LORA_NET_ID | 141 | `0x8D` | `C8831C` |
| SAMPLING_RATE | 130 | `0x82` | `C8916p0` |
| INC_CALIBRATION | 146 | `0x92` | `C8915p` |
| LORA_JOIN | 148 | `0x94` | `C8830B` |
| INC360_CH_CONFIG | 154 | `0x9A` | `C8922s` |
| INC360_CALIBRATION | 152 | `0x98` | `C8919r` |
| INC360_ALARM_CH_CONFIG | 155 | `0x9B` | `C8917q` |
| LASERTIL90_CH_CONFIG | 153 | `0x99` | `C8928v` |
| VW_CH_CONFIG | 128 | `0x80` | `C8918q0` |
| VW_THRESHOLD | 150 | `0x96` | `C8923s0` |
| ANALOG_CONFIG | 143 | `0x8F` | `C8891f` |
| PICO_CONFIG | 147 | `0x93` | `C8839H` |
| DYNAMIC_CONFIG | 158 | `0x9E` | `C9170j` |
| GNSS_CONFIG | 159 | `0x9F` | `C9799b` |
| GNSS_BASE_POSITION_CONFIG | 161 | `0xA1` | `C9798a` |
| GNSS_CORR_CH_CONFIG | 163 | `0xA3` | `C9800c` |
| GNSS_CORR_KEYS_CONFIG | 162 | `0xA2` | `C9802d` |
| BLUETOOTH_CONFIG | 165 | `0xA5` | `C9026a` |
| DIG_CONFIG | 145 | `0x91` | `C8898i` |
| DIG_GENERIC_MODBUS_INSTRUCTIONS | 151 | `0x97` | `C8906l` |
| DIG_CUSTOM_COMMAND | 7 | `0x07` | `C8902k` |
| DIG_POWER_SUPPLY_THRESHOLD | 149 | `0x95` | `C8908m` |

## TIL90 configuration reads

The physical G6 normal TIL90, routed as `LS_G6_INC360`, uses:

- calibration: request body `00 98`, response AM type `0x98`, class `C8919r`;
- enabled channels: request body `00 9A`, response AM type `0x9A`, class `C8922s`.

The alarm/G7-style `Til90Node` path uses:

- calibration: request body `00 98`, response AM type `0x98`, class `C8919r`;
- channel/alarm configuration: request body `00 9B`, response AM type `0x9B`, class `C8917q`.

Inherited read-only configuration methods additionally use sampling rate, LoRa, and Bluetooth IDs from the table above.
