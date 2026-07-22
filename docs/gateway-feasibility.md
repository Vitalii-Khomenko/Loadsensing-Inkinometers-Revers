# Gateway Feasibility Notes

Last updated: 2026-07-15

## Short answer

A custom gateway is feasible, but there are three very different targets:

1. a standard LoRaWAN gateway used with CMT Cloud — realistic and officially supported with some third-party gateways;
2. a fully independent LoRaWAN gateway and network server — technically realistic, but node keys, provisioning, payload decoding, and downlinks must be solved;
3. a replacement for CMT Edge using the current embedded radio profile — substantially harder because it includes Worldsensing-specific authentication, packet semantics, and server behavior.

Reconfiguring a Worldsensing gateway through its supported CMT/admin interface is reasonable. Replacing its firmware or bypassing licensing/access controls is a separate high-risk reverse-engineering project and is not required for sensor interoperability.

## Current sensor radio state

Direct reads from node `101677` show:

```text
MAC version byte: 0 = EU868_V1 (Edge/embedded, not LoRaWAN)
uplink channels: 868.1–869.525 MHz, six enabled
radio enabled: true
network ID: 27484
DevEUI/AppEUI: provisioned
sampling/slot: 3600/3000 seconds
```

The APK separates `CMT Edge radio` from `CMT Cloud radio`. It maps MAC value 2 to `US915_V1` and value 3 to `US915_WAN_V1_0`. Embedded configuration uses a numeric network ID and password through `sendEmbeddedRadioAuth()`. Cloud V2 configuration uses a network token and a LoRaWAN join flow.

The current node is provisioned for an existing embedded Edge network, not a generic LoRaWAN network. Changing it to LoRaWAN would be a multi-command authenticated configuration operation, not just changing frequencies.

## Option comparison

| Option | Difficulty | What is already known | Main missing pieces |
|---|---:|---|---|
| Official Worldsensing Edge gateway + CMT Edge | Low | Intended path for current embedded profile | Valid network ID/password and supported gateway administration |
| Official or validated third-party LoRaWAN gateway + CMT Cloud | Medium | Worldsensing publicly confirms third-party LoRaWAN gateway compatibility | CMT Cloud account/network token, node provisioning, correct regional profile |
| SX1302/SX1303 gateway + independent LoRaWAN server | Medium–high | Standard gateway hardware and servers such as ChirpStack exist | Valid node keys/EUIs, join provisioning, payload codec, configuration downlinks |
| Receive-only LoRa laboratory capture | Medium | Frequencies, SF and channel plans are readable | Exact over-air packet format and security; suitable SDR/concentrator hardware |
| Full independent CMT Edge replacement | High | APK exposes network ID/password authentication and some HTTP API models | Over-air authentication/encryption, packet decoder, deduplication, storage, downlink scheduler, node management |
| Custom firmware on a Worldsensing gateway | High/risky | Gateway exposes local USB-C and Ethernet according to product information | Hardware access, boot chain, signed images, recovery, license/support consequences |

## Realistic recommended paths

### Path A — Keep the current Edge protocol

Use an official Edge gateway and integrate outward through CMT Edge's supported interfaces. Worldsensing documents common data-export interfaces including MQTT, REST API, FTP, and FTPS. This avoids reversing the radio security layer and is the shortest path to a reliable private deployment.

### Path B — Move to supported LoRaWAN

Worldsensing states that third-party LoRaWAN gateways have been tested with CMT Cloud, including an SG50 example. This makes a non-Worldsensing RF gateway realistic when the nodes are provisioned for CMT Cloud/LoRaWAN. It still does not make CMT Cloud optional: the official workflow supplies network identity/token and handles node registration.

Official references:

- [Worldsensing third-party LoRaWAN gateway test](https://www.worldsensing.com/knowledge-center/we-tested-it-low-power-open-lorawan-gateway-fully-compatible-with-worldsensing-networks/)
- [Worldsensing 4G Rugged Gateway specifications](https://www.worldsensing.com/product/4g-rugged-gateway/)
- [Worldsensing management software overview](https://www.worldsensing.com/management-software/)

### Path C — Build a completely independent network

A practical research gateway can use an SX1302/SX1303 concentrator or an SDR for receive-only analysis. For a production bidirectional network, the project must recover or legitimately provision:

- LoRaWAN DevEUI, JoinEUI/AppEUI and root/session keys, or the complete embedded authentication scheme;
- uplink payload decoding for every supported response/product;
- frame counters, replay protection, acknowledgements and downlink scheduling;
- configuration and coverage-test downlinks;
- regional channel plans and legal transmission parameters;
- storage, device registry, time synchronization, monitoring and recovery.

Receiving a LoRa modulation burst is easy compared with securely operating the whole network.

## Existing industrial computer as the site server

An existing site industrial computer can be the local storage, processing and forwarding server, but an antenna cannot be connected directly to an ordinary computer and become a gateway. The radio path requires:

```text
regional sub-GHz antenna
  -> matching/filtering and protected RF feed
  -> LoRa transceiver or multi-channel concentrator
  -> packet-forwarder/radio driver
  -> network server and authentication
  -> payload decoder
  -> local database/application
```

An SDR can capture raw RF samples for research, but a reliable bidirectional network also requires concurrent channel reception, acknowledgements/downlinks, frame counters, authentication, key management and regional radio compliance. For a standard LoRaWAN deployment, an SX1302/SX1303-class concentrator is the normal gateway radio rather than an antenna-only USB device. It still does not solve access to device keys or the Worldsensing payload format.

Before official post-repair programming, the reference sensor stored embedded `US915_V1` (MAC value 2), 902.3–903.7 MHz uplinks, radio disabled, and zero network identity. The operator then configured it for an existing gateway; readback now shows embedded `EU868_V1`, six 868 MHz uplinks, radio enabled, and network ID `27484`. This confirms that the earlier values were lost/non-operational repair state rather than the intended site profile. A generic LoRaWAN concentrator still cannot be assumed to decode or operate this proprietary embedded network. Independent operation would require either:

- supported reprovisioning to a correct regional LoRaWAN profile plus legitimate keys and a payload decoder; or
- recovery and implementation of the proprietary Edge over-air protocol and authentication using lawful, controlled captures.

The first path is substantially more realistic. Worldsensing's own interoperability description states that independent LoRaWAN operation depends on authentication access, payload interpretation and a compatible LoRaWAN Network Server.

## Existing Worldsensing gateway connected locally

For bypassing cloud transport, a CMT Edge gateway is the shortest and supported architecture:

```text
TIL90 sensors -- LoRa --> CMT Edge gateway -- Ethernet/LAN --> industrial computer
                                                        -> local database/browser
                                                        -> customer server
```

Worldsensing states that CMT Edge keeps collected data in the gateway, works without internet, is accessible over the local Ethernet network, and exports through MQTT, FTP/FTPS, Modbus TCP and APIs. The industrial computer can therefore ingest a supported local export, normalize/store it, and forward it to the customer's server without using CMT Cloud.

The 4G Rugged Gateway specification lists USB-C for `local access` and 5 V power, but it does not document USB-C as a continuous raw-measurement serial stream. USB must therefore not be assumed to be the integration interface. Ethernet plus a documented CMT Edge export is the preferred path. The exact gateway model, Edge/Cloud variant, software version, license and enabled exports must be identified before implementation.

A Cloud-only gateway may be configured primarily as a packet forwarder to a remote network server. Whether it can provide local decoded data cannot be inferred from the presence of USB or Ethernet; that depends on its product variant and installed software. Replacing its configured server or firmware is not necessary when an Edge gateway or an independent, legitimately provisioned LoRaWAN gateway is available.

## Can an existing Worldsensing gateway be reconfigured?

Supported network, backhaul, primary/secondary, and data-export settings should be changed through the gateway's documented CMT/admin workflow. The public product description confirms Ethernet, cellular backhaul and local USB-C access, but the APK does not contain the gateway operating system or prove that arbitrary firmware replacement is supported.

Before examining a physical gateway, preserve:

- exact model and product code;
- current configuration export and software version;
- ownership and license/support status;
- Ethernet/USB enumeration and exposed services without attempting login bypass;
- a recovery method supplied by the vendor.

No firmware, factory reset, root access, or bootloader work should be attempted without a recoverable spare gateway.

## Regional radio warning

The earlier shorthand statement that "US915 cannot be used in Europe" was too broad. EU rules harmonise some networked-SRD/IoT operation in portions of 915–921 MHz under specific technical conditions; the commonly referenced harmonised non-specific range includes 915–919.4 MHz. Therefore the number `915` alone is not evidence of unlawful operation.

The earlier recovered state stored `US915_V1` with uplinks at 902.3–903.7 MHz. Those channels are not the same as EU868 or the harmonised 915–919.4 MHz core described by the reviewed EU decisions. Subsequent official configuration produced `EU868_V1` and 868.1–869.525 MHz uplinks, confirming that the earlier values were not the intended working profile for this site.

Before our tooling transmits, identify the original project/gateway profile and actual country, compare a known working sensor, and verify the applicable authorization and technical conditions. Do not overwrite an official working profile based only on the APK enum name. Official references: [EU Decision 2018/1538, current consolidated record](https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX%3A32018D1538) and [EU Decision 2022/180](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32022D0180).

## Recommended next investigation

1. Identify the exact gateway model available to the operator and whether it is Edge or Cloud.
2. Export its supported configuration and record the software version using normal administration only.
3. Decide whether the goal is local CMT Edge integration, CMT Cloud with a third-party LoRaWAN gateway, or complete independence.
4. For complete independence, begin with receive-only over-air capture from a legally configured test node and gateway; do not start with gateway firmware modification.
5. Keep non-EUROPE profile writes blocked until their MAC mapping, channel-group selection, gateway compatibility, regulatory constraints, and physical readback have been validated to the same standard as the embedded EUROPE workflow.
