# Linux One-Cable Reference Capture Plan

Last updated: 2026-07-15

Status: optional official-application comparison. Direct Linux read-only validation has already completed the core protocol gate; this plan remains useful for comparing displayed values and application behavior.

## Required topology

Only one physical data cable is available, so the normal USB-ADB arrangement cannot be used at the same time as the sensor. Use:

```text
Linux PC -- Wi-Fi / wireless ADB --> Android phone -- OTG USB cable --> TIL90
```

The phone and Linux PC must be on the same trusted network. Android 11 or newer normally provides **Developer options → Wireless debugging**. If the phone does not provide wireless debugging and network ADB was not already configured, simultaneous official-app use and ADB capture is not possible with the available cable.

## Step 1 — Pair wireless ADB before attaching the sensor

On the phone, enable Developer options and Wireless debugging. Select **Pair device with pairing code**; Android shows a pairing address and code. On Linux:

```bash
adb version
adb pair PHONE_IP:PAIR_PORT
```

Enter the displayed pairing code. Then use the separate IP address and port shown on the main Wireless debugging screen:

```bash
adb connect PHONE_IP:DEBUG_PORT
adb devices -l
```

The final command must show an `IP:port` device in the `device` state. Pairing and debugging ports are often different. Do not disconnect wireless ADB when the cable is moved to the sensor.

## Step 2 — Start a complete Android log

Create a new session directory, using the actual UTC start time in its name, and copy the metadata template:

```bash
SESSION="captures/reference_sessions/$(date -u +%Y-%m-%dT%H%M%SZ)"
mkdir -p "$SESSION/screenshots"
cp captures/session-metadata-template.md "$SESSION/session.md"
adb logcat -v threadtime | tee "$SESSION/android-logcat.txt"
```

Leave this terminal running. Do not use `adb logcat -c`; earlier buffered context may be useful. In a second terminal, verify that wireless ADB remains connected:

```bash
adb devices -l
```

`logcat` is useful only if the release application logs USB TX/RX data. It must not be assumed to contain raw protocol bytes. Preserve the complete log first; filtering can be done on a copy afterward.

## Step 3 — Connect the official application

Move the only cable to the phone and sensor, with the phone acting as USB host through OTG. Open the official application and grant its USB permission if prompted.

Record one action at a time:

1. connect only;
2. read node health;
3. read node information;
4. read extended information;
5. take one live reading;
6. read sampling rate;
7. read calibration;
8. read channel and alarm configuration;
9. read Bluetooth configuration;
10. read LoRa configuration;
11. query the stored-data interval;
12. download a small historical interval.

These are reference read operations initiated by the official app, not electrically passive observation. Do not open firmware update, factory reset, reboot, clock-setting, or configuration-edit screens.

## Evidence required for every action

- UTC and local timestamp;
- exact screen/action name;
- all values displayed by Android;
- screenshot where practical;
- node label, node ID, and product code;
- firmware and hardware version;
- action start/end and whether multiple responses appeared;
- exact TX/RX bytes, but only if the app or an approved capture method exposes them.

Do not invent missing bytes from the static registry. If `logcat` contains no raw TX/RX bytes, preserve the session and stop at this gate.

## What Linux cannot capture in this topology

Linux `usbmon` cannot see USB traffic flowing directly between the Android phone and the sensor because that bus does not pass through Linux. Likewise, `/dev/ttyUSB0` exists only when the sensor is attached to Linux, in which case the official Android app is not attached to it.

If application logs omit raw bytes, the next capture method requires separate planning, such as application instrumentation or a suitable hardware USB capture device. Neither is implicitly authorized by this plan.

## Linux-only fallback with the same cable

This alternate topology can re-confirm enumeration but cannot capture official-app traffic:

```text
Linux PC -- USB cable --> TIL90
```

Safe inventory commands that do not intentionally transmit application protocol bytes are:

```bash
lsusb -d 10c4:ea60
ls -l /dev/serial/by-id/ 2>/dev/null
udevadm info --query=property --name=/dev/ttyUSB0
```

The previously observed stable path was:

```text
/dev/serial/by-id/usb-Silicon_Labs_CP2102N_USB_to_UART_Bridge_Controller_d2f9787d759ced118acf026ce259fb3e-if00-port0
```

Do not start a terminal program or independent serial client during the reference phase. Even a receive-only serial open can alter termios or modem-control lines, so it should not be described as perfectly passive.

## Validation gates before an independent read-only client

- real DLE framing and escaping are visible in captured bytes;
- physical product code and G6/G7 routing are known;
- the actual node-ID width is confirmed;
- request bytes and response aliases match static analysis;
- live scale factors agree with displayed values;
- stored-data interval and history end marker `0x0080` are confirmed;
- no unexpected state change occurred.
