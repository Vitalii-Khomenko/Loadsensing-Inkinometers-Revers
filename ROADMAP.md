# TIL90 Reverse Engineering Roadmap

Last updated: 2026-07-15

## Update policy

This file is the dated project progress log and roadmap. It must be updated whenever static analysis, passive captures, tests, or hardware work produce new information.

Each update must:

- use an ISO date (`YYYY-MM-DD`);
- be written in English;
- distinguish confirmed facts from hypotheses and unresolved questions;
- list created or changed deliverables;
- record validation results;
- state whether sensor communication or destructive operations occurred.

## Safety status

- Independent tooling has transmitted the documented read requests and one controlled sampling write/restore sequence recorded on 2026-07-15.
- `/dev/ttyUSB0` was opened at 115200 8N1 with DTR/RTS disabled and exclusive access.
- Sampling was changed from 300 to 301 seconds and successfully restored to 300 with ACK and readback verification.
- The operator later used the official workflow to configure the repaired node for an existing gateway; current readback is sampling 3600 seconds and enabled embedded `EU868_V1`. This external state change was not performed by the independent tooling.
- A bounded reboot and a reversible channel trial were performed on node `101677`: uptime reset, Z was temporarily disabled, and all persistent configuration was verified unchanged/restored.
- Sampling, channel flags and gateway radio-slot time are the hardware-validated persistent write families. No full radio/network authentication, calibration, time, identity, factory-reset, bootloader, or firmware write has been performed.

## Progress log

### 2026-07-15 — Project specification reviewed

Status: completed

Reviewed the project specification and the existing analysis notes:

- `Goal.md`;
- `APK-Info.md`;
- `Command.md`.

The immediate target was identified as the complete analysis of:

```text
analysis/jadx/sources/p367g7/C7580a.java
```

The required outputs for this stage were a frame-format draft, a field registry, a Python parser, and automated tests.

### 2026-07-15 — UART framing recovered

Status: completed by static analysis

Confirmed from `C7580a.java` and `analysis/apktool/smali_classes2/g7/a.smali`:

- a frame starts with `DLE STX` (`10 02`);
- a frame ends with `DLE ETX` (`10 03`);
- every data byte `DLE` (`10`) is escaped as `10 10`;
- the UART envelope contains no explicit length field;
- the UART envelope adds and validates no checksum or CRC;
- the Android decoder retains state across incomplete USB reads;
- multiple frames in one USB read are processed using a consumed-byte counter;
- the Android decoded-body buffer is 1024 bytes.

The absence of a frame-level CRC does not prove that individual message payloads never contain their own integrity fields.

### 2026-07-15 — Request and response body formats separated

Status: completed by static analysis

Confirmed that host-to-node requests and node-to-host responses do not use the same internal header.

Requests produced by `AbstractC7694S` contain:

```text
byte 0: AM type
byte 1 onward: command-specific payload
```

`C7580a.send()` applies only the DLE envelope to this request body. It does not add a node ID, sequence number, length, or CRC.

Incoming protocol-v2 responses contain a six-byte header followed by the message-specific payload.

### 2026-07-15 — Protocol-v2 response header recovered

Status: completed by Java/smali comparison

The active response parser in `analysis/apktool/smali_classes2/o7/d.smali` reads:

```text
byte 0, bits 7..4: protocol version, required value 4
byte 0, bits 3..0: high four bits of the active parser's node ID
byte 1: product code
bytes 2..3: low 16 bits of node ID, big-endian
byte 4: sequence number
byte 5: AM type
byte 6 onward: message-specific payload
```

The active parser therefore constructs a 20-bit node ID:

```text
node_id = ((body[0] & 0x0F) << 16) | (body[2] << 8) | body[3]
```

Important discrepancy:

- the generated `C0392a` header helper calls byte 0's low nibble `reserved` and exposes bytes 2–3 as a 16-bit `moteId`;
- the active response parser uses that nibble as the upper four bits of a 20-bit node ID;
- JADX omitted one four-bit read while decompiling `AbstractC8885d.parseHeader`;
- smali was used as the authoritative source for the implemented parser.

Whether real G6 or G7 node IDs use the upper four bits remains unconfirmed until passive captures are available.

### 2026-07-15 — Frame parser and tests implemented

Status: completed

Created:

- `docs/frame-format-draft.md`;
- `analysis/protocol/frame_fields.csv`;
- `tools/packet_parser/__init__.py`;
- `tools/packet_parser/frame.py`;
- `tests/test_frame_parser.py`.

The Python implementation supports:

- frame encoding and DLE escaping;
- one-shot frame decoding;
- incremental parsing across multiple chunks;
- multiple frames in one chunk;
- noise before a frame;
- malformed-escape detection;
- a configurable decoded-body size limit;
- protocol-v2 header decoding;
- request-body construction beginning with AM type.

Validation result:

```text
9 tests passed in 0.01 seconds
Python bytecode compilation succeeded
frame_fields.csv: 15 data rows, 9 columns
```

The tests use synthetic frames only. No hardware communication occurred.

### 2026-07-15 — Complete response AM-type registry recovered

Status: completed by smali analysis

Recovered all response types registered by the Android dispatcher in `g7/d.smali` and resolved the two synthetic factories in `g7/b.smali` and `g7/c.smali`.

Confirmed results:

- 60 unique response AM types are registered;
- the registered range is `0x00` through `0xA5` with gaps;
- health responses use AM types `0x40`, `0x46`, and `0x4F` with the same `C8912o` parser;
- node-information responses use `0x03` and `0x09` with the same `C8924t` parser;
- TIL90 live-reading responses use `0x4C` (`C8880b0`) and `0x50` (`C8877a0`);
- unknown AM types are rejected by the Android dispatcher.

Created:

- `analysis/protocol/message_registry.csv`;
- `docs/message-types.md`;
- `tests/test_message_registry.py`.

An initial incorrect total of 59 entries was detected by the registry test. A direct count of `HashMap.put` instructions in smali confirmed the correct total of 60, and the documentation was corrected.

### 2026-07-15 — Configuration IDs fully recovered

Status: completed by Java/smali comparison

Recovered all 27 configuration IDs from `h7/o.smali`, including constants that JADX incorrectly rendered as Mapbox style values.

Important TIL90 read-only requests:

```text
sampling rate:       request 00 82 -> response AM 82
calibration:         request 00 98 -> response AM 98
channel/alarm config request 00 9B -> response AM 9B
Bluetooth config:    request 00 A5 -> response AM A5
```

