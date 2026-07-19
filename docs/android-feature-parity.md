# Android Application Feature-Parity Notes

Last updated: 2026-07-15

## Conclusion

A browser interface can reproduce most direct node-management functions of the Android application. It cannot be a fully equivalent replacement using only a USB sensor connection because several Android workflows also use Worldsensing cloud/CMT services, gateway state, operator credentials, and model-specific firmware files.

The correct target is therefore:

1. full parity for safe functions implemented by direct serial protocol;
2. clearly separated optional integrations for gateway/backend functions;
3. model-aware hiding of functions that do not apply to `LS_G6_INC360`;
4. isolated destructive/recovery tools that are never exposed as ordinary dashboard actions.

## Why 10 seconds and 30 minutes are both correct

These values refer to related but different operating constraints.

### On-demand measurement

`Inc360Node.java` declares:

```text
MAX_TAKE_READING_TIME_SEC = 10
MIN_SAMPLING_RATE_TIME_SEC = 10
```

The direct request body `02` asks the node to take a reading now. It is not a persistent reporting configuration. Physical captures show that replies arrive after approximately 9–10 seconds:

```text
10:49:47.365 TX -> 10:49:57.011 RX
10:49:57.511 TX -> 10:50:07.162 RX
10:50:07.663 TX -> 10:50:16.711 RX
```

The browser's current live button uses this on-demand request. Its JavaScript timer is only a host-side request schedule. It does not prove that the sensor stores or transmits a LoRa message at that rate. Because a physical reading takes close to ten seconds, the current three-second browser timer can queue requests behind the serial lock. A future UI revision should schedule the next request only after the previous response completes.

### Persistent sampling/reporting configuration

Configuration AM `0x82` stores a persistent period in seconds. The physical node initially reported 300 seconds and reports 3600 seconds after official post-repair gateway programming. The Android selection list contains 30, 60, 120, 300, 600, 900, 1800 seconds and longer values, although the node library itself reports a standalone hardware minimum of 10 seconds.

The Android screen labels this value `reporting period (reading periodicity)`. In standalone mode the library returns the node minimum. When a radio network is configured, it calculates:

```text
minimum = max(node standalone minimum, radio slot capacity)
radio slot capacity = minimum seconds per message × selected network-size bucket
```

For the ordinary region configuration recovered from the APK:

```text
minimum seconds per message: 7.5
network-size buckets: 4, 8, 40, 240, 480, 2000
```

The requested network size is rounded up to one of those buckets. A selected size from 41 through 240 therefore produces:

```text
7.5 × 240 = 1800 seconds = 30 minutes
```

This is one way the Android programming wizard can produce a 30-minute minimum while the same INC360 hardware returns a directly requested local measurement in about ten seconds. The limit protects radio capacity and collision/duty-cycle planning; it is not the sensor's measurement-engine limit.

### Important correction after the 10-sensor observation

Ten physically installed sensors do not automatically mean the application calculates with network size 10. The APK does not discover or count active nodes for this calculation. It uses the number entered in the wizard and stores it as `PREF_NETWORK_SIZE`. The `Set last configuration` workflow later reads that stored value rather than querying a gateway or sensor count.

For the recovered Edge/FCC rules, an entered size of 10 rounds up to bucket 40:

```text
40 × 7.5 = 300 seconds = 5 minutes
```

Therefore a persistent 30-minute minimum after explicitly entering `10` is not explained by the ordinary Edge formula alone. Current hypotheses are:

1. `PREF_NETWORK_SIZE` still contains 240 from an earlier configuration, especially in the `Set last configuration` workflow;
2. the selected radio profile is different from Edge/FCC and uses a different bucket/capacity table;
3. a separate application/library version or server-provided profile enforces 1800 seconds;
4. the displayed installed-node count is not the value passed to `getMinSamplingRate()`.

The adapter simply receives one computed minimum and disables every period below it. It does not contain a special hard-coded 30-minute rule for INC360. To distinguish these hypotheses, a future comparison should record the exact wizard path, radio type, region, network-size field, whether `Set last configuration` was used, and the returned minimum visible in logcat.

### Local sampling mode

The Android app also has a separate `TakeLocalSamplesActivity`. It sends a miscellaneous local-sampling command with duration and period. The application explicitly warns that no radio messages are sent while this mode is enabled. This is a temporary diagnostic stream, distinct from the normal persistent reporting period and from one-shot request `02`. A bounded trial of the exact APK packet on this G6 INC360 firmware 2.81 returned `INVALID_SIZE`; therefore the feature is not currently available for this physical node through that common BaseNode path.

## Android feature map

