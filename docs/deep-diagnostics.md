# Deep read-only diagnostics

Last updated: 2026-07-22

## Purpose

The **Deep diagnostics** browser tab distinguishes an Android connection problem from USB, power, MCU/UART, framing, firmware, configuration, measurement-hardware, and sensor-history failures. It is intended for batch triage of sensors that do not connect to the original phone application.

The suite is read-only. It reports `persistent_writes_sent: 0` and never enters the bootloader, resets, reboots, flashes firmware, or writes configuration. A passive bootloader listen only observes bytes already emitted by the device. It does not send the bootloader password or XMODEM data.

## Test sequence

One run performs these bounded stages:

1. verify CP2102N enumeration, stable path and Linux read/write access;
2. listen for 1.5 seconds without transmitting and count possible XMODEM `C`, NAK, CAN and ACK control-byte hints;
3. send one documented health read while recording received-byte, decoded-frame and framing-error counts;
4. perform five health reads and five node-information reads with individual latency and response status;
5. query every backup configuration family separately so one failure does not hide the remaining results;
6. acquire five live X/Y/Z measurements and inspect timestamps, four-bit sensor error codes, ranges, reported standard deviation and gravity-vector plausibility;
7. inspect recent SQLite health records for an uptime decrease that suggests repeated sensor resets;
8. request at most 200 historical records from a 15-minute sensor-time range and require the normal completion response;
9. compare product, firmware and embedded EUROPE-controlled radio fields with the hardware-tested TIL90 2.81 reference;
10. classify the most likely failure layer and generate next actions.

A healthy physical measurement normally takes approximately ten seconds. Five sequential measurements therefore make a complete healthy run last about one minute. Serial access remains protected by the shared device lock, so background monitoring waits instead of overlapping the diagnostic requests.

## Classifications

The primary classifications are:

- `usb_not_enumerated`;
- `usb_access_denied`;
- `possible_bootloader_mode`;
- `sensor_power_mcu_or_uart`;
- `serial_framing_or_firmware`;
- `unstable_identity`;
- `power_problem`;
- `repeated_sensor_resets`;
- `identity_or_firmware_instability`;
- `configuration_or_firmware_problem`;
- `measurement_hardware_or_firmware`;
- `measurement_plausibility_problem`;
- `history_or_storage_problem`;
- `sensor_responsive_phone_or_app_likely`.

The final classification is diagnostic guidance rather than component-level proof. For example, a quiet CP2102N port can result from sensor power, MCU state, firmware, wiring, or the CP2102N-to-MCU UART path. A low-variation axis while the sensor is stationary is reported as a candidate only; repeat the run while changing physical orientation before calling it a stuck sensor.

## Reports

The latest result remains in web-service memory and can be downloaded from the tab as:

- JSON evidence containing all stages, decoded read results, UART prefix bytes, latencies and recommendations;
- CSV summary containing the classification, step results, every attempted query and recommendations.

The endpoints are token-protected and localhost-only:

```text
POST /api/diagnostics/deep
GET  /api/diagnostics/deep/report.json
GET  /api/diagnostics/deep/report.csv
```

Reports do not contain the saved gateway password because that password is never readable from the sensor and the diagnostic engine does not access browser-local credential storage.

## Physical acceptance result

A complete Docker-hosted run against node `101677`, product `0x4E`, firmware `2.81`, completed in `62.44` seconds and reported `persistent_writes_sent: 0`. The result was `ready` with classification `sensor_responsive_phone_or_app_likely`:

- five of five health reads passed;
- five of five identity reads passed;
- all 13 independently evaluated identity/configuration groups passed;
- five of five X/Y/Z measurements passed with error code zero;
- gravity-vector norms remained approximately one and no angle, noise or stuck-axis warning was produced;
- UART framing decoded normally with zero framing errors;
- passive bootloader status was quiet;
- the bounded history request completed normally with 77 records;
- the embedded EUROPE and TIL90 2.81 reference comparisons passed;
- JSON and CSV downloads were returned by the running container.

This healthy-node result validates the complete diagnostic path and its reference classification. Each damaged-sensor classification still depends on observing the corresponding physical failure condition.

## Recovery boundary

A passive XMODEM control-byte hint is not sufficient product identification and does not authorize a firmware transfer. An unidentified board must not be flashed automatically. When health and identity remain readable, create a checksummed backup before using any separate guarded repair workflow.

If Linux passes repeated health, identity, configuration, measurement and history checks while the phone still fails, investigate Android USB permission, OTG host mode, cable data lines, application state and phone compatibility before changing the sensor.
