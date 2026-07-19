# Validation and Test Plan

Last updated: 2026-07-15

## Completed

- USB enumeration, permissions, exclusive serial open, and DTR/RTS-disabled operation;
- receive-only silence check;
- framing, 20-bit node ID, identity, health, firmware, and hardware reads;
- one real live X/Y/Z measurement;
- sampling, calibration, enabled channels, and stored interval reads;
- all seven safe radio configuration reads;
- synthetic malformed/incomplete/multiple-frame parser cases;
- real-frame regression fixtures;
- CLI allowlist and exact-wire transaction tests;
- checksummed backup schema, corruption detection, device identity matching, and field-level diff tests;
- restore acknowledgement, readback, post-backup comparison, and forced-failure rollback tests;
- localhost Host filtering, session-token enforcement, security headers, and dependency-free frontend tests;
- physical sampling changed-value restore `300 → 301 → 300` with matching readback;
- bounded two-hour history recovery with 18 decoded records and an `0x0080` completion marker;
- reboot with uptime reset `45 → 1`, automatic health recovery and unchanged configuration;
- channel identical write, temporary Z disable, two-axis live response and verified all-axis restore;
- ten stationary live readings with timing and stability statistics;
- exact Android local-sampling packet trial, rejected safely by firmware 2.81 as `INVALID_SIZE`;
- gateway radio-slot changed-value restore `3000 → 3001 → 3000` with ACK, readback and empty final diff;
- readable English web configuration API/UI with preset intervals, history/CSV, profiles and guarded reboot;
- SQLite monitoring with configurable polling and retention, threshold/rate/battery/error/missing-data alerts, and open/resolved/acknowledged lifecycle;
- chunked history jobs with durable cursor, pause/resume, duplicate suppression, progress accounting, and stored CSV export;
- stable by-id resolution, Linux permission/ModemManager diagnostics, and automatic idempotent-read reconnect;
- one physical in-memory monitoring cycle on node 101677: one live sample and one health row stored, no alerts, no error, and clean stop;
- APK-derived read-only recovery classification, including the exact `0xFFFFFFFF` factory-reset sentinel and blocked destructive actions;
- CSV and documentation consistency checks.

## Safe next tests

1. Rotate the sensor through known orientations and validate sign, axis order, and scale against a physical reference.
2. Compare sensor UTC timestamps with the Linux clock over several hours to estimate drift.
3. Wait through at least two 3600-second sampling periods, query the stored-data interval again, then recover only a small bounded interval.
4. Physically disconnect/reconnect during an active monitoring session and confirm automatic reopen, reconnect counter, no duplicate sample, and missing-data alert resolution.
5. Compare the same read values with the official Android display if wireless ADB becomes available.
6. Add a deterministic fake-clock timeout test and fuzz malformed protocol bodies beyond the existing decode-error cases.
7. Investigate local-sampling generation/firmware routing statically; do not probe alternate packet sizes blindly.

The detailed activation order and prerequisites are in `write-validation-gates.md`.

## Tests requiring explicit expansion of scope

- LoRa link check and radio coverage test: actively transmit and may contact configured gateway/backend infrastructure;
- configuring time, Bluetooth, or calibration: writes persistent state and remains unvalidated;
- local high-rate sampling mode: changes runtime behavior and must be checked for restoration semantics;
- interrupted firmware-transfer recovery and upgrade to a newer image;
- end-to-end radio receipt and backend correlation.

These operations must not be added to the read-only CLI. The browser service exposes only its hardware-confirmed allowlist when explicitly launched with `--enable-writes`; it requires identity matching, exact confirmation, before/after snapshots, readback, and recovery verification. The allowlist now includes separate embedded gateway credentials, exact-image firmware 2.81 reinstallation, and the combined factory-reset-and-restore workflow.

## Code-quality gates

For every change:

```bash
/usr/bin/python3 -m pytest -q tests
/usr/bin/python3 -m compileall -q tools tests
```

The machine does not currently provide Ruff or mypy. Python compilation, unit tests, real capture fixtures, allowlist assertions, CSV shape checks, and Markdown consistency checks are the available automated gates.
