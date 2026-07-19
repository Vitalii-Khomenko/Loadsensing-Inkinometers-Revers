# Technical Specification

> Project navigation is in `README.md`; dated execution status is in `ROADMAP.md`. This file remains the authoritative project scope.

## Full Reverse Engineering and Independent Control of Worldsensing Loadsensing TIL90 Sensor

## 1. Project Goal

Develop an independent software and documentation stack that allows complete local control of a Worldsensing Loadsensing TIL90 sensor without relying on the official Android application.

The final system should support:

* device detection and connection;
* node identification;
* reading live measurements;
* reading sensor status and metadata;
* downloading stored historical data;
* changing sampling and radio parameters;
* changing node ID and time;
* reading and writing sensor configuration;
* reading calibration parameters;
* factory reset and reboot;
* firmware version detection;
* firmware backup where technically possible;
* firmware update;
* recovery from failed updates;
* Bluetooth and LoRa configuration;
* independent Linux/Windows client;
* optional Android client;
* documented binary protocol;
* automated tests and packet captures.

The work must proceed in a controlled manner. Read-only operations must be implemented before any write, reset, bootloader, or firmware operation.

---

# 2. Confirmed Device Information

## 2.1 Sensor

Observed device family:

```text
Worldsensing Loadsensing
TIL90 inclinometer
G6 device physically available for testing
```

The Android application also contains support for:

```text
LS_G7_TIL90
INC15
INC360
INC360 Alarm
Laser TIL90
GNSS
Analog
Digital
VW
Pico
Dynamic nodes
```

The TIL90 implementation is located in:

```text
com/worldsensing/ls/lib/nodes/til90
```

Decompiled package path:

```text
analysis/jadx/sources/com/worldsensing/p322ls/lib/nodes/til90/
```

Main classes:

```text
Til90.java
Til90Node.java
```

---

## 2.2 Official Android Application

Application:

```text
Name: Worldsensing
Package: com.worldsensing.loadsensing.wsapp
Version: 2.17.1
Version code: 108
Minimum Android SDK: 26
Target Android SDK: 35
```

Original package:

```text
Worldsensing_2.17.1_APKPure.xapk
```

Base APK:

```text
com.worldsensing.loadsensing.wsapp.apk
```

Important Android activities:

```text
SplashScreenActivity
WelcomeScreenActivity
MainActivity
BluetoothScreenActivity
TakeSampleActivity
TakeLocalSamplesActivity
DownloadDataActivity
FirmwareUpdateActivity
RadioCoverageTestActivity
FactoryResetActivity
RebootNodeActivity
CalibrationParametersActivity
ExportImportActivity
ChangeNodeIdActivity
SetTimeActivity
SetLastConfigActivity
SensorSettingsActivity
VWAutoDiagnosticActivity
BaseAdministratorActivity
GnssCorrectionsCoverageTestActivity
```

USB attachment is handled by:

```text
WelcomeScreenActivity
```

Intent:

```text
android.hardware.usb.action.USB_DEVICE_ATTACHED
```

USB filter:

```text
res/xml/usb_device_filter.xml
```

Contents:

```xml
<resources>
    <usb-device product-id="60000" vendor-id="4292" />
</resources>
```

Converted values:

```text
Vendor ID:  4292  = 0x10C4
Product ID: 60000 = 0xEA60
```

---

## 2.3 USB Interface

Confirmed hardware:

```text
Silicon Labs CP2102N USB to UART Bridge Controller
VID:PID 10c4:ea60
Linux driver: cp210x
Linux device: /dev/ttyUSB0
```

Stable Linux path:

```text
/dev/serial/by-id/usb-Silicon_Labs_CP2102N_USB_to_UART_Bridge_Controller_<SERIAL>-if00-port0
```

Confirmed serial parameters:

```text
Baud rate:   115200
Data bits:   8
Parity:      none
Stop bits:   1
Flow control: none
```

Standard notation:

```text
115200 8N1
```

Android implementation:

```text
analysis/jadx/sources/p279Z6/C4578a.java
analysis/jadx/sources/p279Z6/C4579b.java
```

