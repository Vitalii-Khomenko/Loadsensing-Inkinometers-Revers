# Physical Edge Gateway Local Export

Last updated: 2026-07-24

## Outcome

The connected physical gateway can collect TIL90 radio messages, retain decoded measurements locally, and deliver them to a computer without CMT Cloud or another vendor-hosted service.

The shortest supported architecture is:

```text
TIL90 sensors
  -> embedded EU868 radio
  -> Worldsensing CMT Edge gateway
  -> local Ethernet
  -> operator-owned computer
       -> FTPS/FTP server for CSV delivery, or
       -> MQTT broker for pushed messages, or
       -> Modbus TCP client for latest values, or
       -> HTTPS client for local CSV and inventory reads
```

The gateway remains necessary in this architecture because it implements the embedded radio network, authentication, message reception, decoding, storage, and sensor metadata. The computer replaces cloud transport and third-party visualization, not the radio gateway.

Worldsensing's current CMT Edge description independently states that measurements remain in the gateway, that the product works without internet, that it is accessible through local Ethernet, and that FTP/FTPS, MQTT, Modbus TCP, and APIs are supported. See:

- <https://www.worldsensing.com/product/cmt-edge/>
- <https://www.worldsensing.com/product/cloud-gateway/>

## Physical gateway identity

The following values were read from the connected gateway on 2026-07-24:

| Item | Observed value |
|---|---|
| Gateway model | `LS-G6-KIO-GW-868` |
| CMT/Data Server version | `2.11.1` |
| Gateway and radio network ID | `31253` |
| Radio region | `Europe` |
| Downlink | Enabled |
| Registered nodes | 12 |
| Registered node model | `LS-G6-TIL90-I` |
| Registered node firmware | `2.81` |
| Local web server | lighttpd `1.4.76` on HTTP/HTTPS |
| SSH server | OpenSSH `7.5` on TCP 22 |

The registered nodes were offline at the observation time because none had delivered a message during the gateway's 15-hour online threshold. Historical measurements remained present and downloadable.

The gateway administrator password, radio network password, cellular identifiers, and any exported secrets are deliberately absent from this repository.

## USB local-access path

The gateway's USB local-access connection enumerated in Linux as:

```text
USB device: 0b95:1790 ASIX AX88179
Linux interface: enxc8a362c08af5
Linux address: 169.254.0.5/16
Gateway address: 169.254.0.1
Gateway MAC: 94:05:bb:10:11:7c
```

The local interface is available at:

```text
https://169.254.0.1/dataserver/
```

HTTPS uses a self-signed certificate with common name `worldsensing-gw-31253`. The web application uses HTTP Basic authentication with realm `loadsensing`. The supplied administrator account was physically validated against the web application. The password must remain outside Git, shell scripts, command examples, logs, and exported reports.

USB is a network-management path, not a serial stream of raw TIL90 measurements. It nevertheless exposes the same local CMT Edge web application and allowed a complete HTTPS CSV download.

## SSH result

TCP 22 is open and identifies as OpenSSH `7.5`. The observed ED25519 host-key fingerprint is:

```text
SHA256:96gxBDUegtvHLgm5rYXFxVD84mAhRbuPTA6hDjMagtc
```

The web administrator account was rejected by SSH. A single test of the standard `root` account with the same supplied password was also rejected. No username enumeration, password guessing, key extraction, bypass, exploit, or configuration change was attempted.

The result shows that web administration and operating-system SSH accounts are separate. SSH is not required for the supported local-export design.

## Local measurement evidence

The gateway web page displayed retained decoded `til90ReadingsV1` messages containing:

- sensor temperature;
- X, Y, and Z tilt;
- per-axis standard deviation;
- sensor measurement time and gateway receipt time;
- gateway and network identity;
- RSSI, SNR, frequency, spreading factor, sequence counter, and frame count.

It also displayed `healthV2` messages containing firmware, uptime, temperature, input voltage, measurement time, and radio metadata.

A TIL90 CSV was physically downloaded over the isolated USB network using this authenticated route pattern:

```text
/dataserver/current/reading/<node-id>/til90/<node-id>-readings-current.csv
```

The health route pattern is:

```text
/dataserver/current/health/<node-id>/health/<node-id>-health-current.csv
```

The TIL90 file contained gateway and node metadata followed by these measurement columns:

```text
Date-and-time
Temp-<node>
XaxisTilt-<node>-Ch0
YaxisTilt-<node>-Ch1
ZaxisTilt-<node>-Ch2
XaxisStd-<node>-Ch0
YaxisStd-<node>-Ch1
ZaxisStd-<node>-Ch2
```

The page can additionally define custom compacted CSV files with selected columns from multiple nodes. New nodes are not automatically added to an existing custom file.

