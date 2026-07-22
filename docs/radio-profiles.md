# Original Android Radio Profiles

Last updated: 2026-07-15

Status: static-confirmed from the original application's `RadioRegionsConfigs` initializer. The current physical sensor's `EUROPE` match is hardware-confirmed by two repeated reads after official configuration.

## Inventory

The application contains 20 profiles: 15 embedded/Edge profiles and 5 LoRaWAN/Cloud profiles. The complete frequency groups, default group, MAC family, SF range/default, TX power, ETSI/ADR defaults, 500 kHz flag, downlinks and TTI plan names are preserved in `analysis/protocol/radio_profiles.json` and protected by consistency tests.

| Profile | Plan | MAC | Band | SF min/default/max | TX dBm | Groups |
|---|---|---|---|---:|---:|---:|
| EUROPE | Edge | EU868_V1 | CE | 7/11/11 | 14 | 1 |
| FCC | Edge | US915_V1 | FCC | 7/9/11 | 20 | 8 |
| R923A | Edge | US915_V1 | FCC | 7/11/11 | 20 | 2 |
| R923P | Edge | EU868_V1 | FCC | 7/11/11 | 20 | 1 |
| R922S | Edge | EU868_V1 | FCC | 7/11/11 | 20 | 1 |
| R923M | Edge | EU868_V1 | FCC | 7/12/12 | 20 | 2 |
| R926C | Edge | EU868_V1 | FCC | 7/9/12 | 20 | 1 |
| R866I | Edge | EU868_V1 | CE | 7/11/12 | 20 | 1 |
| R923T | Edge | EU868_V1 | FCC | 7/9/12 | 20 | 2 |
| R922K | Edge | EU868_V1 | FCC | 7/7/9 | 14 | 1 |
| R916I_LEGACY | Edge | EU868_V1 | FCC | 7/10/10 | 14 | 1 |
| R920J | Edge | EU868_V1 | FCC | 7/9/9 | 14 | 3 |
| R922B | Edge | EU868_V1 | FCC | 7/9/9 | 20 | 8 |
| AUSTRALIA500KHZ | Edge | US915_V1 | FCC | 7/9/11 | 20 | 4 |
| R869M | Edge | EU868_V1 | CE | 7/9/9 | 14 | 1 |
| EUROPE_WAN | Cloud | EU868_WAN_V1_0 | CE | 7/11/11 | 14 | 1 |
| FCC_WAN | Cloud | US915_WAN_V1_0 | FCC | 7/9/9 | 20 | 8 |
| R922S_WAN | Cloud | AS923_WAN_V1_0 | FCC | 7/9/9 | 14 | 1 |
| R923A_WAN | Cloud | AU915_WAN_V1_0 | FCC | 7/9/9 | 20 | 7 |
| R865I_WAN | Cloud | EU868_WAN_V1_0 | CE | 7/11/11 | 20 | 1 |

The table order is min/default/max for readability; the JSON stores `[min, max, default]`, matching the constructor.

## Current sensor match

Node `101677` currently matches the embedded `EUROPE` template exactly for the profile-controlled fields:

- MAC `EU868_V1`;
- CE band behavior, ETSI and ADR enabled;
- SF11 and 14 dBm;
- enabled uplinks 868.1, 868.3, 868.5, 868.85, 869.05 and 869.525 MHz;
- unused channel positions seven and eight are zero.

Gateway-specific identity, network ID, password, address, reporting period and slot duration are not regional-profile constants. The browser can apply the physically validated embedded `EUROPE` radio-general and uplink-channel values while preserving those gateway-specific fields. It requires the connected product `0x4E`, derives an exact node-specific confirmation, verifies ACK and readback, and rolls back on failure. The other 19 profiles remain inspection-only because their complete write paths have not been physically validated on this sensor.

## Decompiler boundary

Some APK constants are rendered incorrectly by JADX. The registry records explicit initializer values, while ambiguous network-size/minimum-period constants remain documented separately from these radio profiles. A profile name is an application label, not by itself a regulatory determination for a deployment site.
