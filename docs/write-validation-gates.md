# Write and Active-Operation Validation Gates

Last updated: 2026-07-15

## Purpose

This document defines what is still required before each recovered active operation can be exposed in the CLI or browser. Knowing that an Android method exists is not sufficient: exact wire serialization, acknowledgement, readback, recovery, automated tests and a bounded physical trial are separate gates.

No operation below becomes generally enabled merely because its physical trial succeeds once. Write access must remain off by default and scoped to one verified node ID.

## Required common controls

Every persistent or disruptive operation requires:

1. a fresh identity/configuration backup and raw TX/RX journal;
2. exact node-ID/product/serial matching immediately before transmission;
3. a command-specific value validator and allowlist;
4. synthetic ACK, rejection, timeout and malformed-response tests;
5. readback verification where the value is readable;
6. a defined rollback or reconnect path;
7. an explicit confirmation containing the target node ID and operation;
8. uninterrupted sensor/USB power for the complete transaction;
9. a final health/configuration read and saved post-operation evidence.

## Operation matrix

| Operation | Current evidence | Required before first physical test | Required equipment/input | Recommended order |
|---|---|---|---|---:|
| Bounded history recovery | Bounded two-hour physical recovery completed: 18 records and `0x0080` end marker | Completed for the tested bounds; larger exports still require pagination policy | Current USB sensor with stored records | 1 |
| Reboot | Exact `09` request, health reconnect, uptime reset and unchanged configuration physically validated | Keep explicit node-ID confirmation and bounded timeout | Current USB sensor; stable power | 2 |
| Enable/disable axes | Identical write, Z disable, two-axis live result and restoration physically validated | Keep writes disabled by default and automatic rollback | Current USB sensor in a stable position | 3 |
| Temporary local sampling | Exact Android start packet was rejected by G6 INC360 firmware 2.81 with `INVALID_SIZE`; configuration remained unchanged | Determine whether another generation/node-specific implementation exists before any new physical variant | Current USB sensor; operator present | 4 |
| Set clock | Android command and post-write health verification recovered | Recover exact timestamp/timezone encoding, compare without writing, constrain maximum correction, verify UTC and history continuity | Current USB sensor; synchronized Linux clock | 5 |
| Change node ID | Android command and new-ID health response flow recovered | Recover exact serializer and valid range, check uniqueness, discover by both old/new ID, provide forced recovery scan and immediate rollback | Prefer a spare/non-production sensor | 6 |
| Full embedded radio configuration | Android flow and serializers recovered; EU868 general/up/down/slot/join/auth restore physically validated | Gateway still required for RF receipt and backend correlation | Correct regional gateway for end-to-end validation | USB configuration complete |
| Change calibration | Read format physically validated; no INC360 calibration writer exists in the reviewed app/library | Identify an authorized factory/service command and calibration procedure; validate mathematics, fixtures, rollback and traceability | Precision reference fixture and preferably a spare sensor | Separate research; not currently ready |
| Factory reset | Exact `08 75 B5 44 A2` reset, default-state inventory, complete restore, reboot, and final zero-difference backup physically validated | Always preserve backup and write-only password; use combined browser workflow where possible | Matching backup, gateway credentials, uninterrupted power | Complete on node 101677 |
| Firmware recovery | Exact APK image/hash and G6 password/XMODEM transport physically validated; configuration remained unchanged | Use only mapped 2.81 image; interrupted-transfer rescue remains a field-service risk | Stable power and exact compatible image | Complete for 2.81 reinstallation |

History recovery is read-only, although it is a streaming active request. It should be implemented first because it increases evidence without changing configuration.

## Per-operation trial rules

### History

- Query the oldest/newest interval first.
- Request no more than a small bounded window around known records.
- Stop on `END_OF_RECOVER_DATA` (`0x0080`) or the 40-second deadline.
- Limit accepted bytes and records so corrupt or unexpected streaming cannot exhaust memory/disk.
- Preserve outer capture ID, response sequence and raw body before decoding.

### Axis configuration

- First send the current `x=true, y=true, z=true` value and confirm no state change.
- Then disable only one nonessential axis for one trial.
- Read configuration and a fresh measurement, restore all three axes, and repeat both reads.
- Do not include this operation in general backup restore until the changed-value rollback is physically proven.

### Temporary local sampling

- The duration and period must have conservative limits.
- The stop command must run after success, error, timeout, UI disconnect and process termination where possible.
- After stopping, verify normal one-shot readings and the unchanged persistent sampling/radio configuration.
- The APK navigation names this primarily as a VW workflow; INC360 support remains a hypothesis until the node accepts the command.

### Clock

- Record Linux UTC, sensor UTC, offset and round-trip latency first.
- Do not set time merely to remove a small harmless offset.
- After a controlled change, verify UTC using a health/timestamp response and check that stored-data ordering remains valid.

### Node ID

- Never choose an ID already present in the deployment.
- Port identity must continue to use CP2102N serial/path during the ID transition.
- The tool must listen for a health response under the new ID and still be able to scan/recover when neither expected ID responds.
- Production node-ID changes should wait until the workflow succeeds twice on a spare sensor.

### Radio

The isolated `0x90 + uint16` gateway-slot value is hardware-validated as `3000 → 3001 → 3000`. The complete embedded EU868 general/uplink/downlink/join/auth sequence was later validated during factory-reset restoration, and separate network-ID/password replacement is implemented. None of these USB results proves RF delivery.

- Do not enable the recovered node's stored 902.3–903.7 MHz uplink plan until its original deployment region/profile and the applicable authorization are confirmed; `US915_V1` is an APK enum label, not by itself a legal determination.
- First obtain the exact gateway model, regional profile and credentials.
- Preserve the validated transaction order: general, uplink, downlink, sampling, slot, axes, join, authentication, then reboot and complete backup comparison.
- Use conducted/shielded RF testing or an authorized field setup for early transmissions.
- A successful USB ACK does not prove RF join, gateway reception or correct backend decoding.

### Calibration correction

The reviewed official Android application exposes calibration parameters as a read-only screen. `Inc360Node` implements `requestCalibration()` and channel writes, but no calibration write method. The six coefficients and timestamp are therefore evidence of readable factory calibration, not evidence of a supported user-write operation.

Changing them would require a recovered service/factory command plus a documented physical calibration procedure and metrology reference. It must not be approximated by constructing an unverified `0x98` write packet.

## What the operator must provide

The first three stages are now physically complete on node `101677`. Further active work needs:

- the current sensor connected directly to Linux;
- temporary serial permission with ModemManager not probing the port;
- stable uninterrupted power/USB connection;
- explicit approval before each bounded active/write trial.

Additional requirements:

- synchronized host time for a clock-setting trial;
- a spare/non-production sensor for node-ID work;
- the correct gateway, region and valid network credentials for radio work;
- an appropriate reference fixture and authorized service information for any calibration research.
