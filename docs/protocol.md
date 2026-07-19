# Worldsensing Local Serial Protocol

Last updated: 2026-07-15

This document consolidates static analysis and direct Linux validation. Controlled sampling, axes, radio slot, embedded radio/authentication, reset/recovery, and firmware 2.81 transactions have been restored or verified against complete backups. Calibration, clock, node-ID, arbitrary firmware, and RF receipt remain unvalidated.

## Transport

- CP2102N USB-UART at 115200 8N1 with no flow control.
- Frame start `10 02`; frame end `10 03`.
- Body byte `10` is escaped as `10 10`.
- No length or CRC is added by this UART framing layer.
- Partial frames and multiple frames per USB read are supported.

## Request and response asymmetry

Requests begin with a one-byte AM type followed by request-specific fields. Responses use a six-byte protocol-v2 header followed by response-specific fields. The response header contains version 4, product code, active-parser 20-bit node ID, sequence number, and AM type.

Detailed framing is in `docs/frame-format-draft.md`. The complete response dispatcher is in `analysis/protocol/message_registry.csv`, and confirmed read-only exchanges are in `analysis/protocol/request_response_pairs.csv`.

## Confirmed TIL90 read-only coverage

Static decoders and tests now cover:

- node health and firmware version;
- node serial number and firmware build time;
- extended hardware versions;
- regular TIL90 readings;
- alarm TIL90 readings;
- sampling interval;
- calibration timestamp and coefficients;
- channel and alarm configuration;
- Bluetooth configuration;
- stored-data oldest/newest timestamps;
- historical recovery wrapping and termination.

Direct hardware traffic confirms health, node information, extended information, regular live reading, sampling interval, calibration, normal G6 channel configuration, and stored-data interval. Alarm configuration `0x9B` returned `CONFIG_NOT_PRESENT` on product `0x4E`; normal G6 channels use `0x9A` and reported X/Y/Z enabled. Bluetooth configuration `0xA5` returned `INVALID_INPUT_PARAM` on this firmware.

All seven read-only LoRa configuration responses are implemented and hardware-validated: general settings, address, uplink channels, downlink channels, slot time, network ID, and join parameters. After official post-repair programming, the tested node reports enabled embedded `EU868_V1`, network ID `27484`, provisioned EUIs, and six enabled uplinks from 868.1 through 869.525 MHz. Link check and coverage testing remain excluded because they actively transmit over LoRa.

## Response codes

AM type `0x00` carries a big-endian 16-bit response code:

```text
0x0000 OK
0x0001 INVALID_SIZE
0x0002 INVALID_INPUT_PARAM
0x0003 RESET_UNSUCCESSFUL
0x0004 CONFIG_NOT_PRESENT
0x0005 UNKNOWN_CMD
0x0006 UNSUPPORTED_CMD
0x0007 FAILED_CMD
0x0080 END_OF_RECOVER_DATA
0x0081 END_OF_LORA_COVERAGE_TEST
```

The final two values were recovered from smali; JADX displayed unrelated constants.

## Hardware-validation boundary

The physical device is confirmed as `LS-G6-TIL90-I`, product code `0x4E`, node ID `101677`, firmware `2.81`. The upper node-ID nibble and framing model match the active APK parser. Sampling, axes, radio slot, complete backup-driven radio restoration, embedded authentication, factory reset, reboot, and exact-image firmware recovery have physical ACK/readback or full-backup evidence. Calibration, clock, node-ID, arbitrary firmware, and RF reception remain outside the validated boundary.