Created `docs/configuration-ids.md`.

### 2026-07-15 — Initial TIL90 read-only message paths documented

Status: completed for command and response identification

Confirmed request bodies and response classes for node health, node information, extended node information, live reading, sampling rate, calibration, channel/alarm configuration, and Bluetooth configuration.

New payload findings:

- TIL90/INC360 reading `0x4C` contains UTC timestamp, enabled-axis flags, error status, precision flag, temperature, X/Y/Z angles, and per-axis standard deviations;
- angles are signed 21-bit values scaled by `1/10000°`;
- temperature is a signed 12-bit value scaled by `1/10 °C`;
- calibration response `0x98` contains a 32-bit UTC timestamp and six big-endian IEEE-754 float coefficients;
- channel/alarm response `0x9B` has a 13-byte bit-packed payload containing enable flags, delay, and six signed threshold values scaled by `1/100`.

Validation result after adding registry tests:

```text
13 tests passed in 0.06 seconds
60 dispatcher entries matched 60 CSV rows
```

No sensor communication occurred.

### 2026-07-15 — Read-only status and alarm payload decoders implemented

Status: completed by Java/smali comparison and synthetic tests

Recovered complete field layouts for:

- node health AM types `0x40`, `0x46`, and `0x4F`;
- node information AM types `0x03` and `0x09`;
- extended node information AM type `0x05`;
- TIL90 alarm reading AM type `0x50`.

New confirmed findings:

- health `0x40` has a 15-byte payload and no time delta;
- health `0x46` has a 17-byte payload with a 16-bit time delta;
- health `0x4F` uses a 20-bit serial number and a 12-bit battery field;
- health `0x4F` message version 1 includes a 32-bit humidity sub-block;
- node info `0x03` uses a 16-bit serial number;
- node info `0x09` uses a 32-bit serial number and an explicit two-bit message version;
- extended node info provides two two-byte board hardware versions;
- TIL90 alarm reading `0x50` is variable-length and bit-packed without implicit byte alignment;
- enabled axis readings are serialized in X/Y/Z order even though enable flags are serialized Z/Y/X;
- enabled alarm events follow the same X/Y/Z payload order;
- alarm threshold values are signed 15-bit values scaled by `1/100°`.

Created:

- `tools/packet_parser/messages.py`;
- `tests/test_read_only_messages.py`;
- `docs/read-only-message-formats.md`.

Validation result:

```text
18 tests passed in 0.03 seconds
Python bytecode compilation succeeded
```

All message tests use synthetic bodies generated from the statically recovered layouts. No sensor communication occurred.

### 2026-07-15 — Pre-hardware static analysis completed

Status: completed; reference capture is the next gate

Completed the remaining work that can be verified without connecting a sensor:

- implemented regular TIL90 reading `0x4C`, sampling `0x82`, calibration `0x98`, channel/alarm `0x9B`, and Bluetooth `0xA5` decoders;
- reconstructed historical request encoding, recovered-message wrapping, defragmentation handoff, and stream termination;
- confirmed recovery completion response code `0x0080` and coverage-test completion `0x0081` from smali;
- created an 18-operation read-only request/response registry;
- inventoried and SHA-256 hashed all 15 files in the APK firmware directory;
- confirmed that G6 TIL90 is routed as `LS_G6_INC360`, G6 alarm TIL90 as `LS_G6_INC360_ALARM`, and the explicit `Til90Node` class is G7;
- created a passive-capture handoff with validation gates.

Created or completed:

- `docs/protocol.md`;
- `docs/history-protocol.md`;
- `docs/firmware-inventory.md`;
- `docs/passive-capture-plan.md`;
- `analysis/protocol/request_response_pairs.csv`;
- `analysis/firmware/inventory.csv`;
- `tests/test_til90_config_messages.py`;
- `tests/test_static_inventories.py`.

Validation result:

```text
24 tests passed in 0.04 seconds
15 firmware files matched recorded sizes and SHA-256 hashes
18 read-only operations passed registry validation
```

No serial port was opened and no sensor communication occurred.

### 2026-07-15 — Repository audit and one-cable Linux workflow completed

Status: completed; hardware reference capture remains the next gate

Rechecked the maintained Markdown, CSV registries, Python parser, tests, and the relevant Java/smali evidence. Raw investigation transcripts were retained as archives rather than treated as current instructions.

Corrections made:

- AM type `0x00` is used for acknowledgements and stream termination, not only writes;
- AM type `0x01` is the historical recovered-message wrapper `C8911n0`;
- AM type `0x02` is `C8926u`, containing the oldest and newest stored-data timestamps;
- the read-only registry now includes request `04` to response `0x02`, for 18 operations total;
- the firmware count is explicitly limited to the 15 files in the APK `firmwares/` directory;
- LoRa entries are identified statically but are not described as implemented Python payload decoders;
- the hardware session is called a reference capture because the official application actively sends read requests.

Repository organization added:

- root `README.md` as the project entry point;
- `docs/README.md` as the maintained documentation index;
- `captures/` storage rules and a reusable session metadata template;
- archive notices on `APK-Info.md` and `Command.md`;
- a Linux one-cable workflow in `docs/passive-capture-plan.md`.

The supported one-cable topology is wireless ADB from Linux to Android, with the only USB/OTG cable between Android and the sensor. The plan now states that Linux `usbmon` cannot observe the separate phone-to-sensor USB bus and that `adb logcat` may not expose raw bytes in a release build.

Validation result:

```text
27 tests passed in 0.02 seconds
Python bytecode compilation succeeded
60 response AM types and 18 read-only operations passed consistency checks
```

No serial port was opened, no sensor was connected by this audit, and no application or custom packet was transmitted.

### 2026-07-15 — Physical sensor re-enumerated on Linux

Status: hardware confirmed; serial access pending local permission

The connected sensor interface was observed without opening the serial port:

```text
USB ID:       10c4:ea60
USB device:   Silicon Labs CP210x UART Bridge
driver:       cp210x
port:         /dev/ttyUSB0
stable link:  /dev/serial/by-id/usb-Silicon_Labs_CP2102N_USB_to_UART_Bridge_Controller_d2f9787d759ced118acf026ce259fb3e-if00-port0
permissions:  root:dialout, mode 0660
```

The current `warmond` login is not a member of `dialout`, no per-user ACL is present, and non-interactive sudo is unavailable. ModemManager is active but was not holding the port at inspection time. Serial opening and receive-only listening are therefore waiting for the operator to grant temporary access and, preferably, stop ModemManager for the controlled session.