| Android function | Direct USB possible | Current browser status | Important dependency or risk |
|---|---:|---|---|
| USB discovery and node identification | Yes | Implemented | Read-only |
| Health, battery, temperature, uptime, firmware/hardware | Yes | Implemented | Read-only |
| Take one live sample | Yes | Implemented | One acquisition takes up to about 10 seconds |
| Continuous local diagnostic sampling | APK path exists; G6 trial rejected | Guarded trial implemented | Firmware 2.81 returned `INVALID_SIZE`; no alternate variants should be probed without static evidence |
| Read sampling/reporting period | Yes | Implemented | Read-only |
| Change sampling/reporting period | Yes | Implemented | `300 → 301 → 300` physically validated |
| Read enabled X/Y/Z channels | Yes | Implemented | Read-only |
| Change enabled X/Y/Z channels | Yes | Implemented behind write gate | Z disable/live/readback/restore physically validated |
| Read calibration coefficients | Yes | Implemented | Read-only |
| Change calibration | Not established | Blocked | Official INC360 screen/library only reads calibration; no write method found |
| Read radio region, channels, SF, TX power, address, network ID, join values | Yes | Implemented | Read-only |
| Configure radio/network/password | Yes for embedded mode | Implemented behind write gate | EU868 restore and separate network-ID/password replacement physically validated; RF reception still needs a gateway |
| Setup wizard and network-size validation | Yes locally | Not implemented | Cloud/CMT choices require optional backend integration |
| Link check / radio coverage test | Partly | Blocked | Actively transmits; online result can require gateway/backend access |
| Read stored-data interval | Yes | Implemented in CLI/API | Read-only |
| Download bounded historical data | Yes | Implemented in CLI | Two-hour/18-record recovery physically validated with strict bounds |
| Export/import node configuration | Yes | Implemented | Normal restore plus complete post-factory-reset radio/auth restore physically validated |
| Set node clock | Yes | Blocked | Persistent state change; time source and verification required |
| Reboot | Yes | Web and maintenance CLI | Uptime reset and unchanged configuration physically validated |
| Factory reset | Yes | Implemented behind write gate | Physical reset, full restore, reboot, and zero-difference comparison passed |
| Change node ID / metadata | Mixed | Blocked | Node ID is persistent; metadata may be app/backend-only |
| Firmware version check | Yes | Implemented as identity read | Read-only |
| Firmware update/recovery | Yes for mapped 2.81 image | Implemented behind write gate | Exact-image reinstallation physically passed; no newer normal G6 image exists in this APK |
| Bluetooth configuration | Model-dependent | Read attempt available but unsupported | Physical firmware 2.81 returned `INVALID_INPUT_PARAM` |
| Alarm thresholds | Different product | Not applicable | Normal product `0x4E` uses AM `0x9A`; alarm product uses another configuration |
| Laser, VW, GNSS, DIG, analog settings | Different products | Not applicable | Android app is multi-product; these screens must not appear for this node |
| Cloud registration, tenants, network lists, gateway online status | No, not USB-only | Not implemented | Requires official APIs, credentials, internet, and authorization |

## Relevant recovered code

- `com/worldsensing/.../nodes/inc360/Inc360Node.java`: product capabilities, 10-second standalone minimum, channel read/write path.
- `.../ui/fragments/SamplingRateFragment.java`: selectable reporting periods and minimum-value filtering.
- `.../nodes/BaseNode.java`: radio-aware minimum calculation, slot-time calculation, one-shot/local sampling, configuration, history, time, reboot, and radio methods.
- `.../config/radios/RadioRegionsConfigs.java`: network-size buckets and regional minimum seconds per message.
- `.../ui/screens/takelocalsamples/TakeLocalSamplesActivity.java` and `C6748a.java`: temporary local sampling lifecycle.
- `.../ui/screens/main/MainActivity.java`: entry points for sample, settings, calibration, data download, radio coverage, time, reboot, factory reset, node ID, and firmware update.
- `.../ui/screens/setupwizard/`: radio type, region, network size, authentication, reporting period, and node configuration workflow.

## Recommended parity sequence

### Stage 1 — Complete safe local monitoring

- correct live polling so requests cannot queue;
- add explicit one-shot versus continuous labels;
- show persistent sampling period separately from on-demand acquisition time;
- add bounded physical history recovery and CSV/JSON export;
- reproduce the APK's connection gates as a readable recovery assessment and keep destructive actions in separately confirmed maintenance workflows;
- add device clock comparison without setting it;
- expose a model/capability matrix in the UI.

### Stage 2 — Reversible configuration

- physically validate channel configuration with before/readback/rollback evidence;
- reproduce the Android reporting-period list and calculate the radio/network-size minimum;
- add configuration profiles and stronger diff presentation;
- recover and validate every radio write serializer and authentication step before exposing radio restore.
- treat calibration coefficients as read-only unless a separate authorized factory/service protocol and physical calibration procedure are recovered.

### Stage 3 — Active diagnostics

- recover the exact temporary local-sampling command and stop/state query;
- implement a watchdog that always attempts to exit local mode;
- validate link check independently from online coverage tests;
- add gateway/backend connectors only as optional modules with explicit credentials.

### Stage 4 — Disruptive maintenance

- set time and reboot only after reconnect verification is automated;
- keep node-ID research blocked and factory reset in a separate maintenance mode;
- restrict firmware flashing to the physically proven exact G6 2.81 image and transport.

## Current conclusion for node 101677

After official post-repair programming, the node is configured with persistent sampling period 3600 seconds, LoRa slot time 3000 seconds, enabled embedded `EU868_V1`, and network ID `27484`. The roughly ten-second responses seen in the browser remain fresh, requested USB measurements, not scheduled LoRa transmissions. The earlier 30-minute Android limit still requires capture of the wizard's stored network size/path if its exact UI cause is to be resolved; the final selected one-hour period does not reveal the disabled-option calculation.
