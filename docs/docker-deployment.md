# Docker USB Deployment

Last updated: 2026-07-22

## Outcome

The supplied Compose service can start before the sensor is connected. It remains healthy while waiting for a CP2102N adapter, discovers a single matching `/dev/serial/by-id` path after hotplug, performs serialized read-only acquisition, stores results in SQLite, and resumes automatically after USB disconnects. The browser receives connection state and the latest X/Y/Z values without requiring a manual read.

This deployment is intended for native Docker Engine on Linux, including a Raspberry Pi. Docker Desktop on macOS and Windows does not provide equivalent direct Linux USB-device handling without an additional USB forwarding layer.

## Host preparation

Docker Engine and Docker Compose are required. Verify them with:

```bash
docker --version
docker compose version
```

The Compose defaults assume host UID `1000`, GID `1000`, and `dialout` GID `20`. Check the host values before the first start:

```bash
id -u
id -g
getent group dialout
```

If they differ, create a local environment file:

```bash
cp docker.env.example .env
```

Edit only the numeric values in `.env`. The file is ignored by Git.

The reviewed udev rule grants the `dialout` group access and tells ModemManager to ignore the adapter. Install it on the Linux host if permanent access is required:

```bash
sudo install -m 0644 config/99-til90-cp210x.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Reconnect the USB cable after installing the rule.

## Build and start

The sensor may be disconnected during startup:

```bash
docker compose up --build -d
docker compose ps
```

Open `http://127.0.0.1:8765/`. The initial state is **Waiting for USB sensor**. Connect one TIL90 adapter; device discovery retries every two seconds and the state progresses through **Sensor detected**, **Connecting**, and **Sensor connected**. The first live result appears after the sensor answers its bounded request. Normal automatic intervals are ten seconds for tilt and sixty seconds for health.

Inspect service activity with:

```bash
docker compose logs -f til90
```

Stop the service without deleting the database:

```bash
docker compose down
```

Rebuild after pulling new source:

```bash
docker compose up --build -d
```

## USB hotplug design

The container receives a bind view of `/dev`, so new `/dev/ttyUSB*` devices and `/dev/serial/by-id` links appear without recreating it. The device cgroup rule permits character-device major `188`, used by Linux USB serial ports. The service selects a device only when exactly one matching CP2102N alias exists. It never silently chooses between multiple sensors.

Every transaction resolves the stable alias and opens the port under the shared serial lock. An idempotent read may reopen after an OS or serial disconnect; write transactions are never automatically retried. The monitoring loop waits and retries when the adapter is absent instead of terminating the web service.

For multiple simultaneous sensors, deploy one explicitly configured service per stable by-id path or implement the documented multi-sensor manager. Do not rely on `/dev/ttyUSB0` numbering.

## Persistence and security

SQLite data remains under the host repository's `data/` directory and is mounted at `/app/data`. The application code and container root filesystem are read-only. `/tmp` is a small in-memory filesystem.

The Compose service:

- publishes the browser only on host loopback;
- keeps sensor writes disabled;
- drops all Linux capabilities;
- enables `no-new-privileges`;
- grants the ttyUSB device class instead of using `privileged: true`;
- excludes APKs, decompiler output, captures, and runtime databases from the build context.

The `/dev` bind exposes device names to the container, but the device cgroup continues to restrict which character devices may be opened. A rootless Docker configuration may impose additional device-cgroup limitations; use ordinary rootful Docker Engine with the unprivileged application UID if rootless device forwarding fails.

## Validation without hardware

The container should be healthy while no sensor is attached:

```bash
docker compose ps
curl --fail http://127.0.0.1:8765/api/status
```

Expected status includes an empty `ports` list and `device_detected: false`. This is a waiting state, not a service failure. Physical USB identity, permissions, first response, live values, disconnect, and reconnect should be checked when the sensor is available.
