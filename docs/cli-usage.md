# Linux Read-Only CLI

Last updated: 2026-07-15

`tools/til90_cli.py` is a Linux CLI for the directly connected CP2102N interface. Its command registry contains only read requests. There are no configuration-write, clock, reset, reboot, bootloader, coverage-test, or firmware commands.

## Prerequisites

The sensor appears as `/dev/ttyUSB0` and under `/dev/serial/by-id/`. The user needs serial permission, and ModemManager should not probe the port during a controlled session:

```bash
sudo systemctl stop ModemManager
sudo setfacl -m u:"$(id -un)":rw /dev/ttyUSB0
```

The ACL is temporary and normally disappears when the device is unplugged. Restore ModemManager after the session:

```bash
sudo systemctl start ModemManager
```

For permanent local access, review `config/99-til90-cp210x.rules`. Its USB IDs `10c4:ea60` match the physically connected CP2102N. Install it only with administrator approval:

```bash
sudo install -m 0644 config/99-til90-cp210x.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

The browser console reports the stable `/dev/serial/by-id` alias, current mode/owner/group, read/write access, ModemManager state, reconnect count, and corrective commands. Read transactions automatically reopen the device after a temporary OS/serial disconnect. Persistent writes are never blindly retried.

## Detection and basic reads

Run commands from the repository root:

```bash
/usr/bin/python3 -m tools.til90_cli detect --pretty
/usr/bin/python3 -m tools.til90_cli read identity --pretty
/usr/bin/python3 -m tools.til90_cli read live --pretty
/usr/bin/python3 -m tools.til90_cli read configuration --pretty
/usr/bin/python3 -m tools.til90_cli read radio --pretty
```

The script form is also supported:

```bash
/usr/bin/python3 tools/til90_cli.py read health --pretty
```

When more than one CP2102N is present, select the port explicitly:

```bash
/usr/bin/python3 -m tools.til90_cli \
  --port /dev/serial/by-id/DEVICE read health --pretty
```

## Repeated measurements and JSON capture

```bash
/usr/bin/python3 -m tools.til90_cli read live --count 3 --delay 1 --pretty
/usr/bin/python3 -m tools.til90_cli read all --pretty --output captures/my-read.json
```

Output contains host TX/RX timestamps, exact framed TX bytes, decoded response-body bytes, the protocol header, status, and decoded data. Exit code is nonzero for a timeout, device response error, decode error, or host serial error.

`all` intentionally excludes Bluetooth configuration because physical firmware 2.81 returned `INVALID_INPUT_PARAM`. It also excludes history download and any radio coverage test.

## Available selections

- groups: `identity`, `measurement`, `configuration`, `radio`, `all`;
- identity: `health`, `info`, `extended`;
- sensor data: `live`, `sampling`, `calibration`, `channels`, `interval`;
- radio: `radio-general`, `radio-address`, `radio-channels`, `radio-down-channels`, `radio-slot-time`, `radio-network-id`, `radio-join`;
- diagnostic unsupported-on-this-node read: `bluetooth`.

The CLI does not reveal a network password. Static analysis shows that the Android app retains the operator-entered password in encrypted application preferences and sends it through authentication write commands; there is no corresponding password read response.
