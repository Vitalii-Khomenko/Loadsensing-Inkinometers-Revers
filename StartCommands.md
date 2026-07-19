# Sensor Access Setup

Run these commands in a terminal:

```bash
sudo systemctl stop ModemManager
sudo setfacl -m u:"$(id -un)":rw /dev/ttyUSB0
```

Verify access:

```bash
getfacl /dev/ttyUSB0
```

The output must contain the current user with `rw-` permissions. The sensor is expected at `/dev/ttyUSB0`; prefer its stable `/dev/serial/by-id/` path when available.

Example expected ACL:

```text
# file: dev/ttyUSB0
# owner: root
# group: dialout
user::rw-
user:warmond:rw-
group::rw-
mask::rw-
other::---
```

Continue with `docs/cli-usage.md` for read-only commands or `docs/web-app.md` for the English browser console.

/usr/bin/python3 -m tools.web_service \
  --serial-port /dev/ttyUSB0 \
  --enable-writes

http://127.0.0.1:8765/