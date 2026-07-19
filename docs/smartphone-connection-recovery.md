# Smartphone Connection and Sensor Recovery

Last updated: 2026-07-15

## First rule: diagnose before reset

A sensor that is invisible to the Android application does not yet justify a reboot, factory reset, or firmware flash. USB enumeration, Android permission, serial-port opening, protocol response, recognized product type, supported firmware, and valid configuration are separate gates. A factory reset cannot repair a bad cable or missing Android USB permission and may erase the information needed to rejoin the existing gateway.

## What the original APK does

Static analysis of application version 2.17.1 establishes this connection sequence:

1. The manifest and `usb_device_filter.xml` accept only vendor `4292` (`0x10C4`) and product `60000` (`0xEA60`), the Silicon Labs CP2102N adapter used by the physical sensor.
2. `WelcomeScreenActivity` handles `USB_DEVICE_ATTACHED`, searches Android's USB device list for that exact pair, and calls `UsbManager.requestPermission`.
3. Permission denial is logged separately as `PERMISSION DENIED -- USB PERMS`.
4. After permission, the app calls `UsbManager.openDevice`. A null result is treated as a USB-open failure.
5. The serial library opens the adapter as 115200 baud, 8 data bits, 1 stop bit, no parity, and no flow control, then starts its receive callback.
6. Node identification reads node information. After the initial request, reply timeouts permit four delayed retries at two-second intervals, for at most five attempts. The node-factory layer also applies a ten-second timeout to each identification operation.
7. A valid reply is then classified by product code and checked for minimum supported firmware.
8. After identification, the app reads the LoRa address. Only address `0xFFFFFFFF` triggers its explicit **Factory Reset Required** path. Failure or an empty result from that optional address read does not trigger reset.

Relevant recovered sources include `WelcomeScreenActivity`, its view model `C6758a`, USB classes `C4578a`/`C4579b`, `NodeFactory`, and `BaseNode` under `analysis/jadx/sources/`. Smali confirms details where the Java decompiler lost constructor instructions.

## Smartphone checklist

Work in this order:

1. Disconnect the sensor from Linux; one USB device cannot be controlled by the phone and Linux at the same time.
2. Use a known data-capable cable and the correct OTG adapter. A charging-only cable can power equipment without exposing USB data.
3. Confirm that the phone supports USB host/OTG mode and that OTG has not been disabled by a battery-saving or vendor setting.
4. Connect the sensor only after opening the official application, then accept the Android USB permission dialog.
5. If no dialog appears, unplug the sensor, force-stop the app, clear its saved USB-device default/permission in Android settings, reopen it, and reconnect.
6. Check the connector for contamination, looseness, or mechanical damage. Avoid an unpowered hub during diagnosis.
7. Ensure the sensor has the required internal battery/power path. The APK itself warns that some nodes shut down after USB removal unless a battery is connected and, where applicable, the switch is in `BATT` mode.
8. Wait through the application's identification retries instead of rapidly reconnecting during an active attempt.

Android versions and phone vendors expose USB-default controls differently. Clearing application data also removes application settings and should be treated separately from clearing only a USB default.

## Cross-check with Linux

If the smartphone still does not react, move the cable to Linux and use the new **Maintenance → Read-only recovery** check, or run the existing commands:

```bash
/usr/bin/python3 -m tools.til90_cli detect --pretty
/usr/bin/python3 -m tools.til90_cli read health --pretty
/usr/bin/python3 -m tools.til90_cli read identity --pretty
/usr/bin/python3 -m tools.til90_cli read configuration --pretty
```

Interpret the result by layer:

| Result | Most likely layer | Safe next action |
|---|---|---|
| No `10c4:ea60` device on phone or Linux | Cable, OTG/host mode, connector, adapter, or power | Change one physical component at a time; do not reset |
| CP2102N appears, but the phone cannot open it | Android USB permission, stale app connection, or another process | Revoke/regrant permission and reconnect with only one host |
| CP2102N opens, but Linux health also times out | Sensor power, CP2102N-to-MCU UART, MCU state, or firmware | Preserve diagnostics; try a full USB disconnect; escalate before destructive recovery |
| Linux reads health and identity, but Android fails | Android permission/app compatibility or app state | Record Android/app version and logs; sensor firmware is demonstrably responsive |
| Health works, complete configuration fails | One protocol/configuration family or unstable connection | Save health evidence, retry full read, compare the failing AM type |
| All reads work, but radio fields are empty/disabled | Configuration or post-repair provisioning, not USB | Compare with a known-good node and gateway project |
| LoRa address is exactly `0xFFFFFFFF` | APK-defined factory-reset-required sentinel | Backup and use an approved official recovery plan; do not auto-reset |

## Recovery features in our program

The web recovery check now performs, without writes:

- CP2102N enumeration and stable by-id resolution;
- Linux mode, owner/group, read/write permission, and ModemManager checks;
- bounded serial reopen/retry for health;
- node ID, product, firmware, and complete checksummed configuration read;
- sampling and enabled-axis plausibility;
- radio enabled state, address, network ID, and active-channel plausibility;
- the APK's exact `0xFFFFFFFF` factory-reset sentinel check;
- battery/uptime display and reconnect count;
- an explicit list of allowed and blocked recovery actions.

The program can then safely offer:

1. repeated read-only diagnosis and evidence capture;
2. a checksummed backup;
3. guarded reboot after identity and backup, because reboot was physically validated;
4. restoration from a matching checksummed backup, including the physically validated complete post-reset radio and gateway-authentication sequence;
5. history recovery to verify that the node is still measuring and storing data.

It must not infer that a radio warning means factory reset is appropriate.

## Factory reset evidence and boundary

The exact factory-reset serializer was recovered statically. Smali confirms AM type `0x08` followed by the 32-bit big-endian constant `0x75B544A2`, giving unframed payload:

```text
08 75 B5 44 A2
```

The APK first records uptime, sends the command, requires a success response within five seconds, then waits up to ten seconds for a health message without assuming the previous node ID. It removes the old in-memory node instance only after the post-reset health check succeeds.

The command was physically validated on node `101677` after a checksummed backup. Reset preserved identity, calibration, axes, and radio address, while it reset sampling, radio region/channels/slot, join identity, and authentication. The complete configuration was restored with a temporary gateway password, rebooted, and compared against the pre-reset backup with no semantic differences. The browser exposes only the combined reset-and-restore workflow; the standalone reset remains a guarded maintenance CLI operation.

## Firmware recovery evidence and boundary

For an unidentified/corrupted node, the APK has a separate bootloader workflow. It asks the bootloader for node type, selects a bundled/latest firmware image, flashes it, and gives the UI a 120-second timeout. It also contains model-specific follow-up logic, including an INC360 Alarm case. This is not equivalent to retrying an ordinary serial query.

The exact mapped G6 image was physically reinstalled using the Android ordering and XMODEM-CRC behavior. The service validates filename, size, SHA-256, product code, and current version before entering the bootloader; it then requires the node to return as firmware 2.81 and compares complete before/after configuration. This is a recovery/reinstallation path, not an upgrade path, because the APK contains no newer normal G6 TIL90 image. An interrupted transfer is still a field-service risk and requires stable USB power.
