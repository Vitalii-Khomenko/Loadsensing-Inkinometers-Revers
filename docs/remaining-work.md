# Remaining Work Register

Last updated: 2026-07-15

This register preserves work that is useful but not yet complete. Completion claims remain in `ROADMAP.md`; safety prerequisites remain authoritative in `write-validation-gates.md`.

## Safe work without a gateway

| Priority | Work | Current state | Completion evidence required |
|---|---|---|---|
| 1 | Smartphone failure/recovery diagnosis | APK path documented; Linux read-only recovery check implemented | Test several Android failure cases and preserve screenshots/logs |
| 2 | Long-duration monitoring endurance | One physical background cycle passed | 24–72 hour run with database growth, restart, retention, and stale-data results |
| 3 | Physical USB disconnect/reconnect | Synthetic reopen test passed | Disconnect during monitoring and history; verify recovery, counters, dedup, and alert resolution |
| 4 | Multi-sensor service/dashboard | Architecture documented only | Two or more CP2102N devices, explicit node/location mapping, independent schedules and fault isolation |
| 5 | Orientation and scale validation | Stationary series completed | Reference fixture at known angles for sign, axis order, linearity, repeatability, and temperature effects |
| 6 | Clock drift analysis | Short comparison only | Multi-hour UTC comparison; no clock write |
| 7 | Large history endurance | Physical two-hour core and synthetic resume passed | Multi-chunk physical pause/resume, wraparound, dedup, and CSV validation |
| 8 | Protocol robustness | Existing malformed-frame tests pass | Deterministic fake-clock timeouts and broader decoder/property fuzzing |
| 9 | Operational reports | CSV and readable UI available | PDF/printable inspection report, alarm acknowledgement export, and database backup/restore procedure |

## Work requiring a gateway or official project access

- confirm USB/Ethernet services and supported local export on the exact gateway model;
- correlate sensor transmission, gateway receipt, decoded values, timestamps, and sequence/capture IDs;
- validate gateway slot semantics under the real network size and reporting plan;
- determine the Android wizard state that locks shorter sampling choices;
- test link check/coverage only with site authorization and controlled RF logging;
- evaluate a supported local gateway/API path that avoids cloud dependency without bypassing credentials.

## Persistent writes still blocked

- calibration write;
- sensor clock write;
- node ID change;
- upgrade to firmware newer than 2.81, because no newer mapped G6 image is available.

Factory reset, exact-image firmware 2.81 recovery, complete EU868 configuration restoration, and separate embedded gateway network-ID/password replacement are now physically validated. End-to-end RF delivery remains in the gateway-dependent section because USB ACK/readback cannot prove reception.

## Productization beyond the research console

- multi-user authentication and network deployment model;
- encrypted secrets and project/gateway credential storage;
- automatic database backup, disk-space alarm, watchdog, and service packaging;
- remote notifications with delivery acknowledgement;
- tamper-evident audit trail and role-based approval for writes;
- redundancy, health supervision, calibration management, cybersecurity review, and applicable railway/site certification.
