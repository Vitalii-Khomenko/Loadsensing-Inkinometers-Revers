# Guarded Maintenance CLI

Last updated: 2026-07-15

The ordinary `tools.til90_cli` remains read-only. Physically validated disruptive tests live in a separate command and require an exact confirmation containing node ID `101677`.

```bash
/usr/bin/python3 -m tools.maintenance_cli reboot \
  --port /dev/ttyUSB0 --confirm 'REBOOT 101677'

/usr/bin/python3 -m tools.maintenance_cli validate-channels \
  --port /dev/ttyUSB0 --axis z \
  --confirm 'VALIDATE CHANNELS 101677'

/usr/bin/python3 -m tools.maintenance_cli validate-gateway-slot \
  --port /dev/ttyUSB0 \
  --confirm 'VALIDATE GATEWAY SLOT 101677'

/usr/bin/python3 -m tools.maintenance_cli flash-firmware \
  --port /dev/ttyUSB0 --confirm 'FLASH FIRMWARE 101677 2.81' \
  --output firmware-reflash.json

/usr/bin/python3 -m tools.maintenance_cli factory-reset \
  --port /dev/ttyUSB0 --confirm 'FACTORY RESET 101677' \
  --output factory-reset.json
```

The reboot command takes a complete backup, sends exact body `09`, waits for health, proves uptime reset and rejects any persistent configuration difference. The channel validation writes the identical state, temporarily disables one axis, reads configuration and a live result, restores the original flags in `finally`, and compares complete before/after snapshots.

An additional research command reproduces the original application's bounded local-sampling packet. On this G6 INC360 firmware 2.81 it was safely rejected as `INVALID_SIZE`; it is retained as evidence tooling, not as a supported operating feature.

```bash
/usr/bin/python3 -m tools.maintenance_cli validate-local-sampling \
  --port /dev/ttyUSB0 --duration 6 --period 2 \
  --confirm 'VALIDATE LOCAL SAMPLING 101677'
```

Before factory reset, create a full backup and preserve the gateway password separately because it is write-only. Restore a reset node with:

```bash
/usr/bin/python3 -m tools.post_reset_restore_cli \
  --port /dev/ttyUSB0 \
  --backup pre-reset-backup.json \
  --network-id 27484 \
  --password-file gateway-password.txt \
  --confirm 'RESTORE AFTER RESET 101677' \
  --output post-reset-restore.json
```

The password file must contain only the password and have mode `0600`. Restoration writes radio general configuration, uplink/downlink channels, sampling, gateway slot, axes, join identifiers, and authentication in the Android order, with ACK and readback after every readable operation. Reboot afterward and create a final backup.

The physical validation evidence is in `captures/reference_sessions/2026-07-15T180007Z-reset-firmware-validation/`. The final backup has no semantic configuration differences from the pre-reset backup. Persistent and disruptive operations remain disabled by default in the browser service and require `--enable-writes` plus exact confirmation.