Important calls:

```java
setBaudRate(115200);
setDataBits(8);
setStopBits(1);
setParity(0);
setFlowControl(0);
write(byte[]);
```

---

# 3. Confirmed Software Architecture

Current high-level command path:

```text
Android UI
    ↓
Node-specific class
    ↓
Til90Node
    ↓
C7596n message dispatcher
    ↓
C7580a binary serializer/parser
    ↓
InterfaceC2964c connection interface
    ↓
C4579b USB connection wrapper
    ↓
C4578a USB serial transport
    ↓
CP2102N
    ↓
Sensor UART
```

Important classes:

```text
p367g7/C7596n.java
p367g7/C7580a.java
p367g7/C7600r.java
p162O7/InterfaceC2964c.java
p162O7/InterfaceC2963b.java
p279Z6/C4578a.java
p279Z6/C4579b.java
```

`C7596n` performs:

* outgoing message queueing;
* one-command-at-a-time transmission;
* 50 ms delay before send;
* incoming byte processing;
* response filtering by node ID;
* response filtering by class/type;
* timeout handling;
* multiple-response handling;
* registration of receive callbacks.

The actual packet serializer/parser is expected in:

```text
p367g7/C7580a.java
```

---

# 4. Confirmed TIL90 Parameters

From `Til90Node.java`:

```text
Maximum take-reading duration: 10 seconds
Minimum standalone sampling interval: 10 seconds
```

Channels:

```text
AXIS_X
AXIS_Y
AXIS_Z
```

Detected node type used by the application:

```text
NodeType.LS_G7_TIL90
```

The physical test sensor is G6, so the agent must determine:

* whether G6 and G7 share the same TIL90 protocol;
* whether G6 is mapped to the same node class;
* whether generation-specific behavior exists only in bootloader and firmware handling;
* whether a separate G6 TIL90 class exists elsewhere.

---

# 5. Confirmed Configuration Codes

The configuration request class is:

```text
p378h7/C7711o.java
```

Confirmed protocol configuration IDs:

```text
INC360_CALIBRATION       = 152 = 0x98
LASERTIL90_CH_CONFIG    = 153 = 0x99
INC360_CH_CONFIG        = 154 = 0x9A
INC360_ALARM_CH_CONFIG  = 155 = 0x9B
DYNAMIC_CONFIG          = 158 = 0x9E
GNSS_CONFIG             = 159 = 0x9F
GNSS_BASE_POSITION      = 161 = 0xA1
GNSS_CORRECTION_KEYS    = 162 = 0xA2
GNSS_CORRECTION_CHANNEL = 163 = 0xA3
BLUETOOTH_CONFIG        = 165 = 0xA5
```

TIL90 methods:

```java
requestCalibration()
    → INC360_CALIBRATION
    → 152 / 0x98

requestChannelConfig()
    → INC360_ALARM_CH_CONFIG
    → 155 / 0x9B
```

The agent must recover all remaining IDs from smali where JADX replaced constants with unrelated Mapbox constants.

---

# 6. Confirmed Firmware and Bootloader Information

Relevant classes:

```text
p334d7/C6859c.java
p334d7/C6865h.java
p334d7/C6869l.java
```

Detected serial modes:

```text
RAW
BRIDGE_ASCII
DFU_BGAPI
```

These represent:

* normal binary node protocol;
* Bluetooth bridge using ASCII AT commands;
* Bluetooth firmware update through BGAPI.

Detected firmware transfer mechanisms:

```text
XMODEM
YMODEM
CRC-16 polynomial 0x1021
```

Observed bootloader behavior:

```text
G6:
send "worldsensing"
wait for transfer request

G7:
send "worldsensing"
wait
send "3"
wait
```

The discovered firmware update code may use:

```text
YMODEM/XMODEM block size: 128 bytes
SOH: 0x01
EOT: 0x04
ACK: 0x06
CRC request: ASCII 'C' = 0x43
```

Bluetooth firmware resource discovered:

```text
firmwares/480-00182-R126.3.3.36_UART.gbl
```

