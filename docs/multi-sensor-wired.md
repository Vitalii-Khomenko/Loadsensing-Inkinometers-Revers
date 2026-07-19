# Wired Multi-Sensor Operation

Last updated: 2026-07-15

## Feasibility

Connecting ten TIL90 sensors by USB/UART adapters to one Linux computer is a realistic topology for fast, local measurements of selected points. The serial traffic is very small compared with USB full-speed capacity. The limiting factor is the sensor's measurement time, not USB bandwidth.

The current CLI and browser service support one selected serial port. Multi-sensor support has not yet been implemented, but the existing `DeviceService` already provides the correct per-device transaction lock. A manager can create one service instance per port and run independent sensor reads concurrently.

The physical reference sensor required approximately ten seconds for one fresh live-reading transaction. Therefore:

- ten sequential reads would take approximately 100 seconds;
- ten concurrent reads should normally complete as one approximately 10–12 second batch;
- this does not prove that one sensor can produce fresh readings faster than its own acquisition cycle.

The exact batch time must be measured on the final hubs, cables, computer, and ten sensors.

## Recommended topology

```text
Linux computer
  |-- powered USB hub A
  |     |-- sensor 1 adapter
  |     |-- sensor 2 adapter
  |     `-- ...
  `-- powered USB hub B
        |-- sensor 6 adapter
        `-- ... sensor 10 adapter
```

Use powered, good-quality hubs and verify their total current rating against the complete connected load. Two hubs reduce port-count pressure and make cable management easier, although they do not eliminate the computer as a common failure point. A passive hub should not be assumed to power ten interfaces reliably.

Ordinary USB cable length is limited. The USB-IF lists maximum full-speed cable lengths by connector type, including 5 m for Standard-B, 4.5 m for Mini-B, 2 m for Micro-B, and 4 m for USB-C. For more distant measurement points, use a suitable active/fibre USB extension, isolated serial-over-Ethernet hardware, or a small Linux collector close to the sensors instead of chaining unqualified extension cables.

For sensors mounted on separate structures or exposed outdoor equipment, assess ground-potential differences, surge/lightning exposure, ingress protection, and USB isolation. Provide strain relief so cable force does not bias the inclinometer or move its mounting.

## Railway distances of 50–100 metres

A passive 50–100 m USB cable is not a valid solution. There are three technically different ways to cover this distance:

| Method | Demonstrated distance | Suitability near railway infrastructure |
|---|---:|---|
| Passive USB cable | 2–5 m depending on connector | Not suitable for 50–100 m |
| Powered USB-over-Cat5e/6 extender pair | Up to 100 m for specified commercial systems | Technically possible in a protected installation; copper remains electrically continuous and needs an EMC, surge, grounding and environmental design |
| USB-over-fibre extender | Commercial systems specify 500 m multimode and up to 10 km single-mode | Strong electrical-isolation option, but specialised hardware is required at both ends |
| Local Linux collector plus industrial Ethernet/fibre backbone | Backbone-dependent | Recommended architecture for several distributed trackside locations |

The 100 m Cat5e claim applies only to an active extender system designed for that distance; it does not mean that a USB cable can be replaced by passive pin adapters or connected through arbitrary Ethernet equipment. Some products use dedicated point-to-point Cat cable, while others explicitly support a LAN. Verify the exact model and topology before purchase.

For ten sensors distributed along a railway, the preferred design is usually:

```text
sensor or local cluster
  -> short original USB connection
  -> protected industrial Linux collector
  -> galvanically isolated fibre/Ethernet backbone
  -> central Linux server and browser
```

This avoids running ten separate long USB links to one computer, allows a local collector to buffer measurements during a backbone outage, and limits one cable or hub failure to a small cluster. Where fibre is not possible, an industrial copper network still requires site-specific surge protection, shielding, bonding, power and EMC engineering.

Do not expose a consumer USB extender, hub, computer or connector directly beside the track. The enclosure, power supply, network equipment and installation should be selected for the railway electromagnetic and environmental conditions applicable to the actual country and site. The Advantech railway examples cite EN 50121-3-2/EN 50121-4 equipment and fibre-ring architectures, but a product citation is not a compliance assessment for this sensor system.

Before selecting equipment, record the distance and topology of every point, whether sensors are clustered, available local power, existing fibre/Ethernet, outdoor enclosure rating, grounding/bonding design, and the required behavior during power or network loss.

## Raspberry Pi collectors over Wi-Fi

A Raspberry Pi is a small Linux computer and can perform the local-collector role. The physical topology can be reduced to a short USB cable between the sensor and collector plus one local power feed:

```text
TIL90 -- short USB --> Raspberry Pi -- Wi-Fi --> access point/server
                              |
                         local power