The authenticated inventory endpoint was also physically read:

```text
/dataserver/api/v1/inventory/networks/<network-id>
/dataserver/api/v1/inventory/nodes/<node-id>
```

These inventory routes return configuration metadata. No general measurement REST route was identified during this session, so automated measurement ingestion should initially use the proven CSV route, FTP/FTPS, MQTT, or Modbus rather than inventing an undocumented API.

## FTP and FTPS

The `FTP client` page configures the gateway as an outbound client. The computer must run the receiving server; the gateway is not offering an FTP server on TCP 21.

The physical page supports:

- enabled/disabled state;
- destination hostname or IP address and port;
- anonymous or username/password authentication;
- FTP;
- FTPS with certificate validation;
- FTPS while ignoring a self-signed certificate;
- extended passive or passive transfer;
- append to the current file;
- a unique file for every upload;
- overwrite of the previous upload;
- independent destination paths for TIL90 readings, gateway/node health, custom compacted data, and other supported device families;
- `Save and test` validation against the destination server.

At inspection time FTP was disabled, its destination and credentials were empty, and every data-family export was disabled. The selected output policy was append-to-file. No gateway setting was changed and no test upload was sent.

For an unattended local installation, FTPS with a certificate trusted by the gateway is preferred. Plain FTP is functional on an isolated LAN but exposes its username, password, and data to any device able to observe that network. The `ignore self-signed certificates` option weakens server authentication and should be reserved for a controlled acceptance test.

The precise retry, batching, and upload cadence are not exposed by the inspected page and still require a physical transfer test. File ingestion must therefore be idempotent and tolerate a repeated file, repeated rows, delayed delivery, and reconnection.

## MQTT

The gateway contains an outbound MQTT pusher that explicitly states that it pushes data received from nodes to an MQTT server. It supports:

- broker hostname and port;
- client ID and topic;
- CA validation using an uploaded or system certificate, or no validation;
- username and password;
- client certificate and private key;
- optional notification topic.

MQTT was disabled and no broker or topic was configured. TCP 1883 and 8883 were filtered on the gateway because this component is an outbound client, not a local broker.

For a near-real-time local web service, the preferred future path is:

```text
gateway MQTT client -> broker on the operator computer -> parser/database -> browser service
```

The exact JSON schema, retained-session behavior, queue depth, retry policy, ordering, and duplicate behavior must be captured from a controlled local-broker test before production use.

## Modbus TCP

The built-in Modbus TCP gateway returns the latest measurement received from each mapped node. The physical page supports:

- disabled;
- enabled on wired interfaces only;
- enabled on all interfaces, including cellular WAN;
- per-node Modbus Unit IDs from 1 through 246;
- reserved Unit ID 247 for node status;
- stale-message timeouts from 30 seconds through 24 hours, or `Never`.

The current configuration is disabled, uses a 12-hour timeout value, and has no node-to-unit mappings. TCP 502 was consequently filtered during the local port check.

Modbus is appropriate for PLC/SCADA polling of the latest value. It is not the preferred historical archive because the interface deliberately returns the latest received value until it becomes stale. The model-specific register map must be obtained from the applicable Worldsensing user guide before enabling it.

## Network settings for internet-independent operation

The gateway currently uses automatic backhaul selection and has an active cellular connection. Its network watchdog is enabled, and automatic NTP points to `pool.ntp.org`.

The gateway page explicitly instructs operators to disable the network watchdog when no internet connection is available. Otherwise, a deliberate offline deployment can be treated as a network failure and trigger gateway reboots.

Before moving to a direct Ethernet-only deployment:

1. export and preserve the current gateway configuration;
2. record a recovery route through the USB address `169.254.0.1`;
3. choose an unused private subnet for the computer and gateway;
4. configure a static Ethernet address on the gateway, because a direct cable normally has no DHCP server;
5. configure the computer in the same subnet;
6. disable the internet network watchdog;
7. use a local NTP server or explicitly define the clock-maintenance plan;
8. keep the gateway web UI bound to the private/local network and restrict it with the computer firewall;
9. configure one supported export and perform its built-in connection test;
10. wait for at least one complete sensor reporting period;
11. disconnect or disable cellular/internet only during an attended acceptance test;
12. prove reception, local storage, export, restart behavior, deduplication, and recovery.

Example addressing only:

```text
gateway Ethernet: 192.168.50.1/24
computer Ethernet: 192.168.50.2/24
local export host: 192.168.50.2
```

These values must not be applied if they conflict with the site network. The gateway page states that Ethernet configuration changes are applied after reboot.

### Exact administration pages

