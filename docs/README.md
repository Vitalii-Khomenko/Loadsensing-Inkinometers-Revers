# Documentation Index

Last updated: 2026-07-22

Evidence labels used in this project:

- **Static-confirmed**: recovered from APK Java/smali and cross-checked where decompilation disagreed.
- **Synthetic-tested**: implemented and exercised with constructed byte sequences, but not a physical sensor.
- **Capture-pending**: requires traffic or displayed values from the official application and the physical G6 sensor.

## Read in this order

| Document | Contents | Status |
|---|---|---|
| `protocol.md` | Consolidated framing, headers, response codes, and coverage | Hardware-confirmed read-only core |
| `frame-format-draft.md` | Detailed DLE framing and protocol-v2 header | Hardware-confirmed on physical G6 |
| `message-types.md` | 60 response AM types and primary TIL90 paths | Static-confirmed |
| `read-only-message-formats.md` | Decoded TIL90 response payload layouts | Static-confirmed and synthetic-tested |
| `configuration-ids.md` | All 27 configuration identifiers | Static-confirmed |
| `history-protocol.md` | Stored interval, historical stream, and resumable SQLite import | Physical core confirmed; importer synthetic-tested |
| `firmware-inventory.md` | Firmware-directory inventory, G6/G7 mapping, and exact-image recovery | G6 2.81 reinstallation hardware-confirmed |
| `passive-capture-plan.md` | Optional official-app comparison using wireless ADB | Still useful if app/display comparison is needed |
| `cli-usage.md` | Safe Linux CLI commands and serial prerequisites | Implemented and hardware-tested |
| `maintenance-cli.md` | Reboot, rollback validation, factory reset, post-reset restore, and firmware recovery commands | Hardware-confirmed on node 101677 |
| `web-app.md` | Local browser UI, monitoring, alerts, resumable history, USB diagnostics, backup/restore, and security boundary | Implemented; write subset hardware-tested |
| `docker-deployment.md` | Linux Docker build, USB hotplug, automatic monitoring, persistence, and security | Container smoke-tested without hardware |
| `node-identity.md` | Writable protocol node ID versus factory identity and deeper-change boundary | Static-confirmed; physical node-ID change blocked |
| `monitoring-and-alerts.md` | SQLite schema, acquisition flow, alert lifecycle, scheduling, and operational limits | Implemented and synthetic-tested |
| `smartphone-connection-recovery.md` | APK USB flow, phone/Linux troubleshooting, read-only recovery, reset and firmware boundaries | Static-confirmed and implemented where safe |
| `remaining-work.md` | Preserved backlog, required evidence, gateway dependencies, and productization work | Current backlog |
| `android-feature-parity.md` | Android function map and explanation of 10-second local reads versus radio reporting limits | Static-confirmed; implementation roadmap |
| `gateway-feasibility.md` | Edge versus LoRaWAN gateway options, difficulty, dependencies, and regional safety | Static analysis plus official product references |
| `multi-sensor-wired.md` | Ten-sensor USB topology, identity safeguards, concurrent reads, and validation plan | Architecture documented; implementation pending |
| `radio.md` | Physical G6 radio values, gateway model, and password boundary | Hardware-confirmed |
| `radio-profiles.md` | All 20 original Android regional profiles and the current sensor match | Static-confirmed; current EUROPE match hardware-confirmed |
| `testing-plan.md` | Completed, safe-next, and scope-expanding tests | Current plan |
| `write-validation-gates.md` | Exact prerequisites, rollback controls, equipment and order for active/write tests | Current execution gate |

Machine-readable registries live in `analysis/protocol/`. The parser implementation lives in `tools/packet_parser/`. The dated completion record is `ROADMAP.md` in the repository root.

The repository-wide English-only authoring rule is defined in `AGENTS.md` and enforced by `tests/test_language_policy.py`.

Reference-session storage rules and a metadata template live in `captures/`.

## Known validation boundary

Direct Linux evidence now proves physical product code `0x4E`, use of the upper node-ID nibble, request/response framing, and the core scale decoders. Exact sequence semantics and agreement with the official application's displayed values remain open.
