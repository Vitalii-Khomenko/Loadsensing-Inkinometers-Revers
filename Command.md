# Command Reference

Last updated: 2026-07-15

This file replaces the obsolete mixed-language interactive setup log. The authoritative project status is `ROADMAP.md`; detailed operator instructions are in `docs/cli-usage.md`, `docs/web-app.md`, and `docs/maintenance-cli.md`.

## Prepare the connected sensor

```bash
sudo systemctl stop ModemManager
sudo setfacl -m u:"$(id -un)":rw /dev/ttyUSB0
getfacl /dev/ttyUSB0
```

The ACL output must show the current user with `rw-` access. All direct serial tools use 115200 8N1, disable DTR/RTS, and request exclusive access.

## Run automated validation

```bash
cd /home/warmond/ReversEngeneering/Inklinometers
/usr/bin/python3 -m pytest -q tests
/usr/bin/python3 -m compileall -q tools tests
```

## Read-only CLI

```bash
/usr/bin/python3 -m tools.til90_cli detect --pretty
/usr/bin/python3 -m tools.til90_cli read identity --port /dev/ttyUSB0 --pretty
/usr/bin/python3 -m tools.til90_cli read health --port /dev/ttyUSB0 --pretty
/usr/bin/python3 -m tools.til90_cli read live --port /dev/ttyUSB0 --pretty
/usr/bin/python3 -m tools.til90_cli read configuration --port /dev/ttyUSB0 --pretty
/usr/bin/python3 -m tools.til90_cli read radio --port /dev/ttyUSB0 --pretty
```

## Web operator console

Read-only mode:

```bash
/usr/bin/python3 -m tools.web_service \
  --serial-port /dev/ttyUSB0 \
  --database data/til90.sqlite3
```

Validated configuration and reboot mode:

```bash
/usr/bin/python3 -m tools.web_service \
  --serial-port /dev/ttyUSB0 \
  --enable-writes
```

Open `http://127.0.0.1:8765/`.

The English web interface supports readable status, live measurements, persistent SQLite monitoring, local alerts, resumable/deduplicated history and CSV, USB diagnostics, recovery assessment, configuration, separate gateway credentials, checksummed backup/restore, guarded reboot, factory-reset-and-restore, and exact-image firmware recovery.

## Guarded maintenance CLI

```bash
/usr/bin/python3 -m tools.maintenance_cli reboot \
  --port /dev/ttyUSB0 \
  --confirm 'REBOOT 101677'

/usr/bin/python3 -m tools.maintenance_cli validate-channels \
  --port /dev/ttyUSB0 --axis z \
  --confirm 'VALIDATE CHANNELS 101677'

/usr/bin/python3 -m tools.maintenance_cli validate-gateway-slot \
  --port /dev/ttyUSB0 \
  --confirm 'VALIDATE GATEWAY SLOT 101677'

/usr/bin/python3 -m tools.maintenance_cli flash-firmware \
  --port /dev/ttyUSB0 \
  --confirm 'FLASH FIRMWARE 101677 2.81'

/usr/bin/python3 -m tools.maintenance_cli factory-reset \
  --port /dev/ttyUSB0 \
  --confirm 'FACTORY RESET 101677'
```

## Safety boundary

Hardware-validated write and recovery families:

- sampling interval;
- enabled X/Y/Z flags;
- gateway radio-slot time.
- complete embedded EU868 radio restoration from a backup;
- gateway network ID and password replacement;
- factory reset followed by full restore and reboot verification;
- exact mapped firmware 2.81 reinstallation.

Calibration, sensor clock, node ID, arbitrary firmware, and RF reception without a gateway remain blocked.