The agent must not execute bootloader or firmware commands until the normal read-only protocol is fully understood and a recovery plan exists.

---

# 7. Project Directory Structure

Use the following structure:

```text
Inklinometers/
├── original/
│   ├── Worldsensing_2.17.1_APKPure.xapk
│   └── checksums.txt
├── xapk_extracted/
├── analysis/
│   ├── original/
│   ├── jadx/
│   ├── apktool/
│   ├── smali/
│   ├── logs/
│   ├── grep/
│   ├── protocol/
│   ├── firmware/
│   └── captures/
├── docs/
│   ├── architecture.md
│   ├── protocol.md
│   ├── commands.md
│   ├── message-types.md
│   ├── node-types.md
│   ├── firmware.md
│   ├── recovery.md
│   └── test-plan.md
├── tools/
│   ├── serial_sniffer/
│   ├── packet_parser/
│   ├── apk_analysis/
│   └── firmware_tools/
├── client/
│   ├── worldsensing/
│   │   ├── transport/
│   │   ├── protocol/
│   │   ├── messages/
│   │   ├── nodes/
│   │   ├── firmware/
│   │   └── cli/
│   └── tests/
└── captures/
    ├── usb/
    ├── serial/
    ├── android/
    └── reference_sessions/
```

---

# 8. Phase 1 — Preserve Evidence and Baseline

## Objectives

Create a reproducible baseline before modifying anything.

## Tasks

1. Calculate hashes:

```bash
sha256sum Worldsensing_2.17.1_APKPure.xapk
sha256sum xapk_extracted/*.apk
```

2. Save:

```text
APK version
package name
file sizes
hashes
JADX version
apktool version
Java version
Linux kernel
USB device information
sensor serial number
sensor label photographs
```

3. Record the current sensor state using the official application:

```text
Node ID
firmware version
hardware version
serial number
sampling interval
radio settings
region
channel configuration
calibration coefficients
battery status
temperature
last measurement
number of stored samples
Bluetooth configuration
```

4. Export every configuration file available through the official application.

5. Download all historical data before testing write operations.

6. Photograph every configuration screen.

## Deliverables

```text
docs/baseline.md
analysis/logs/device_baseline.txt
analysis/logs/apk_hashes.txt
analysis/captures/official_app_screens/
```

---

# 9. Phase 2 — Complete Static Analysis of the APK

## Objectives

Recover the full internal architecture, packet definitions, command IDs, and parsing logic.

## Priority Classes

### Transport and packet handling

```text
p367g7/C7580a.java
p367g7/C7596n.java
p367g7/C7600r.java
p162O7/InterfaceC2964c.java
p279Z6/C4578a.java
p279Z6/C4579b.java
```

### Base node implementation

```text
com/worldsensing/p322ls/lib/nodes/BaseNode.java
com/worldsensing/p322ls/lib/nodes/Node.java
com/worldsensing/p322ls/lib/nodes/NodeGenerics.java
com/worldsensing/p322ls/lib/nodes/NodeType.java
```

### TIL90 implementation

```text
com/worldsensing/p322ls/lib/nodes/til90/Til90.java
com/worldsensing/p322ls/lib/nodes/til90/Til90Node.java
```

### Related inclinometer classes

```text
nodes/inc15/
nodes/inc360/
nodes/inc360alarm/
nodes/lasertil90/
```

### Message classes

```text
p378h7/
p434m7/
p456o7/
```

## Required Analysis

For each message class, document:

```text
class name
human-readable purpose
AM type
payload length
field offsets
field sizes
byte order
signed/unsigned handling
scale factor
units
node ID location
timestamp format
CRC/checksum
expected response class
timeout
supported node generations
```

## Required Search Commands

```bash
grep -RniE \
'getAmType|getPayload|setNodeId|nodeId|CRC|checksum|length|ByteBuffer|LITTLE_ENDIAN|BIG_ENDIAN' \
analysis/jadx/sources
```

```bash
grep -RniE \
'requestNodeReading|requestNodeInfo|requestNodeHealth|requestDataRecovery|requestFactoryReset|sendNodeReboot' \
analysis/jadx/sources/com/worldsensing
```