```

The collector should run a small background service that reads the sensor, timestamps and buffers results locally, and sends them to the central browser service over authenticated TLS or MQTT. It should continue collecting during a Wi-Fi outage and upload the backlog after reconnection. The central service, not each field unit, should host the main operator interface.

Possible hardware tiers, using manufacturer list prices available on 2026-07-15:

| Tier | Base computer price | Appropriate use | Important limitations |
|---|---:|---|---|
| Raspberry Pi Zero 2 W | USD 15 | One sensor, proof of concept, protected indoor cabinet | One 2.4 GHz Wi-Fi radio, one USB OTG data port, 512 MB RAM, consumer board without field enclosure or industrial power input |
| Raspberry Pi 4 | From USD 35 | Small cluster, development and protected cabinet | Requires separate storage, 5 V supply and enclosure; published ambient operating range is 0–50 °C |
| Revolution Pi Core | From EUR 266 excluding tax | DIN-rail industrial Linux collector | Base variants do not include Wi-Fi; external industrial network equipment may be required |
| Revolution Pi Connect with Wi-Fi | Approximately EUR 515–558 excluding tax depending on generation/configuration | More integrated industrial collector | Much higher cost; exact interfaces and environmental approvals still require model-level review |

The base-board price is not the installed point price. A deployable point also needs storage, a power converter or supply, enclosure, terminals/cable glands, surge and grounding provisions, and possibly an external Wi-Fi antenna or access point. A low-cost Raspberry Pi assembly in a protected test cabinet may be roughly EUR 50–150 in ordinary parts. A properly engineered outdoor/railway point may cost several hundred euros or more before installation; this is a planning estimate, not a supplier quotation.

Wi-Fi must be treated as a designed network, not assumed coverage. Trackside range depends on access-point placement, antennas, metal cabinets, vegetation, trains, interference and local radio rules. A metal cabinet can severely attenuate the onboard antenna. Perform a site survey at the installed antenna positions and provide external industrial access points/antennas where required. Use Ethernet, fibre or cellular where reliable Wi-Fi coverage cannot be demonstrated.

For field reliability, use a high-endurance storage card or eMMC/SSD, a read-only or power-loss-tolerant filesystem design, a hardware/software watchdog, local queue limits, automatic restart, time synchronization, and a small backup-power allowance for clean shutdown. Do not use a consumer plug-in power supply exposed outdoors; derive power through equipment appropriate to the site's available supply and protection design.

## Stable identity and location mapping

Do not identify a measurement point only by `/dev/ttyUSB0`, because Linux port numbers can change after reconnecting devices.

The currently connected CP2102N exposes both:

```text
serial: d2f9787d759ced118acf026ce259fb3e
path:   pci-0000:0b:00.0-usb-0:2:1.0
```

The multi-sensor manager should record:

- sensor node ID and product code, read from the sensor itself;
- adapter USB serial number when it is unique;
- `/dev/serial/by-id/` path;
- `/dev/serial/by-path/` path as the physical hub-port fallback;
- operator-assigned location and description.

On every connection, the program must read the sensor identity and compare it with the configured location. If an adapter has a duplicated or missing USB serial number, the program must use the physical USB path and still verify the node ID. A mismatch must be shown as an error, not silently assigned to the old location.

## Software design

The safe implementation is a multi-device manager above the existing `DeviceService`:

1. discover all matching CP2102N ports;
2. open each port independently and read identity;
3. associate node ID with the configured measurement location;
4. retain one lock and one serial connection scope per device;
5. issue live-reading requests concurrently with a bounded worker pool;
6. timestamp each request and response using the Linux host clock;
7. return partial results if one sensor times out or disconnects;
8. store raw protocol evidence alongside decoded X/Y/Z values;
9. expose per-sensor online, busy, stale, timeout, and identity-mismatch states;
10. keep all configuration writes disabled unless explicitly enabled for one identified node.

Starting requests with a small stagger can make logs and recovery clearer, but the software must measure whether this changes batch latency. One blocked port must never hold the locks of other devices.

The browser interface can then show a ten-row overview, location labels, last update age, X/Y/Z values, alarms, and a per-sensor history chart. Configuration and backup/restore operations must always display the target node ID and location before confirmation; a group restore should not be added until single-node identity safeguards are tested.

## Validation before field use

Start with two sensors and then expand to ten. Record these tests:

- port discovery and correct node-ID/location mapping across reconnects and reboots;
- swapped cables and duplicated adapter serial numbers;
- simultaneous live-read latency and timestamp spread;
- one disconnected, slow, or malformed-response sensor during a batch;
- hub power removal and recovery without confusing identities;
- continuous operation for at least 24 hours with timeout and memory statistics;
- comparison of each sensor's browser value with the existing single-device CLI;
- CSV/JSON persistence, host-clock changes, and restart recovery;
- read-only operation with radio configuration unchanged.

For important monitoring, add a watchdog, local append-only storage, disk-space limits, time synchronization, and clear stale-data alarms. This research interface should not be treated as a certified safety alarm system without an independent engineering and reliability assessment.

## Current status

The topology and required safeguards are documented, but multi-port code and multi-sensor hardware testing are pending. No sensor was opened or queried while preparing this document; only Linux udev properties for the already enumerated CP2102N were read.

Official hardware references:

- [Silicon Labs CP2102N data sheet](https://www.silabs.com/documents/public/data-sheets/cp2102n-datasheet.pdf)
- [USB-IF electrical compliance and cable-length table](https://compliance.usb.org/index.asp?UpdateFile=Electrical)
- [Icron RG2300A/RG2310A USB extension ranges](https://www.icron.com/assets/usb-2-0-rg2310a-core-datasheet.pdf)
- [Advantech railway communications examples](https://advcloudfiles.advantech.com/membership/upload/e4c57661/Intelligent%20Railway%20Solutions.pdf)
- [Raspberry Pi Zero 2 W specifications and USD 15 list price](https://www.raspberrypi.com/products/raspberry-pi-zero-2-w/)
- [Raspberry Pi 4 specifications and list price](https://www.raspberrypi.com/products/raspberry-pi-4-model-b/)
- [Revolution Pi product prices](https://revolutionpi.com/en/ordering/overview-products-and-prices)