| Purpose | CMT Edge page | Required offline action |
|---|---|---|
| Network watchdog | `Configuration -> Internet` | Clear `Activate network Watchdog`. The page states that it reboots after 40 minutes of unsuccessful internet checks. |
| Backhaul selection | `Configuration -> Internet` | Select `Manual Configuration`, then `Ethernet with DHCP` or `Ethernet with static IP`; do not leave cellular fallback selected. |
| Time synchronization | `Configuration -> Internet` | Replace default `pool.ntp.org` with an operator-owned local NTP server. |
| Email delivery | `Configuration -> Internet` | Do not use the default internet SMTP service; use a local SMTP server or leave email delivery unused. |
| Remote tunnel | `Configuration -> Remote access` | Clear `Activate remote tunnel` after cellular isolation and local recovery access are ready. |
| Cellular APN | `Configuration -> Cellular modem` | This page configures SIM PIN and APN but exposes no modem-disable switch on version 2.11.1. |

Disabling the remote tunnel while leaving a cellular public address active is not sufficient. The physical page warns that disabling the tunnel also removes its cellular firewall protection. A strict offline deployment must first prevent cellular internet access by removing or deactivating the SIM/service, then disable the tunnel.

Connecting the gateway to an ordinary home router with DHCP gives it a LAN address but normally also gives it an internet default route. For a strict no-internet deployment, use one of:

- a direct gateway-to-computer cable with static addresses and no internet route;
- an isolated VLAN that allows only the collector computer;
- a router firewall rule that denies all gateway internet egress while allowing local collector traffic.

Entering a deliberately invalid APN is not a reliable or maintainable modem-disable mechanism.

The non-secret deployment intent is recorded in `config/gateway-local.example.yaml`. It is a planning template and is not yet consumed by the Docker service. Addresses are examples, all exports remain disabled, and credentials are represented only by environment-variable names.

## Does local Ethernet increase measurement frequency?

Local Ethernet reduces the delay and uncertainty between gateway reception and delivery to the computer. MQTT can expose a received message quickly, and local FTPS/HTTPS avoids cellular and cloud latency. It does not make a sensor transmit more often and does not increase the gateway's radio reception capacity.

The data path has two separate rates:

```text
sensor reporting period and radio capacity
  -> gateway receives and decodes
  -> Ethernet export latency
```

Ethernet improves only the second stage. A faster sensor reporting configuration affects the first stage and must remain within radio airtime, collision, spreading-factor, retry, health-message, downlink, and gateway-processing limits.

Worldsensing's current 4G Rugged Gateway page publishes an upper bound of 30 messages per minute for a single-gateway Edge deployment:

<https://www.worldsensing.com/product/cloud-gateway/>

For 200 sensors, the ideal average before health messages and retries is:

| Sensor reporting period | Average reading messages per minute | Fraction of the published 30/minute upper bound |
|---:|---:|---:|
| 60 minutes | 3.33 | 11% |
| 30 minutes | 6.67 | 22% |
| 15 minutes | 13.33 | 44% |
| 10 minutes | 20.00 | 67% |
| 5 minutes | 40.00 | 133% |
| 1 minute | 200.00 | 667% |

This simple average is optimistic. It excludes health packets, retries, downlinks, multi-frame messages, unequal spreading factors, synchronized transmission bursts, interference, and loss. Thirty messages per minute is a published upper bound, not a safe continuous design target.

For a 200-sensor first deployment, 15-minute reporting is a reasonable conservative starting hypothesis because its ideal data load is about 44% of the published upper bound. Ten minutes may be feasible but requires a controlled load test and scheduling analysis. Five minutes exceeds the published single-Edge bound even before overhead and is not a valid one-gateway plan.

The physically connected gateway currently has only 12 registered sensors, so support for 200 nodes on this exact software/license combination is not yet proven. Network-size licensing, storage retention, UI performance, radio-slot behavior, and export backpressure must be confirmed before accepting a 200-node design.

## Separate credentials

Three different secrets must not be confused:

1. the CMT Edge web administrator password;
2. the embedded radio network password used to authenticate sensors;
3. the FTP, FTPS, or MQTT destination credentials owned by the operator computer.

The web administrator password does not provide the radio network password. The gateway radio page states that its network password cannot be retrieved and must be recorded when assigned.

The connected gateway uses radio network ID `31253`. The previously tested repository reference sensor `101677` was last read with network ID `27484`, and it is not one of the 12 nodes registered in gateway `31253`. It will not be assumed to communicate with this gateway until it is deliberately provisioned with the gateway's correct radio network ID, correct radio password, EUROPE profile, and compatible reporting settings.

## Gateway-to-sensor downlinks

The physical `Configuration -> Radio` page separates gateway-local changes from messages sent to nodes.