```bash
grep -RniE \
'INC360_CALIBRATION|INC360_ALARM_CH_CONFIG|LS_G7_TIL90|LS_G6' \
analysis/jadx/sources analysis/apktool/smali*
```

## JADX Failure Handling

JADX reported 48 decompilation errors. For every critical failed method:

1. Locate the corresponding smali file.
2. Reconstruct control flow manually.
3. Record original register use.
4. Recover constants from `const`, `const/16`, `const-wide`, and static initializers.
5. Compare the Java output with smali.
6. Mark uncertain fields explicitly.

## Deliverables

```text
docs/architecture.md
docs/message-types.md
docs/node-types.md
docs/configuration-ids.md
analysis/protocol/message_registry.csv
```

---

# 10. Phase 3 — Recover Binary Packet Format

## Objectives

Determine the exact UART frame structure.

## Main Target

Analyze:

```text
p367g7/C7580a.java
```

Determine:

```text
preamble
protocol version
AM type
node ID
payload length
payload
sequence number
message direction
CRC/checksum
escaping
frame terminator
fragmentation rules
multiple frames in one read
partial frame handling
```

## Required Questions

1. What is the minimum frame length?
2. Is there a fixed header?
3. Is the protocol TinyOS Active Message based?
4. What does `getAmType()` represent?
5. Is node ID 16-bit, 32-bit, or 64-bit?
6. Is payload length encoded explicitly?
7. Is CRC included in UART data?
8. Does CP2102N deliver raw frames or framed packets?
9. Can multiple messages arrive in one USB read?
10. How are incomplete messages buffered?
11. Are bytes escaped?
12. Is there a request sequence number?
13. How are failed responses represented?

## Deliverables

```text
docs/protocol.md
docs/frame-format.md
tools/packet_parser/frame.py
tests/test_frame_parser.py
```

---

# 11. Phase 4 — Passive Dynamic Capture

## Objectives

Observe official application traffic without sending custom commands.

## Preferred Methods

### Method A — Android logcat

```bash
adb logcat
```

Filter:

```bash
adb logcat | grep -iE \
'usb|serial|send:|received byte|node|worldsensing|loadsensing'
```

The application logs transmitted and received bytes through:

```text
C4578a.send()
C4578a.onReceivedData()
```

Expected log strings:

```text
send: <hex>
Received byte message: <hex>
```

### Method B — Modify logging level

If release logging suppresses verbose messages:

* patch the APK;
* replace logging checks;
* instrument `C4578a.send`;
* instrument `C4578a.onReceivedData`;
* use Frida only if necessary.

### Method C — Linux bridge/sniffer

Use a controlled serial proxy:

```text
official Android app ↔ USB device
```

Possible tools:

```text
usbmon
Wireshark USBPcap equivalent
Frida
Xposed
custom Android USB proxy
hardware UART tap
```

## Reference Capture Sequence

Capture one action at a time:

```text
01_connect
02_request_node_info
03_request_hardware_version
04_request_firmware_version
05_request_serial_number
06_request_node_health
07_request_live_reading
08_request_multiple_readings
09_request_sampling_rate
10_request_calibration
11_request_channel_config
12_download_history
13_request_radio_config
14_request_bluetooth_config
15_set_time
16_change_sampling_rate
17_reboot
```

Do not capture factory reset or firmware update until recovery is established.

## Deliverables

```text
captures/reference_sessions/
docs/capture-index.md
analysis/protocol/request_response_pairs.csv
```

---

# 12. Phase 5 — Build a Read-Only Python Client

## Objectives

Implement a safe independent client supporting only non-destructive operations.

## Technology

```text
Python 3.11+
pyserial
dataclasses
enum
struct
logging
pytest
```

## Package Structure

```text
client/worldsensing/
├── transport/
│   ├── base.py
│   └── serial.py
├── protocol/
│   ├── frame.py
│   ├── parser.py
│   ├── crc.py
│   └── registry.py
├── messages/
│   ├── base.py
│   ├── requests.py
│   └── responses.py
├── nodes/
│   ├── base.py
│   └── til90.py
└── cli/
    └── main.py
```