No serial port was opened and no protocol bytes were transmitted.

### 2026-07-15 — First independent Linux read-only session completed

Status: completed successfully on the physical G6 sensor

After the operator stopped ModemManager and granted a temporary ACL, the stable CP2102N port was opened at 115200 8N1 with flow control, DTR, and RTS disabled. A five-second receive-only listen produced zero bytes, confirming that the sensor waits for requests.

Physical identity confirmed:

```text
model:          LS-G6-TIL90-I / LS_G6_INC360
product code:   0x4E
node/serial ID: 101677 / 0x18D2D
firmware:       2.81
firmware build: 2023-11-29T10:03:02Z
```

The response header began with `0x41`, proving that the low nibble of header byte 0 supplies the upper node-ID bits on this physical G6. DLE framing and the active parser's 20-bit node-ID interpretation are therefore hardware-confirmed.

Successful read-only results:

- health: battery 3.35 V, temperature 27 °C, uptime 12,823 seconds;
- node and extended information;
- live reading after 9.65 seconds: X -2.4473°, Y 2.8581°, Z 86.2360°, temperature 27.8 °C, error code 0;
- sampling interval: 300 seconds;
- calibration timestamp and six coefficients;
- stored-data interval: oldest `1`, newest `1784111660`;
- normal G6 channel configuration `0x9A`: X, Y, and Z enabled.

Product routing correction:

- request `00 9B` returned `CONFIG_NOT_PRESENT` because that channel/alarm path is not present on normal product `0x4E`;
- request `00 9A` returned the correct normal INC360/G6 channel configuration;
- Bluetooth configuration `00 A5` returned `INVALID_INPUT_PARAM` on this device/firmware and must not be described as hardware-supported.

The read-only registry was expanded to 19 operations, `decode_inc360_channel_config()` was added, and exact UART frames were preserved in `captures/reference_sessions/2026-07-15T103257Z/`. Real frames are now regression fixtures in `tests/test_hardware_capture_20260715.py`.

No configuration value was changed. No time, reset, reboot, bootloader, factory-reset, or firmware command was sent.

### 2026-07-15 — Read-only CLI and physical radio audit completed

Status: completed for the current safe scope

Implemented `tools/til90_cli.py`, supporting automatic CP2102N discovery, explicit port selection, JSON output, exact TX/RX evidence, repeated queries, grouped reads, response-code reporting, and protected `0600` output files. Both module and script invocation are supported. The CLI registry contains only allowlisted read requests and deliberately has no write, reset, reboot, firmware, coverage-test, or factory command.

Implemented and hardware-validated decoders for LoRa general settings, address, uplink/downlink channel tables, slot time, network ID, and join configuration.

Physical radio results:

```text
radio enabled: false
network ID:    0
LoRa address:  81890605 / 0x04E18D2D
DevEUI:        0000000000000000
AppEUI:        0000000000000000
SF / TX power: 9 / 20
slot time:     300 seconds
uplink:        902.3–903.7 MHz, 8 enabled channels
downlink:      923.3–927.5 MHz, 8 enabled channels
```

The sensor is therefore not currently configured for an active gateway network. Static analysis also established that no read response returns the Edge network password. The Android app stores the operator-entered password encrypted in SharedPreferences and uses it only in authentication/configuration write commands. A LoRa node is not associated with one gateway like a Wi-Fi client; specific gateway IDs require backend coverage-test results, while the direct link-check response exposes only margin and gateway count.

The radio coverage test was not run because it actively transmits and can interact with gateway/backend state.

Three repeated stationary live reads all succeeded with sequence numbers 92–94 and error code zero. Observed angle ranges were X 0.0011°, Y 0.0019°, and Z 0.0014°.

Created or updated:

- `tools/til90_cli.py`;
- LoRa decoders in `tools/packet_parser/messages.py`;
- `docs/cli-usage.md`;
- `docs/radio.md`;
- `docs/testing-plan.md`;
- real radio and repeated-reading capture files;
- CLI, error-path, LoRa, and hardware regression tests.

Validation result:

```text
39 tests passed in 0.04 seconds
Python bytecode compilation succeeded
Both CLI invocation styles passed
```

No persistent node setting was changed and no active radio test was performed.

### 2026-07-15 — Local browser console and guarded backup/restore completed

Status: implemented, software-tested, and sampling restore hardware-validated

Implemented a local Python/FastAPI service and dependency-free browser interface. The service binds to loopback and serializes access to the USB port. The browser supports identity, status, live measurements with an X/Y/Z chart, configuration/radio inspection, exact protocol evidence, checksummed JSON backup, backup validation, restore diff preview, and guarded restore.

Backup/restore controls now include:

- canonical SHA-256 checksum and schema validation;
- node ID, product code, serial number, and firmware-build matching;
- a fresh pre-write backup and field-level diff;
- complete rejection when any unsupported field differs;
- exact `RESTORE <node-id>` confirmation;
- command acknowledgement, immediate readback, and full post-backup comparison;
- reverse-order rollback after a write or verification failure;
- no arbitrary-byte transmission endpoint;
- writes disabled by default and exposed only with `--enable-writes`.

Physical validation changed only the sampling interval:

```text
300 -> 301: request 82 00 01 2D, response 0000 OK, readback 301
301 -> 300: request 82 00 01 2C, response 0000 OK, readback 300
```

At this stage the final sensor state was sampling `300` seconds, and channel serialization (`9A + flags`) was synthetic-only. This limitation was superseded later on 2026-07-15 by the recorded reversible Z-axis trial. Calibration, radio, identity, factory-reset, bootloader, and firmware writes remain blocked.

Created or updated:

- `tools/config_backup.py`;
- `tools/device_service.py`;
- `tools/web_service.py`;
- `web/index.html`, `web/app.js`, and `web/styles.css`;
- backup, restore, service, HTTP-security, and frontend tests;
- `docs/web-app.md`;
- `captures/reference_sessions/2026-07-15T103257Z/restore-validation.md`;
- repository indexes and safety documentation.

Validation result:

```text
50 tests passed
Python bytecode compilation succeeded
Physical changed-value sampling restore succeeded in both directions
Real HTTP backup creation and checksum validation succeeded through the running service
```

### 2026-07-15 — Android feature parity and sampling-period semantics mapped

Status: completed by static analysis and existing physical captures

Reviewed the Android setup wizard, INC360 node implementation, base node operations, radio-region capacity rules, local-sampling screen, and main maintenance entry points.

