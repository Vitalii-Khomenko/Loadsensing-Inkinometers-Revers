# TIL90 Reverse Engineering

Last updated: 2026-07-19

This repository documents a safety-first reverse engineering effort for a Worldsensing Loadsensing TIL90 sensor. Static analysis, direct Linux reads, monitoring, history, guarded configuration, gateway credentials, factory-reset recovery, and firmware 2.81 reinstallation are implemented. Calibration and node-ID writes remain blocked.

## Current state

- The UART framing and protocol-v2 response header are implemented.
- The Android response dispatcher registry contains 60 AM types.
- The read-only exchange registry contains 19 operations.
- Core TIL90 status, measurement, configuration, and history payloads have tested decoders.
- Direct Linux reads have confirmed health, identity, live measurements, sampling, calibration, G6 channels, and the stored-data interval.
- The physical sensor is `LS-G6-TIL90-I`, product `0x4E`, node `101677`, firmware `2.81`.
- After official post-repair programming, its radio is enabled as embedded `EU868_V1` with network ID `27484`, six 868 MHz uplinks, SF11, and TX power 14; the network password is not returned by the read protocol.
- An English localhost operator console provides readable inspection, graphs, persistent SQLite monitoring, local alerts, resumable/deduplicated history, CSV export, USB diagnostics, configuration presets, checksummed backup/restore and guarded reboot. Sampling, axis flags and gateway radio-slot time are hardware-validated write families.
- All 20 original Android radio profiles are inventoried; the current hardware configuration exactly matches embedded `EUROPE`.
- Bounded history returned 18 records, reboot reset uptime without changing configuration, and a temporary Z-axis disable produced an X/Y-only reading before verified restoration.
- The physical node passed an exact-image firmware 2.81 reflash, factory reset, complete backup-driven restoration with new gateway credentials, reboot, and a final zero-difference configuration comparison.

Start with `docs/README.md`. The first hardware evidence is under `captures/reference_sessions/2026-07-15T103257Z/`; the post-gateway-configuration comparison is under `captures/reference_sessions/2026-07-15T161221Z-post-gateway-config/`.

## Measurement axes and operating principle

The physical `LS-G6-TIL90-I` reports three enabled angular channels: X, Y, and Z. A hardware-captured live response returned X `-2.4473°`, Y `2.8581°`, and Z `86.2360°` at `27.8 °C`. All three channels are enabled on the tested node. A controlled configuration trial temporarily disabled Z, produced an X/Y-only live result, and then restored all three axes with a zero-difference configuration comparison.

The three reported angles describe the direction of the same gravity vector in the sensor's body coordinate system. For a stationary sensor, the measured acceleration components satisfy approximately:

```text
sqrt(ax^2 + ay^2 + az^2) = g
```

An individual axis angle can be represented conceptually as `theta_i = asin(ai / g)`, followed by the stored offset and gain calibration for that axis. The node exposes separate X/Y/Z offset and gain coefficients. When the sensor lies approximately level with Z pointing upward, X and Y are near `0°` and Z is near `+90°`; turning it onto a side moves the corresponding horizontal axis toward `+90°` or `-90°`.

Although the payload contains three angle values, gravity supplies only two independent tilt degrees of freedom. The channels are geometrically related and, under stationary ideal conditions, approximately satisfy:

```text
sin(theta_x)^2 + sin(theta_y)^2 + sin(theta_z)^2 = 1
```

The sensor can therefore describe inclination in three body-axis channels and can be used to derive pitch and roll with a documented mounting convention. It cannot independently determine rotation about the gravity vector (yaw or compass heading). The protocol supports an optional nine-bit `azimuth` field in version-1 regular readings, but the tested firmware `2.81` uses the version-0 reading format and has not produced a hardware-confirmed azimuth.

Each enabled channel is encoded as a signed 21-bit angle scaled by `1/10000°` and is accompanied by a standard-deviation value. The message also carries temperature, timestamp, precision mode, and an error code. The `0.0001°` protocol increment is an encoding resolution, not a demonstrated absolute accuracy. Axis sign, mounting orientation, linearity, repeatability, and temperature effects still require validation against a traceable angular reference fixture before metrology claims are made.

