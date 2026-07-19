# TIL90 Local Browser Console

Last updated: 2026-07-15

The browser application is a local interface around the tested Python protocol implementation. It binds to loopback, talks directly to the CP2102N USB serial adapter, and does not need a phone, gateway, cloud account, or internet connection.

## Start

Grant serial access and stop ModemManager as documented in `cli-usage.md`, then run from the repository root:

The service requires Python 3, pyserial, FastAPI, and Uvicorn. Their reproducible version ranges are listed in `requirements.txt`. If they are not already installed, use a virtual environment:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m tools.web_service
```

With the currently prepared system Python, start it directly:

```bash
/usr/bin/python3 -m tools.web_service
```

The default persistent database is `data/til90.sqlite3`. To place it on a separate disk or backup volume:

```bash
/usr/bin/python3 -m tools.web_service --database /path/to/til90.sqlite3
```

Open `http://127.0.0.1:8765/`. To use a specific serial device:

```bash
/usr/bin/python3 -m tools.web_service \
  --serial-port /dev/serial/by-id/usb-Silicon_Labs_CP2102N_USB_to_UART_Bridge_Controller_d2f9787d759ced118acf026ce259fb3e-if00-port0
```

The default mode is read-only. Sampling and enabled-axis restore are exposed only when the service is deliberately started with:

```bash
/usr/bin/python3 -m tools.web_service --enable-writes
```

This switch does not expose arbitrary writes. It enables only physically validated operations with target checks, exact confirmation, readback or post-operation backup comparison, and a defined recovery path.

## Functions

- detect the local serial sensor;
- present identity, health, live tilt, configuration, radio and gateway values as readable English cards instead of raw JSON;
- plot recent X/Y/Z samples and show a measurement table without overlapping the approximately ten-second requests;
- configure measurement interval, gateway radio-slot time and enabled X/Y/Z axes from presets or validated custom values;
- replace embedded gateway network ID and password independently of the regional profile;
- validate and reinstall the exact APK-mapped G6 TIL90 firmware 2.81 image;
- run a guarded factory-reset, full backup-driven restore, reboot, and final configuration comparison;
- preview all changes before write and require exact `RESTORE <node-id>` confirmation;
- browse all 20 original Android radio profiles; regional profile editing remains separate from gateway credentials;
- run persistent background measurement and health polling with configurable intervals and retention;
- evaluate absolute X/Y/Z, rate-of-change, low-battery, sensor-error, and missing-data alerts locally;
- preserve open, resolved, and acknowledged alert state across service restarts;
- import up to 366 days of sensor history in bounded chunks with durable progress, pause/resume, and duplicate suppression;
- browse measurements stored by live, manual, or history sources and export them as CSV;
- diagnose stable USB identity, permissions, ModemManager conflicts, and reconnect state;
- run a complete read-only recovery assessment covering USB, health, identity, configuration plausibility, the APK factory-reset sentinel, and allowed/blocked actions;
- perform the hardware-validated reboot flow when writes are explicitly enabled;
- keep exact TX/RX evidence collapsed in a separate engineering section;
- create a complete JSON configuration backup with a SHA-256 corruption check;
- validate an uploaded backup without contacting the sensor;
- read the current sensor and preview an exact field-level restore plan;
- restore hardware-validated fields with identity checks, exact confirmation, ACK, readback, full post-backup comparison, and rollback on failure.

## Restore boundary

Hardware-confirmed on node `101677`, firmware `2.81`:

- sampling interval write `82 + uint24 seconds`, tested as `300 → 301 → 300`;
- channel flags write `9A + flags`, tested with identical state, temporary Z disable, X/Y-only live result and all-axis restore;
- gateway radio-slot write `90 + uint16 seconds`, tested as `3000 → 3001 → 3000`;
- every write returned response code `0x0000`, readback matched and the final configuration diff was empty.

The measurement interval and gateway slot are deliberately separate controls. The first determines ordinary measurement/storage periodicity. The second is the radio network's send-slot parameter used to distribute transmissions. It is not an independent promise that the gateway receives a packet at that exact wall-clock interval; values must remain compatible with the configured gateway/network plan.

Still blocked:

- calibration and node-identity changes;
- arbitrary regional-profile editing and arbitrary firmware files;
- firmware newer than 2.81 because no newer mapped normal G6 image is present;
- RF receipt verification until a gateway is available.