Confirmed three distinct measurement modes:

- on-demand request `02` starts a fresh measurement and returns in approximately 9–10 seconds on the physical G6;
- persistent configuration AM `0x82` stored 300 seconds at this pre-programming capture (later changed to 3600 seconds by the official workflow);
- the temporary local-sampling diagnostic mode accepts a duration and period and suppresses radio messages while active.

The Android library declares a 10-second standalone minimum for `LS_G6_INC360`. In a configured radio network it uses the larger of that hardware minimum and the radio capacity slot. Default region rules use 7.5 seconds per node and network-size buckets `4, 8, 40, 240, 480, 2000`. The 240-node bucket therefore produces `7.5 × 240 = 1800` seconds, explaining the wizard's 30-minute minimum for network sizes from 41 through 240.

Created `docs/android-feature-parity.md` with:

- a direct-USB versus backend-dependent feature matrix;
- current browser coverage and write-safety boundaries;
- product-specific exclusions for the normal G6 INC360;
- a staged implementation roadmap toward Android parity;
- a known UI issue: the current three-second host timer can queue on-demand requests that each take approximately ten seconds.

No sensor communication occurred during this analysis and no files in the browser implementation were changed.

### 2026-07-15 — Ten-node sampling limit corrected and gateway options assessed

Status: completed by static analysis and official product-document review

The operator reported that the Android application still disables every reporting period below 30 minutes with only ten physical sensors. This disproves network population alone as a sufficient explanation.

Confirmed from Java and smali:

- the application does not discover the active sensor population for its minimum-period calculation;
- it passes the wizard-entered value stored as `PREF_NETWORK_SIZE`;
- the `Set last configuration` workflow reloads that stored value from SharedPreferences;
- the adapter receives one minimum and disables every listed period below it;
- an entered Edge/FCC size of 10 should round to bucket 40 and calculate `40 × 7.5 = 300` seconds, not 1800 seconds.

The remaining 30-minute hypotheses are a stale stored size of 240, a different radio profile/capacity table, a version/server constraint, or a difference between the displayed installed count and the value passed to the library.

Gateway assessment:

- the pre-programming physical node MAC value 2 mapped to embedded `US915_V1`, not LoRaWAN;
- the Edge path uses numeric network ID/password authentication;
- the Cloud path uses LoRaWAN profiles and a CMT network token;
- Worldsensing publicly documents tested third-party LoRaWAN gateway compatibility with CMT Cloud;
- a generic LoRaWAN gateway is therefore realistic after supported node provisioning, while a complete CMT Edge replacement requires substantially more protocol and backend reverse engineering;
- current captured 902.3–903.7 MHz uplinks must not be enabled by this research tooling until the unit's original region/profile and applicable authorization are confirmed.

Created `docs/gateway-feasibility.md` and corrected `docs/android-feature-parity.md`. No sensor or gateway communication occurred.

### 2026-07-15 — Ten-sensor wired Linux topology assessed

Status: architecture documented; implementation and multi-sensor hardware validation pending

Confirmed that a single Linux computer can realistically service ten independently cabled TIL90 sensors. CP2102N traffic is negligible relative to its USB full-speed link; the observed approximately ten-second sensor acquisition is the expected batch bottleneck. Parallel per-port transactions should therefore return a ten-sensor batch in approximately 10–12 seconds instead of approximately 100 seconds for sequential reads, subject to physical validation.

Linux udev inspection of the already enumerated adapter confirmed a unique CP2102N serial number and a physical USB path. The design requires every port to be mapped by sensor node ID, adapter serial and physical path, with identity re-read after every connection so cable swaps cannot silently relabel locations.

Created `docs/multi-sensor-wired.md` with:

- powered-hub and long-distance cabling guidance;
- concurrent multi-device service architecture;
- node-ID/location safety checks and duplicate-serial handling;
- partial-failure, timestamping, storage and browser requirements;
- staged two-to-ten-sensor validation and 24-hour stability tests.

The current CLI and browser remain single-port implementations. No serial port was opened, no sensor request was transmitted, and no destructive operation occurred. Only read-only Linux udev metadata was inspected.

### 2026-07-15 — 50–100 metre railway cabling options reviewed

Status: deployment guidance documented; site survey and hardware selection pending

Official USB-IF information confirms that passive full-speed USB cable assemblies are limited to approximately 2–5 metres depending on connector type. A 50–100 m passive USB cable is therefore not a supported topology.

Commercial active extenders demonstrate that USB can be transported over specified Cat5e/6 systems for 100 m. The reviewed Icron platform also specifies 500 m over multimode fibre and up to 10 km over single-mode fibre. These are product-system capabilities, not evidence that passive adapters or arbitrary Ethernet switches can extend USB.

For sensors distributed beside railway infrastructure, the recommended architecture is a short USB connection to a protected local Linux collector at each sensor or cluster, followed by an industrial fibre/Ethernet backbone to the central service. Fibre avoids an electrically continuous long copper path; local buffering also limits common-mode failures and preserves measurements during a network interruption.

Expanded `docs/multi-sensor-wired.md` with the distance comparison, proposed distributed-collector topology, and railway EMC, surge, grounding, enclosure and power considerations. Final equipment selection requires a site survey and applicable railway/environmental compliance review. No sensor or serial communication occurred and no hardware state changed.

### 2026-07-15 — Raspberry Pi Wi-Fi collector option assessed

Status: architecture and indicative cost tiers documented; prototype pending

Confirmed that a Raspberry Pi can serve as the local Linux collector: one short USB link connects the TIL90, one local power feed supplies the collector, and measurements are forwarded over Wi-Fi. The proposed service buffers timestamped readings locally during network outages and later forwards them to the central browser service using authenticated transport.

Recorded current manufacturer base prices and boundaries:

- Raspberry Pi Zero 2 W: USD 15, suitable for a protected single-sensor prototype;
- Raspberry Pi 4: from USD 35, with more USB ports and dual-band Wi-Fi but still requiring protected power, storage and enclosure;
- Revolution Pi Core: from EUR 266 excluding tax;
- Wi-Fi-equipped Revolution Pi Connect configurations: approximately EUR 515–558 excluding tax.

These are computer-only prices, not installed railway-point costs. Enclosure, storage, industrial power conversion, cable glands, surge/grounding provisions and network equipment can make a field point cost several hundred euros or more. Wi-Fi range cannot be inferred from the board specification and requires a site survey at the installed antenna position, especially when metal cabinets, trains and trackside obstructions are present.