## Repository map

| Path | Purpose | Authority |
|---|---|---|
| `AGENTS.md` | Mandatory English-only policy for all authored code, UI, tests, and documentation | Repository-wide rule |
| `Goal.md` | Full project specification and safety stages | Authoritative scope |
| `ROADMAP.md` | Dated English progress log and next gate | Authoritative status |
| `docs/multi-sensor-wired.md` | Proposed ten-sensor wired Linux architecture and test plan | Design complete; implementation pending |
| `docs/README.md` | Documentation index and evidence labels | Current navigation |
| `docs/protocol.md` | Consolidated protocol summary | Current technical summary |
| `analysis/protocol/*.csv` | Machine-readable protocol registries | Static-analysis output |
| `tools/packet_parser/` | Python frame and payload decoders | Tested implementation |
| `tools/til90_cli.py` | Direct Linux read-only CLI | Hardware-tested |
| `tools/maintenance_cli.py`, `tools/firmware_service.py` | Explicitly confirmed reboot, factory reset, and firmware recovery | Hardware-tested on node 101677 |
| `tools/web_service.py`, `web/` | Readable local operator console and guarded configuration API | Implemented and hardware-backed |
| `tools/monitoring_store.py`, `tools/monitoring_service.py` | SQLite acquisition, retention, and alert evaluation | Implemented and synthetic-tested |
| `tools/history_manager.py` | Chunked, deduplicated, resumable history importer | Implemented and synthetic-tested |
| `tools/usb_diagnostics.py`, `config/99-til90-cp210x.rules` | Stable Linux identity, access diagnostics, and permanent udev template | Implemented; current adapter verified |
| `docs/monitoring-and-alerts.md` | Persistent acquisition, schema, alert semantics, and reliability boundary | Current design and operator reference |
| `docs/smartphone-connection-recovery.md` | Original APK connection path and safe sensor recovery decision tree | Current troubleshooting reference |
| `docs/remaining-work.md` | Consolidated unfinished work and validation gates | Current backlog |
| `tests/` | Synthetic and consistency tests | Automated validation |
| `captures/` | Reference-session layout and metadata template | Capture-pending |
| `APK-Info.md` | Raw command output and investigation notes | Historical evidence |
| `Command.md`, `StartCommands.md` | Current English command and serial-access quick references | Maintained operator guidance |

Large decompiler outputs under `analysis/jadx/` and `analysis/apktool/` are source evidence, not maintained documentation.

## Validation

Run from the repository root:

```bash
/usr/bin/python3 -m pytest -q tests
/usr/bin/python3 -m compileall -q tools tests
```

The explicit `/usr/bin/python3` avoids accidentally using an unrelated active virtual environment.

## Read-only CLI

After granting serial access as described in `docs/cli-usage.md`:

```bash
/usr/bin/python3 -m tools.til90_cli detect --pretty
/usr/bin/python3 -m tools.til90_cli read identity --pretty
/usr/bin/python3 -m tools.til90_cli read live --pretty
/usr/bin/python3 -m tools.til90_cli read radio --pretty
```

## Local browser console

```bash
/usr/bin/python3 -m tools.web_service
```

Open `http://127.0.0.1:8765/`. See `docs/web-app.md` for backup/restore behavior and the explicit write enable switch.

Long-term data is stored by default in `data/til90.sqlite3`. Use `--database PATH` to select another SQLite file.

## Safety boundary

The read-only CLI remains restricted to its documented allowlist. Browser writes require a separate `--enable-writes` launch, identity checks, exact confirmation, readback, post-operation backup comparison, and a recovery path. Sampling, axes, radio slot, embedded gateway credentials, complete post-reset radio restoration, factory reset, and exact-image firmware 2.81 recovery are hardware-validated. Calibration writes, node-ID changes, newer firmware, and RF delivery without a gateway remain blocked.