## Initial Read-Only Commands

Implement in this order:

```text
detect device
open serial port
listen without transmitting
request node info
request node health
request serial number
request hardware version
request firmware version
request current reading
request sampling rate
request calibration
request channel configuration
request radio configuration
request Bluetooth configuration
download stored data
```

## Safety Requirements

The client must reject by default:

```text
factory reset
firmware update
bootloader entry
reboot
set node ID
set calibration
set channel configuration
set radio settings
erase history
```

Require an explicit flag:

```bash
--allow-write
```

For destructive operations require:

```bash
--dangerous
```

## Deliverables

```text
client/worldsensing/
worldsensing-cli
tests/
docs/client-usage.md
```

---

# 13. Phase 6 — Measurement Decoding

## Objectives

Decode the TIL90 measurement payload.

## Required Fields

Determine whether responses contain:

```text
X angle
Y angle
Z angle
temperature
battery voltage
supply state
sensor status
timestamp
quality/status flags
raw accelerometer values
calibrated values
alarm state
```

## Required Analysis

Compare:

```text
raw packet bytes
official app displayed values
physical sensor orientation
known reference angles
```

Perform controlled tests:

```text
sensor level
+1 degree X
-1 degree X
+5 degrees X
+1 degree Y
-1 degree Y
rotated 90 degrees
temperature change
```

Do not exceed mechanical or manufacturer limits.

## Output Model

Example:

```python
@dataclass
class Til90Reading:
    node_id: int
    timestamp: datetime | None
    x_deg: float
    y_deg: float
    z_deg: float | None
    temperature_c: float | None
    battery_v: float | None
    status: int
    raw_payload: bytes
```

## Deliverables

```text
docs/til90-reading-format.md
tests/fixtures/til90_readings/
tools/plot_til90.py
```

---

# 14. Phase 7 — Historical Data Recovery

## Objectives

Reproduce the official `DownloadDataActivity`.

## Required Analysis

Locate:

```text
requestDataRecovery
generateHistoricDataFromMessages
generateHistoricDataFromMessagesWithFormat
DownloadDataActivity
TakeLocalSamplesActivity
```

Determine:

```text
start timestamp encoding
end timestamp encoding
pagination
maximum records per request
response sequence
end-of-data marker
timezone handling
sample interval
duplicate handling
CRC
message ordering
```

## Deliverables

```text
worldsensing-cli history download
CSV export
JSON export
SQLite storage
docs/history-protocol.md
```

---

# 15. Phase 8 — Configuration Read and Write

## Objectives

Implement safe configuration management.

## Configuration Areas

```text
sampling interval
node time
node ID
channel configuration
alarm thresholds
calibration
radio region
radio channels
radio network ID
slot timing
LoRa session
Bluetooth configuration
cloud configuration
sensor metadata
last configuration restore
```

## Mandatory Workflow

For every write operation:

1. Read current configuration.
2. Save JSON backup.
3. Validate new values.
4. Show byte-level diff.
5. Require confirmation.
6. Send one write command.
7. Read back configuration.
8. Compare expected and actual values.
9. Save transaction log.
10. Provide rollback command.

## Example CLI

```bash
worldsensing-cli config read --output sensor-backup.json
worldsensing-cli config diff sensor-backup.json new-config.json
worldsensing-cli config apply new-config.json --allow-write
worldsensing-cli config verify new-config.json
worldsensing-cli config restore sensor-backup.json --allow-write
```

## Deliverables

```text
docs/configuration.md
docs/write-safety.md
client/worldsensing/config/
```

---

# 16. Phase 9 — Reboot and Factory Reset

## Objectives

Implement these only after configuration backup and restore are verified.

## Requirements

### Reboot

* identify exact command;
* confirm normal response;
* detect USB disconnect/reconnect;
* reopen the port;
* verify device identity;
* read node health afterward.

### Factory reset

Before implementation:

* determine exactly what is erased;
* determine whether calibration is preserved;
* determine whether node ID changes;
* determine radio default values;
* determine whether historical data is erased;
* determine whether firmware is preserved;
* create complete backup;
* verify restore functionality.

Factory reset must require:

```bash
--dangerous
--confirm-node-id <ID>
--backup <FILE>
```

## Deliverables

```text
docs/reboot.md
docs/factory-reset.md
tests/test_reconnect.py
```

---

# 17. Phase 10 — Firmware Extraction and Inventory

## Objectives

Identify every firmware file embedded in the APK.

## Tasks

Search:

```bash
find analysis/apktool -type f \
  \( -iname '*.bin' -o -iname '*.hex' -o -iname '*.gbl' \
  -o -iname '*.fw' -o -iname '*.img' \)
```

Search strings:

```bash
grep -RniE \
'firmware|bootloader|gbl|xmodem|ymodem|uart|version' \
analysis/apktool analysis/jadx
```

Extract from:

```text
base APK
config.arm64_v8a.apk
assets/
res/raw/
unknown/
native libraries
JAR resources
```

For every firmware file record:

```text
filename
size
SHA-256
target board
target generation
version
format
header
signatures
encryption
compression
update method
```

## Deliverables

```text
analysis/firmware/inventory.csv
docs/firmware-inventory.md
```

---

# 18. Phase 11 — Firmware Update Reimplementation

## Objectives

Reproduce official firmware update behavior safely.

## Known Information

G6 and G7 update paths differ.

G6 bootloader sequence appears to include:

```text
reboot command
wait for bootloader
send "worldsensing"
wait for ASCII 'C'
start XMODEM/YMODEM transfer
```

G7 sequence appears to include:

```text
reboot command
send "worldsensing"
send "3"
wait for transfer request
send YMODEM header where required
send firmware
```

Transfer details:

```text
128-byte blocks
SOH = 0x01
EOT = 0x04
ACK = 0x06
'C' = 0x43
CRC-16/CCITT polynomial = 0x1021
```

## Mandatory Safety Conditions

Do not test firmware updates until:

* exact device generation is identified;
* correct firmware image is identified;
* current firmware version is known;
* bootloader recovery is understood;
* power is stable;
* USB disconnect risk is minimized;
* original configuration is backed up;
* official application remains available;
* a second recovery machine is available;
* serial logs are enabled.

## Firmware CLI

```bash
worldsensing-cli firmware info
worldsensing-cli firmware verify firmware.bin
worldsensing-cli firmware dry-run firmware.bin
worldsensing-cli firmware update firmware.bin \
  --dangerous \
  --confirm-node-id <ID>
```

## Deliverables

```text
docs/firmware.md
docs/bootloader.md
docs/recovery.md
client/worldsensing/firmware/
```

---

# 19. Phase 12 — Bluetooth Bridge Analysis

## Objectives

Recover Bluetooth configuration and firmware update logic.

## Known Modes

```text
RAW
BRIDGE_ASCII
DFU_BGAPI
```

## Tasks

Analyze:

```text
C6859c
C7013b
C7016e
C7890b
BluetoothConfig
BluetoothScreenActivity
```

Determine:

```text
command to enter Bluetooth bridge
AT command set
module manufacturer
Bluetooth firmware version command
Bluetooth name
BLE services
BLE characteristics
authentication
BGAPI framing
Bluetooth DFU process
```

## Deliverables

```text
docs/bluetooth.md
docs/bgapi.md
client/worldsensing/bluetooth/
```

---

# 20. Phase 13 — LoRa and Radio Configuration

## Objectives

Support local reading and configuration of radio parameters.

## Required Areas

```text
radio region
frequency plan
network ID
slot time
downlink channels
channel group
LoRa join configuration
LoRa MAC address
LoRa session state
coverage test
radio off mode
embedded gateway configuration
cloud radio authentication
```

## Restrictions

Do not transmit arbitrary radio packets or change regional frequency settings without validating legal regional limits.

The client must validate the configured region before applying radio parameters.

## Deliverables

```text
docs/radio.md
docs/lora.md
client/worldsensing/radio/
```