Expanded `docs/multi-sensor-wired.md` with the Wi-Fi topology, price tiers, offline-buffer behavior, field reliability controls and installation-cost boundary. No sensor communication or hardware mutation occurred.

### 2026-07-15 — Local RF and gateway-to-site-computer architectures clarified

Status: theoretical paths documented; exact site gateway identification pending

Established that an antenna alone cannot turn the existing industrial computer into a LoRa gateway. A compatible regional antenna, RF front end, LoRa transceiver or multi-channel concentrator, radio driver/packet forwarder, network server, authentication material and payload decoder are separate required layers. An SDR can support receive-only research but does not by itself provide a reliable bidirectional sensor network.

At this pre-programming stage, the reference TIL90 was radio-disabled in proprietary embedded `US915_V1`, not LoRaWAN. It therefore could not be assumed to work with a generic LoRaWAN concentrator. The later official configuration changed it to embedded `EU868_V1`, which remains proprietary rather than LoRaWAN. A fully independent network requires either supported regional LoRaWAN reprovisioning with legitimate keys and a decoder, or substantially harder recovery of the proprietary Edge radio protocol.

Official product information confirms a simpler cloud-independent route: CMT Edge stores collected data in the gateway, operates without internet, is accessible through the local Ethernet network, and exports through MQTT, FTP/FTPS, Modbus TCP and APIs. An existing industrial computer can ingest one of these supported interfaces and forward results to the customer's server.

The 4G Rugged Gateway lists USB-C as local access and power, but no reviewed public specification identifies it as a raw measurement stream. Ethernet and a documented CMT Edge export are therefore the preferred integration interface. Updated `docs/gateway-feasibility.md`. No device, gateway or radio communication occurred.

### 2026-07-15 — Active/write validation gates defined

Status: execution plan completed; physical trials pending explicit per-operation approval

Re-audited the Android INC360 implementation and corrected the calibration boundary. The official calibration activity only calls `getCalibrationParameters()`, and `Inc360Node` provides `requestCalibration()` but no calibration write method. Calibration coefficients must therefore remain read-only; changing them requires separate authorized factory/service protocol research and a physical metrology procedure.

Created `docs/write-validation-gates.md` with common transaction safeguards and a staged order:

1. bounded read-only history recovery;
2. reboot with automatic reconnect and health verification;
3. identical-value and reversible one-axis configuration trials;
4. temporary local sampling with a mandatory stop watchdog;
5. bounded clock correction;
6. node-ID testing on a spare sensor;
7. radio configuration only with a correct regional gateway/profile and credentials;
8. calibration kept as separate, currently unsupported research.

Updated `docs/android-feature-parity.md`, `docs/testing-plan.md` and the documentation index. The first four stages require the connected sensor, uninterrupted USB/power, serial access and explicit approval before active/write trials. Radio additionally requires a suitable gateway and credentials; node-ID work should use a spare sensor. No sensor command was transmitted and no hardware state changed.

### 2026-07-15 — European 915 MHz warning corrected

Status: previous overbroad wording corrected; recovered-unit provenance remains unknown

Corrected the earlier shorthand statement that `US915_V1` cannot be used in Europe. Current EU spectrum decisions provide harmonised technical conditions for some networked short-range/IoT operation within portions of 915–921 MHz, including a 915–919.4 MHz core. The number `915` or an APK enum name is therefore not, by itself, a legal conclusion.

The physical evidence is narrower: this recovered unit currently stores embedded `US915_V1`, enabled uplink channels 902.3–903.7 MHz, and `radio disabled`. This does not describe other deployed sensors and does not reveal whether the unit came from another region, retained a restored/default profile, was a regional variant, or operated under a project-specific authorization.

Updated `docs/gateway-feasibility.md`, `docs/write-validation-gates.md` and earlier roadmap wording. Future radio work must first record the unit's provenance, exact country/site, gateway profile and authorization, and compare a known working sensor. No radio or serial communication occurred.

### 2026-07-15 — Official post-repair gateway configuration captured

Status: read-only capture complete and repeated; no independent write performed

After the operator configured repaired node `101677` for an existing gateway with the official workflow, the independent Linux CLI captured all supported read-only groups and repeated the radio/configuration groups. Both reads agreed apart from response sequence numbers.

Confirmed transition:

- MAC `US915_V1` byte 2 to embedded `EU868_V1` byte 0;
- radio disabled to enabled, ETSI disabled to enabled;
- SF/TX power `9/20` to `11/14`;
- eight 902.3–903.7 MHz uplinks to six enabled 868.1–869.525 MHz uplinks;
- sampling 300 to 3600 seconds and radio slot 300 to 3000 seconds;
- network ID 0 to 27484, with non-zero DevEUI and AppEUI.

Node identity, firmware 2.81, LoRa address, calibration coefficients and enabled X/Y/Z axes remained unchanged. This confirms the operator's report that the earlier disabled US915/zero-network state was lost or non-operational repair configuration rather than the intended site profile.

The response still stores the earlier 923.3–927.5 MHz downlink table and an RX2 value decoded as 1020 MHz, while `use_custom_rx2=false`. Android's embedded-Europe region configuration supplies only the six 868 MHz channels. These retained fields are documented as operationally unconfirmed and must not be presented as active frequencies without gateway/on-air evidence.

Created `captures/reference_sessions/2026-07-15T161221Z-post-gateway-config/` with mode-0600 JSON evidence, repeated reads, a validated checksummed `til90-config-backup/v1` snapshot, session metadata and SHA-256 hashes. Added a regression test for the new physical frames and updated current radio/protocol/gateway documentation. Only USB read requests were transmitted; no configuration, link-check, coverage, reboot, reset, bootloader or firmware command was sent by the independent tooling.

### 2026-07-15 — Original Android radio profiles inventoried

Status: complete static inventory; current profile hardware-matched

Recovered all 20 profiles from `RadioRegionsConfigs`: 15 embedded/Edge and 5 LoRaWAN/Cloud. Preserved MAC family, band, SF limits/default, TX power, ETSI/ADR settings, 500 kHz flag, uplink groups, downlinks and TTI plan names in `analysis/protocol/radio_profiles.json`.

The physical node's repeated radio read matches the `EUROPE` Edge profile exactly: `EU868_V1`, SF11, 14 dBm, ETSI/ADR enabled and six uplinks from 868.1 through 869.525 MHz. Gateway identity, network password and reporting parameters are not profile constants.

