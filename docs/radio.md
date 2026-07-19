# Physical G6 Radio Configuration

Last updated: 2026-07-15

Status: decoded from direct read-only traffic on node `101677`, product `0x4E`, firmware `2.81`.

## Current values

| Field | Value |
|---|---|
| Radio MAC | byte `0` = `EU868_V1` (embedded/Edge) |
| Radio enabled | Yes |
| Network ID | `27484` / `0x6B5C` |
| LoRa address | `81890605` / `0x04E18D2D` |
| DevEUI | `70B3D52C70118D2D` |
| AppEUI | `70B3D52C70106B5C` |
| ADR | Enabled |
| ETSI | Enabled |
| Spreading factor | 11 |
| TX power | 14 |
| Sampling period | 3600 seconds |
| Slot time | 3000 seconds |
| Custom RX2 | Disabled |
| Stored RX2 frequency | 1,020,000,000 Hz; ignored while custom RX2 is disabled |
| RX2 spreading factor | 12 |
| Uplink channels | 868.1, 868.3, 868.5, 868.85, 869.05, 869.525 MHz; final two entries disabled |
| Stored downlink table | 923.3–927.5 MHz retained from prior state; operational relevance unconfirmed |

The current values were read twice with identical results. Raw bodies are preserved in `captures/reference_sessions/2026-07-15T161221Z-post-gateway-config/`. The earlier disabled `US915_V1` state is preserved in `captures/reference_sessions/2026-07-15T103257Z/radio-traffic.txt`.

## Gateway interpretation

The node is now configured for an active embedded/Edge network: radio enabled, network ID `27484`, and non-zero EUIs. This proves provisioning state, but a configuration read still does not identify a specific receiving gateway or prove that the latest scheduled uplink was received.

LoRa nodes are also not associated with exactly one gateway in the same way as a Wi-Fi client. An uplink can be received by multiple gateways. The APK's direct link-check response reports only link margin and gateway count. Specific gateway IDs are obtained from the backend coverage-test API, using network credentials and an active radio coverage operation.

Coverage testing is not part of the CLI read allowlist because it transmits over LoRa for up to 60 seconds and interacts with external gateway/backend state.

## Before/after repair evidence

The operator reported that this restored unit had lost its settings during repair and configured it for an existing gateway with the official workflow. The subsequent read changed MAC `US915_V1 → EU868_V1`, radio `off → on`, uplinks `902.3–903.7 → 868.1–869.525 MHz`, sampling `300 → 3600` seconds, slot `300 → 3000` seconds, network ID `0 → 27484`, and populated both EUIs. Identity, calibration, enabled axes and LoRa address remained unchanged.

The stored 923.3–927.5 MHz downlink table did not change. Static Android region configuration for embedded Europe supplies the six 868 MHz channel table without the FCC downlink list. Together with `use_custom_rx2=false`, this means the retained downlink/RX2 fields should be treated as inactive or unresolved storage until gateway/on-air evidence proves otherwise.

## Password boundary

No configuration response contains the Edge network password. `NetworkIdFragment` loads `PREF_EDGE_NETWORK_PASSWORD` from Android SharedPreferences and decrypts it locally. `BaseNode` uses the password only in radio authentication/configuration send methods. Consequently, direct serial read-only access can retrieve network ID and radio parameters but cannot retrieve the original password.