### Confirmed downlink categories

The page states that disabling gateway downlinks prevents these four operations:

| Downlink category | Meaning | Physical UI evidence |
|---|---|---|
| Node time | Synchronize or correct the sensor clock | Listed on the Radio page |
| Reporting period | Change the persistent interval at which a node reports | Listed on the Radio page; the network page supports selecting multiple nodes |
| Spreading factor | Change the node's radio spreading factor | Listed on the Radio page |
| Sensor configuration | Deliver product-specific persistent settings | Listed generically; the exact fields depend on node model and firmware |

The network page additionally provides:

- multi-select `Change reporting period`;
- multi-select `Cancel all downlinks`, whose confirmation text specifically refers to pending reporting-period changes.

This is evidence of per-node queued configuration, not evidence of one unauthenticated RF broadcast that immediately reconfigures every sleeping sensor. Battery nodes normally receive a queued downlink in association with their radio communication window, so completion must be verified per node after a subsequent message.

For the physical G6 TIL90, the direct USB protocol independently confirms persistent configuration families for sampling, channel flags, radio settings, network authentication, time, and other maintenance operations. That does not prove that every USB operation has a corresponding CMT Edge downlink. Only the four categories named by the gateway UI are treated as remotely supported here.

No physical UI or captured gateway traffic has confirmed remote sensor:

- network-ID/password replacement;
- region/frequency-plan migration;
- node-ID change;
- reboot;
- factory reset;
- firmware update;
- calibration write.

These operations must not be inferred from the generic phrase `sensor configuration`.

### Radio-page controls that are not sensor commands

| Radio page action | Actual target |
|---|---|
| `Change country and frequency range` | Changes the gateway receiver/transmitter radio plan; the page says all sensors must already match |
| `Change radio network ID and password` | Changes gateway radio credentials; the page says all sensors must already match and the password cannot be retrieved |
| `Disable gateway downlink` | Stops this gateway from transmitting node time, reporting-period, spreading-factor, and model-specific configuration downlinks |
| `Change Lora Server parameters` | Cloud-gateway server routing; hidden on this Edge model |
| Repeater network ID/password | Repeater-local configuration; hidden on this Edge model |

Changing gateway network ID or region first can strand the existing nodes because the gateway and sensors will no longer share the same radio parameters.

## Can all sensors be switched to another gateway?

There is no confirmed `switch gateway` command and no confirmed bulk network-credential migration in Data Server 2.11.1.

Embedded Edge sensors are associated with a radio network rather than a unique physical gateway. A replacement gateway can receive the existing sensors without changing them when it is configured with the same:

- legal region and frequency plan;
- radio network ID;
- case-sensitive radio network password;
- compatible protocol and downlink behavior.

The practical same-network replacement sequence is:

1. preserve the old gateway configuration and separately retained radio password;
2. configure the replacement gateway with the identical region, frequency plan, network ID, and password;
3. import or recreate node metadata and data-export configuration as supported;
4. prevent simultaneous conflicting downlinks;
5. turn off the old gateway or disable its downlinks;
6. observe each node through at least one complete reporting period;
7. verify node ID, timestamps, RSSI/SNR, sequence continuity, duplicates, and missing messages.

The gateway page warns that two gateways with the same radio network ID in the same area can produce duplicate messages, data loss, and incorrect network behavior. It recommends a supported CMT Cloud multi-gateway architecture or disabling downlinks on one gateway for redundancy. A dual-Edge arrangement must therefore not be treated as supported seamless redundancy without an acceptance test.

If the replacement uses a different network ID or password, every sensor must be provisioned with those new values. The reviewed Edge interface offers no confirmed command to broadcast new credentials to all old-network sensors. For a 200-node migration, the currently validated route is attended per-sensor USB provisioning using the guarded batch workflow, with identity, acknowledgement, readback, and a final gateway-reception check for every node.

The web administrator password is not the radio password and cannot be used for this migration.

## Recommended implementation order

1. Validate HTTPS pull of current TIL90 and health CSV over the physical RJ45 interface.
2. Build a read-only importer that records file hash, node ID, measurement timestamp, and source row for deduplication.
3. Configure FTPS from the gateway to an operator-owned server and validate backlog/retry behavior.
4. Capture MQTT messages from a local broker and compare them against the same CSV rows.
5. Select FTPS for durable batch transfer, MQTT for low-latency streaming, or both.
6. Enable Modbus only if a PLC/SCADA consumer requires it and the official TIL90 register map is available.
7. Perform an attended internet-disconnection test after watchdog and time synchronization have been made offline-safe.

No gateway configuration, radio setting, node registry, FTP setting, MQTT setting, Modbus mapping, reboot, or firmware state was changed during this investigation.