Created `docs/radio-profiles.md` and `tests/test_radio_profiles.py`. No sensor command was sent for the static inventory.

### 2026-07-15 — Bounded physical history recovery completed

Status: completed without configuration change

Requested epochs `1784125053..1784132253` with strict 7200-second, 25-record, 65536-byte and 40-second limits. Node `101677` returned 18 records in 608 received bytes followed by response `0x0080`: 12 regular INC360 readings and 6 health messages.

All wrappers used capture ID 5, outer and inner sequence numbers matched, and the end endpoint was inclusive. The history proves that direct health/live requests can be stored alongside scheduled readings and shows the transition from the previous 300-second schedule to the official 3600-second schedule.

Evidence: `captures/reference_sessions/2026-07-15T162317Z-extended-validation/history-last-two-hours.json`. Only a bounded read request was transmitted.

### 2026-07-15 — Reboot and channel rollback physically validated

Status: completed and restored

Recovered the exact Android reboot request body `09` and implemented a separately confirmed maintenance command. The physical reboot produced health at uptime 1 after pre-reboot uptime 45; node ID, firmware and every semantic configuration field remained unchanged.

Channel validation then sent identical state `9A 07`, temporarily disabled Z with `9A 03`, confirmed readback and received a live packet containing X and Y only. The mandatory restore `9A 07` succeeded, all three axes read back enabled, and the complete configuration diff was empty.

Created `tools/maintenance_cli.py`, `tests/test_maintenance_cli.py` and `docs/maintenance-cli.md`. Evidence is in `reboot-validation.json` and `channel-validation.json` in the extended-validation capture directory. No radio, calibration, identity, time, reset, bootloader or firmware write occurred.

### 2026-07-15 — Local sampling boundary and stationary series tested

Status: normal live series complete; continuous local mode unsupported on tested firmware path

The exact common Android local-sampling body for duration 6 seconds and period 2 seconds was `15 00 02 00 00 00 20 00 00 60`. G6 INC360 firmware 2.81 rejected it with `INVALID_SIZE`; a post-trial full backup proved no configuration change. Alternate packet-size variants were not guessed or transmitted.

Ten ordinary one-shot live measurements all succeeded with mean latency 9.60 seconds. With the sensor stationary, angle ranges were X 0.0558°, Y 0.0373° and Z 0.0530°; temperature ranged 27.9–28.3 °C. Sensor timestamps were about 12 seconds behind receive time, but the measurement itself consumed about 9.6 seconds, so no clock write is justified from this short trial.

Evidence: `local-sampling-rejection.json`, `live-stability-10.json` and `final-configuration.json`. The local-mode request was rejected before activation; ordinary measurement requests are read-only.

### 2026-07-15 — Gateway slot write validated and web console rebuilt

Status: completed, restored and tested

Recovered the original application's exact gateway radio-slot serializer as AM `0x90` plus an unsigned 16-bit big-endian seconds value. The physical trial sent the identical 3000-second value, changed it to 3001, verified ACK/readback, restored 3000 and confirmed an empty full-configuration diff. This validates the radio-slot field separately from the ordinary 3600-second measurement interval; it does not validate frequency, password, network-ID or RF delivery changes.

Rebuilt the local web application as an English operator console. Raw JSON is no longer the normal display. It now provides readable device/status cards, non-overlapping live measurements, graph and table views, configuration presets, separate measurement and gateway-slot controls, axis selection, all 20 original radio profiles in view-only mode, bounded historical recovery with CSV export, checksummed backup/restore, guarded reboot and a collapsed UART evidence area. A follow-up language audit removed all Cyrillic strings from the maintained web, tools, tests and documentation paths. The obsolete mixed-language `Command.md` log and `StartCommands.md` note were replaced with concise current English operator references.

Added expiring server-side configuration previews so the browser never needs to edit backup JSON. Applying configuration still requires `--enable-writes`, exact node-ID confirmation, fresh identity/configuration reads, an ACK, immediate readback, a complete post-backup comparison and rollback. Full radio/network programming remains blocked.

The complete web write path was then exercised against the physical node: the API preview exposed only `radio_slot_time`, applied `3000 → 3001`, verified the new value, previewed the reverse operation and restored 3000. Final reads confirmed sampling 3600 and X/Y/Z enabled. This separately verifies that the browser's preview/apply layer uses the same guarded hardware path successfully.

Created hardware evidence `gateway-slot-validation.json`; updated `tools/config_backup.py`, `tools/device_service.py`, `tools/web_service.py`, `web/index.html`, `web/app.js`, `web/styles.css`, API/frontend tests and operator documentation. The final sensor state remained sampling 3600 seconds, gateway slot 3000 seconds and X/Y/Z enabled.

### 2026-07-15 — English-only repository policy enforced

Status: completed and automated

Added root `AGENTS.md` as a persistent repository-wide instruction: all project-authored code identifiers, comments, docstrings, UI strings, API messages, logs, tests, filenames, documentation, registries and reports must be English. The policy applies even when requests are written in another language.

Added `tests/test_language_policy.py` to scan every maintained root document plus `docs/`, `tools/`, `tests/`, `web/`, `analysis/protocol/` and `analysis/firmware/` for Cyrillic content and non-ASCII authored paths. Immutable decompiler output, original packages and raw captures remain explicit evidence exclusions and must not be rewritten.

The repository language audit passed. No sensor communication or hardware state change occurred.

## Current deliverables