The web maintenance allowlist includes exact-image 2.81 reinstallation and a combined factory reset, backup-driven complete restore, reboot, and comparison. It does not expose a standalone reset button, which reduces the chance of intentionally leaving the node in defaults.

An uploaded backup must have a valid checksum and match node ID, product code, serial number, and firmware build. Any unsupported difference makes the entire plan non-applicable.

The SHA-256 value detects accidental corruption; it is not a keyed digital signature and does not make an edited file trustworthy. Restore safety comes from strict schema checks, fresh device reads, the field allowlist, identity matching, confirmation, and readback.

## Local security model

- HTTP binding and accepted Host values are loopback-only;
- API documentation and arbitrary packet endpoints are absent;
- device-affecting POST requests require an unpredictable same-origin session token;
- no CORS permission is emitted;
- responses use `no-store`, a restrictive Content Security Policy, frame denial, MIME sniffing protection, and no-referrer policy;
- one process lock serializes all USB operations;
- idempotent read groups automatically close and reopen the serial device after a temporary OS/serial failure; write packets are not automatically repeated;
- Uvicorn access logging is disabled to avoid noisy local transaction logs.

This is a local engineering tool, not a network service. Do not proxy it or expose it to a LAN.

## Operator workflow

Start read-only for inspection:

```bash
/usr/bin/python3 -m tools.web_service --serial-port /dev/ttyUSB0
```

Restart explicitly for validated configuration and reboot actions:

```bash
/usr/bin/python3 -m tools.web_service \
  --serial-port /dev/ttyUSB0 \
  --enable-writes
```

Even in write mode, the UI cannot send arbitrary packets, write calibration or node identity, select arbitrary firmware, or claim gateway reception. Network credentials, factory state, and mapped firmware recovery are exposed only through their guarded workflows.

## Monitoring and alerts

Monitoring is disabled by default. Enable it from **Monitoring & alerts** after selecting intervals. A live acquisition takes approximately ten seconds on the tested node, so the minimum configured measurement interval is ten seconds and actual scheduling never overlaps a running request. Health polling has a 30-second minimum. Manual reads, monitoring, history, backup, and configuration share the same serial lock.

SQLite uses WAL mode for a file-backed database. Measurement uniqueness is `(node_id, timestamp)`, so importing the same history range again is safe. Retention cleanup applies to measurement and health rows; alert and history-job audit rows remain available.

Alert rules are disabled when their input is blank, except the enabled-by-default sensor-error rule. When a condition first becomes true, one open event is created per node and rule. Repeated observations update that event. When the value returns within limits, it becomes resolved. Acknowledgement records operator review but does not suppress evaluation or falsely resolve an active condition.

These alerts are local engineering aids, not a certified railway safety system. Browser closure does not stop monitoring, but stopping the Python service does. Service restart resumes monitoring only when its persisted `enabled` setting is true.

## Resumable history

The history page creates a durable job instead of retaining one large response in browser memory. The default chunk is six hours; allowed chunks are five minutes through seven days. Each chunk must receive the device's normal `0x0080` completion response before its cursor advances. A disconnect, timeout, limit response, or incomplete stream pauses the job with its error text. **Resume** continues at the unchanged cursor. **Pause** takes effect between chunks.

Decoded measurement and health records are inserted into the same SQLite database. Job counters distinguish records received, newly imported, and duplicates. The UI limits normal table reads; CSV export is independently bounded to 10,000 newest matching measurements.

## Linux USB reliability

The service converts `/dev/ttyUSB0` to the matching `/dev/serial/by-id` alias before opening it. On the tested adapter that alias is `usb-Silicon_Labs_CP2102N_USB_to_UART_Bridge_Controller_d2f9787d759ced118acf026ce259fb3e-if00-port0`, with verified USB IDs `10c4:ea60`.

The maintenance page reports path resolution, mode, owner/group, read/write access, ModemManager state, and corrective actions. `config/99-til90-cp210x.rules` is the reviewed udev template for persistent `dialout`/desktop-session access. Installation changes the host and therefore remains an explicit administrator action.

The separate **Read-only recovery** action continues through health, identity, checksummed configuration, sampling/axes, radio plausibility, power and reconnect state. It never reboots or writes. See `smartphone-connection-recovery.md` for interpretation and the original APK evidence.