---

# 21. Phase 14 — Full Independent Application

## Minimum Features

```text
device connection
device inventory
live values
history download
graphs
CSV/JSON export
configuration backup
configuration restore
firmware management
radio settings
Bluetooth settings
logs
diagnostic mode
```

## Preferred Implementations

### First implementation

```text
Python CLI
```

### Second implementation

```text
Python desktop GUI using PySide6
```

### Optional third implementation

```text
Android application using Kotlin
```

## GUI Views

```text
Connection
Node information
Live measurements
Historical data
Sensor configuration
Radio configuration
Bluetooth configuration
Calibration
Firmware
Diagnostics
Logs
```

---

# 22. Phase 15 — Testing Strategy

## Unit Tests

Test:

```text
frame encoding
frame decoding
CRC
partial messages
multiple frames in one read
invalid length
invalid checksum
unknown message type
signed values
endianness
timestamp conversion
measurement scaling
```

## Hardware-in-the-Loop Tests

Test against the real sensor:

```text
connect/disconnect
read node info
read health
read live measurement
download history
change sampling interval
restore sampling interval
reboot
reconnect
configuration backup/restore
```

## Destructive Tests

Only after all previous phases:

```text
firmware update
failed-transfer recovery
factory reset
configuration restoration
```

## Deliverables

```text
tests/unit/
tests/integration/
tests/hardware/
docs/test-results.md
```

---

# 23. Required Logging

Every session must record:

```text
UTC timestamp
local timestamp
device path
USB serial number
node ID
firmware version
command name
TX bytes in hex
RX bytes in hex
decoded request
decoded response
duration
result
exception
```

Example:

```text
2026-07-15T09:30:00Z
NODE=123456
CMD=request_node_info
TX=...
RX=...
RESULT=success
DURATION_MS=184
```

Logs must never silently omit raw packets.

---

# 24. Safety Rules for the AI Agent

The agent must follow these rules:

1. Do not send guessed packets to the device.
2. Do not brute-force command IDs.
3. Do not enter bootloader before recovery is documented.
4. Do not execute factory reset without a full configuration backup.
5. Do not flash firmware based only on filename similarity.
6. Do not assume G6 and G7 firmware compatibility.
7. Do not modify calibration before reading and saving the original coefficients.
8. Do not alter radio region blindly.
9. Do not erase stored measurements before downloading them.
10. Do not treat JADX output as authoritative when smali disagrees.
11. Preserve all original APK and firmware files read-only.
12. Add dry-run mode for every write function.
13. Require explicit confirmation for destructive operations.
14. Verify every write by reading the value back.
15. Maintain a complete protocol evidence table.

---

# 25. Immediate Next Task for Codex

Start with the exact next reverse-engineering target:

```text
analysis/jadx/sources/p367g7/C7580a.java
```

## Codex Task

1. Read the complete file.
2. Locate all serialization and parsing methods.
3. Identify:

   * frame header;
   * payload layout;
   * AM type;
   * node ID;
   * message length;
   * checksum or CRC;
   * byte order;
   * incomplete-message handling.
4. Open every referenced helper class.
5. Compare critical methods with smali.
6. Produce:

```text
docs/frame-format-draft.md
analysis/protocol/frame_fields.csv
tools/packet_parser/frame.py
tests/test_frame_parser.py
```

7. Do not transmit anything to `/dev/ttyUSB0` yet.

---

# 26. Definition of Project Completion

The project is complete when the independent client can perform all of the following without the official Android application:

```text
detect and connect to the sensor
identify generation and model
read node ID
read serial number
read firmware and hardware versions
read live X/Y/Z measurements
read temperature and battery state
download all historical data
read all configuration
backup configuration
change sampling interval
change node ID
set device time
configure channels and alarms
read and restore calibration
configure Bluetooth
configure radio and LoRa
reboot the sensor
factory reset and restore configuration
verify firmware image compatibility
update firmware
recover from an interrupted update
generate complete logs and reports
```

All protocol fields, commands, message types, firmware procedures, and recovery procedures must be documented and reproducible.