| Deliverable | Status | Last update |
|---|---|---|
| `docs/frame-format-draft.md` | Hardware-confirmed on physical G6 | 2026-07-15 |
| `analysis/protocol/frame_fields.csv` | Complete for the known framing/header fields | 2026-07-15 |
| `tools/packet_parser/frame.py` | Implemented and tested | 2026-07-15 |
| `tests/test_frame_parser.py` | 9 passing tests | 2026-07-15 |
| `docs/configuration-ids.md` | All 27 configuration IDs recovered | 2026-07-15 |
| `docs/message-types.md` | 60 dispatcher types plus TIL90 paths documented | 2026-07-15 |
| `analysis/protocol/message_registry.csv` | Complete dispatcher registry | 2026-07-15 |
| `tests/test_message_registry.py` | 4 passing registry tests | 2026-07-15 |
| `tools/packet_parser/messages.py` | TIL90 read-only and history helpers implemented | 2026-07-15 |
| `tests/` | 79 passing protocol, firmware transport, radio authentication, CLI, monitoring, recovery, alerts, history, USB, backup/restore, web, language-policy, and consistency tests | 2026-07-15 |
| `docs/read-only-message-formats.md` | TIL90 read-only payload layouts documented | 2026-07-15 |
| `docs/protocol.md` | Consolidated static protocol completed | 2026-07-15 |
| `docs/history-protocol.md` | Bounded recovery hardware-confirmed | 2026-07-15 |
| `analysis/protocol/radio_profiles.json` | All 20 original Android profiles inventoried | 2026-07-15 |
| `tools/maintenance_cli.py` | Reboot, channel and gateway-slot rollback hardware-confirmed | 2026-07-15 |
| `analysis/protocol/request_response_pairs.csv` | 19 read-only operations registered | 2026-07-15 |
| `analysis/firmware/inventory.csv` | 15 firmware-directory files hashed and mapped | 2026-07-15 |
| `docs/passive-capture-plan.md` | Hardware-validation handoff ready | 2026-07-15 |
| `docs/multi-sensor-wired.md` | Ten-sensor wired architecture documented; implementation pending | 2026-07-15 |
| `docs/write-validation-gates.md` | Active/write prerequisites and staged validation order documented | 2026-07-15 |
| Direct Linux reference capture | Completed for core G6 reads | 2026-07-15 |
| Read-only serial CLI | Implemented and hardware-tested | 2026-07-15 |
| Local browser console | Readable operator UI, configuration, history, backup and reboot implemented/tested | 2026-07-15 |
| Local persistent monitoring and alerts | SQLite/WAL storage, retention, local rules and lifecycle implemented/tested | 2026-07-15 |
| Advanced history recovery | Chunked, durable, resumable and deduplicated importer implemented/tested | 2026-07-15 |
| USB reliability | Stable by-id selection, diagnostics, udev template and read reconnect implemented/tested | 2026-07-15 |
| Read-only recovery assessment | APK-derived USB/protocol/configuration decision tree implemented and hardware-tested | 2026-07-15 |
| Checksummed configuration backup | Implemented and hardware-tested | 2026-07-15 |
| Sampling restore | Changed-value write/readback/restore hardware-confirmed | 2026-07-15 |
| Channel restore | Changed-value write/readback/rollback hardware-confirmed | 2026-07-15 |
| Gateway radio-slot restore | `3000 → 3001 → 3000` hardware-confirmed | 2026-07-15 |
| Embedded radio/network restore | Factory-reset restore and gateway credential replacement hardware-confirmed | 2026-07-15 |
| Factory reset and firmware 2.81 recovery | Hardware-confirmed with final zero-difference backup | 2026-07-15 |
| Calibration write | Blocked; no official INC360 writer or metrology procedure found | 2026-07-15 |

## Next work

### Phase A — Complete the static message registry

Status: completed from static evidence

The 60-type dispatcher registry, configuration IDs, read-only request/response pairs, historical wrappers, and TIL90 payload decoders are complete. Sequence-number semantics require real captures.

### Phase B — Analyze TIL90 read-only messages

Status: completed from static evidence

Node health, information, hardware, live readings, sampling, calibration, normal G6 channels, radio configuration, and stored interval are hardware-confirmed. Alarm/Bluetooth behavior and history wrapping are statically traced, with device response codes recorded where applicable.

### Phase C — Official-application reference capture

Status: optional comparison; direct Linux validation completed the core protocol gates

1. Capture official-application traffic without sending custom packets.
2. Validate DLE framing against real traffic.
3. Confirm the real node-ID width and upper-nibble behavior.
4. Confirm request/response AM types and sequence-number behavior.
5. Store raw, timestamped captures without omitting bytes.

### Phase D — Independent read-only client

Status: read client, persistent monitoring, local alerts, and resumable history implemented; long-duration physical validation remains

Implement device detection, serial listening, node identification, status reads, and live measurements. Write and destructive commands must remain disabled by default.

## Unresolved questions

- Are any checksums or CRCs embedded in individual message payloads?
- How is the one-byte response sequence number generated and matched?
- Do displayed live values confirm the statically recovered TIL90 scale factors?
- How do capture ID and sequence number roll over during larger historical recovery?
- Does stored-data oldest timestamp `1` mean that no historical records are currently stored?
- Why does Bluetooth configuration return `INVALID_INPUT_PARAM` on firmware 2.81?

### 2026-07-15 — Persistent monitoring, local alerts, resumable history, and USB reliability completed

Status: implementation and automated validation complete; safe physical API read complete

Implemented a persistent SQLite/WAL data layer for measurements, health records, settings, alert state and history-job progress. Background monitoring is disabled by default and exposes configurable measurement/health intervals and retention. Manual and automatic reads feed the same deduplicated store.

Added local absolute-axis, per-axis rate, low-battery, sensor-error and missing-data rules. Each node/rule has at most one open event; repeated observations update it, a clear condition resolves it, and acknowledgement is recorded separately from condition state.

Replaced large browser-only history handling with durable bounded jobs. Long ranges are split into independently completed chunks, progress is committed after the `0x0080` end marker, failures pause without advancing the cursor, and resume repeats only the uncommitted chunk. Unique node/timestamp keys suppress duplicate imports, while received/imported/duplicate counters remain visible. Stored measurements can be filtered and exported as CSV.

Hardened Linux USB handling by preferring the matching `/dev/serial/by-id` alias and reopening idempotent reads after bounded OS/serial failures. Writes are not automatically retried. Added readable diagnostics for resolved path, permissions, owner/group, ModemManager, and reconnect counters, plus `config/99-til90-cp210x.rules`. The connected adapter independently reported vendor/product `10c4:ea60`, matching the template.

Expanded the English web console with Monitoring & Alerts, history-job progress/Pause/Resume, stored measurement tables, CSV export, and USB diagnostics. Added `docs/monitoring-and-alerts.md` and updated operator, CLI, history, test, index and root documentation.

Automated validation now reports 70 passing tests, successful Python compilation and valid JavaScript syntax. A localhost API validation performed one read-only health request against physical node `101677`: status `ok`, one health row stored in an in-memory database, stable by-id resolution confirmed, USB read/write access available and ModemManager inactive. A second physical smoke test enabled background monitoring with a ten-second measurement setting, stored one live sample and one health row, produced no alert or error, and stopped cleanly. Both databases were memory-only. No configuration, radio, reboot, reset, bootloader or firmware write was transmitted.

### 2026-07-15 — Smartphone connection and non-destructive recovery path documented

Status: APK analysis, implementation, documentation and physical read-only validation complete

