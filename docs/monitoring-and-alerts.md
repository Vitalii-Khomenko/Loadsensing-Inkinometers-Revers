# Local Monitoring and Alerts

Last updated: 2026-07-15

## Purpose

The local service can continuously acquire a directly attached sensor without a phone, gateway, or cloud. It persists decoded values in SQLite, evaluates local engineering thresholds, and keeps enough job state to resume interrupted sensor-history imports.

## Data flow

```text
TIL90 over CP2102N
  -> serialized DeviceService read
  -> MonitoringService or HistoryManager
  -> MonitoringStore (SQLite/WAL)
  -> AlertEngine
  -> localhost API and readable browser tables/CSV
```

Manual reads, background monitoring, history recovery, backup, and configuration all share the same process lock. A background read waits for a manual operation instead of opening a competing serial session.

## SQLite contents

| Table | Purpose | Deduplication or lifecycle |
|---|---|---|
| `samples` | X/Y/Z angle, standard deviations, temperature, source | Unique node ID and sensor timestamp |
| `health` | Battery, temperature, uptime, firmware, source | Unique node ID and sensor timestamp |
| `alerts` | Threshold event audit | At most one open event per node/rule; resolved rows retained |
| `history_jobs` | Range, cursor, bounds, progress, and last error | One durable row per import request |
| `settings` | Monitoring intervals, retention, and rules | One current monitor configuration |

File-backed databases enable WAL and a ten-second busy timeout. All access inside the process is protected by a reentrant lock. The normal API limits table results, and CSV export returns at most 10,000 matching measurements.

## Scheduling and recovery

- monitoring defaults to disabled, 60-second measurement polling, 300-second health polling, and 365-day retention;
- the approximately ten-second physical live acquisition establishes the ten-second minimum poll setting;
- serial/OS failures use a bounded reopen retry for idempotent reads only;
- monitoring records its last success, last error, and next due epochs;
- retention cleanup runs at most once per day;
- a history job commits only complete chunks and pauses on any incomplete result;
- resume starts at the last uncommitted cursor; SQLite uniqueness suppresses repeated records.

## Alert semantics

Supported rules are absolute X/Y/Z angle, X/Y/Z rate of change, low battery, sensor error code, and missing measurements. Empty numeric settings disable that rule. An active condition creates or updates one open row. A clear condition resolves that row. Acknowledgement records review but does not change whether the condition is active.

Rate is calculated from consecutive stored samples using their sensor timestamps. Missing-data age also uses the latest sensor timestamp. The Linux host clock therefore needs normal time synchronization, and sensor clock drift should be assessed before relying on tight timing thresholds.

## Operational boundary

This feature is not a certified safety alarm or a substitute for an engineered site monitoring system. It has no remote notification transport, redundant collector, signed audit log, high-availability database, independent watchdog, or railway safety certification. Those require a separate product and site risk assessment.

The complete background path was physically smoke-tested against node `101677` using an in-memory database: monitoring started through the localhost API, stored one ordinary live sample and one health record, reported no error or open alert, and stopped cleanly. Persistent multi-hour operation and deliberate physical disconnect/reconnect remain separate endurance tests.