Traced the original Android 2.17.1 connection path from manifest/device filter through USB permission, CP2102N open, 115200 8N1 configuration, receive callback, timed identification retries, product/firmware classification and the post-identification LoRa-address check. The app accepts USB IDs `10c4:ea60`; permission denial, port-open failure and protocol timeout are distinct states. Only LoRa address `0xFFFFFFFF` invokes its explicit factory-reset-required UI.

Recovered the factory-reset transaction statically and confirmed its decompiler-damaged constructor in smali: AM `0x08` plus constant `0x75B544A2`, or unframed payload `08 75 B5 44 A2`. The app requires a success response, then a health message without assuming the previous node ID. This command remains documentation-only because radio credentials, complete restore and failure recovery are not yet proven. The APK's separate bootloader/type-detection/firmware-flash workflow remains blocked for the same reason.

Added `tools/recovery_check.py` and a readable Maintenance-page action that checks USB presence/access, health response, identity, every backup read group, sampling/axes, radio plausibility, power, reconnect state and the exact factory-reset sentinel without writing. Added `docs/smartphone-connection-recovery.md` with phone/OTG/permission/power troubleshooting and a phone-versus-Linux decision table. Added `docs/remaining-work.md` to preserve endurance, disconnect, multi-sensor, physical metrology, clock, large-history, gateway, reporting and productization work.

The physical read-only assessment passed every layer on node `101677`: firmware 2.81, sampling 3600 seconds, X/Y/Z enabled, radio enabled, address `81890605`, network ID `27484`, six active uplinks, no reconnect and no factory-reset sentinel. No reboot, reset, configuration write, bootloader or firmware packet was sent. Automated validation increased to 72 passing tests; all frontend DOM references and JavaScript syntax passed.

### 2026-07-15 — Factory reset, full restore, and firmware recovery validated

Status: completed on physical node 101677

Created a checksummed full backup before destructive work and preserved the gateway password separately with mode `0600`. Recovered the exact G6 firmware workflow from the Android client: send reboot `09`, wait one second, write bootloader password `worldsensing`, wait for XMODEM `C`, transfer 128-byte XMODEM-CRC blocks with the two deliberate initial CRC-probe retries used by the APK, then finish with acknowledged EOT.

The exact APK-mapped `LSG_TIL90_v2_81.bin` image was validated at 124288 bytes with SHA-256 `9dba6261df792649b0cebd0db86f1aa459bb93209b8783dad2da020a5f0b227f`. A first handshake trial safely timed out before block transmission because it waited for `C` too early. After correcting the ordering, the physical reflash completed all 971 blocks with exactly two expected retries. The sensor returned as product `0x4E`, firmware 2.81, and the configuration diff was empty.

Sent the APK factory-reset body `08 75 B5 44 A2`. The node acknowledged it and returned under the same identity. Reset preserved node ID, firmware, serial/radio address, X/Y/Z flags, and calibration coefficients/timestamp. It changed sampling `3600 → 300`, gateway slot `3000 → 300`, disabled the radio, selected US915_V1 defaults, replaced uplink channels, and cleared network ID and join identity.

Implemented the exact embedded authentication derivation, join identifiers, complete radio payload serializers, and an ordered post-reset restore. An initial replay attempt was rejected as `UNKNOWN_CMD` before changing state; analysis showed that the AM/configuration type is the final byte of the six-byte response header and must be retained in a write. The corrected serializer was regression-tested, then the node accepted and read back radio general, uplink/downlink channels, sampling, slot, axes, join, and authentication operations.

Restored network ID `27484` using a temporary password stored only in the protected capture directory. The original password cannot be read from hardware and was not present in the backup. Reboot verification passed, and an independent final backup had no semantic configuration differences from the pre-reset backup. RF receipt is not claimed without a gateway.

Added guarded firmware, factory-reset, post-reset restore, and separate gateway-credential services/CLI paths. Expanded the English localhost browser with exact-image firmware validation/reinstallation and a combined reset, restore, reboot, and compare workflow. Password fields use secret models, are cleared in the browser after success, and are never returned by the API.

Evidence is under `captures/reference_sessions/2026-07-15T180007Z-reset-firmware-validation/`, including pre/reset/flash/restore/reboot/final backups, session notes, and checksums. Automated validation reports 79 passing tests and valid JavaScript syntax.

### 2026-07-15 — German stakeholder report prepared

Status: completed

Added `reports/localized/TIL90_Project_Report_DE.md`, a deliberately non-technical German summary for colleagues. It explains the project objective, completed sensor and web-console capabilities, physically validated reset/restore and firmware recovery, operational benefits, remaining limitations, and future gateway/multi-sensor opportunities. Added a narrow repository-language exception for explicitly requested localized stakeholder reports; all code, UI, technical documentation, tests, filenames, and roadmap content remain English.

### 2026-07-22 — Docker USB hotplug and automatic web acquisition completed

Status: image and no-hardware runtime smoke validation complete; physical hotplug validation pending sensor connection

Added a Python 3.13 Docker image and hardened Compose deployment. The service binds only to host loopback, drops all Linux capabilities, enables `no-new-privileges`, keeps the root filesystem read-only, persists SQLite under `data/`, and grants ttyUSB major `188` without using privileged mode. A strict Docker context excludes APK archives, extracted/decompiled evidence, captures, runtime databases, and test caches.

Extended the existing serialized monitoring loop with explicit waiting, connecting, connected, and retrying states plus latest sample/health publication. Container startup enables ten-second live reads and sixty-second health reads. The browser polls this state, updates the connection indicator, and renders new X/Y/Z data automatically. The process remains healthy when no CP2102N exists and retries after later hotplug or a serial disconnect.

Added a regression test for absent-to-present USB acquisition and fixed a history-resume race in which a job could already be marked paused while its previous worker was still leaving the finalization path. Automated validation now reports 82 passing tests, successful Python compilation, valid JavaScript syntax, and a valid Compose model.

Updated the Linux udev template to request ModemManager exclusion. Added operator documentation for host UID/GID mapping, dialout access, start/stop/rebuild, persistence, rootless limitations, multiple-device ambiguity, and physical acceptance testing.

Recovered the official application's version-aware node-ID path for documentation. It accepts a 20-bit value on recent firmware, verifies a health response at the new ID, and retains a legacy 16-bit branch. No second application command was found for rewriting serial, product, calibration identity, or a possible manufacturing fallback ID; deeper identity modification remains blocked pending an authorized service path and recovery-safe physical validation.
