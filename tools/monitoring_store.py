"""Thread-safe SQLite storage for measurements, health, alerts, and history jobs."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any


DEFAULT_MONITOR_CONFIG = {
    "enabled": False,
    "measurement_interval_seconds": 60,
    "health_interval_seconds": 300,
    "retention_days": 365,
    "alerts": {
        "x_absolute_deg": None,
        "y_absolute_deg": None,
        "z_absolute_deg": None,
        "rate_deg_per_minute": None,
        "low_battery_v": 3.0,
        "missing_data_seconds": 300,
        "sensor_error": True,
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class MonitoringStore:
    """Own one SQLite connection and serialize its use across worker threads."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path) if str(path) != ":memory:" else None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(
            str(path), timeout=10, check_same_thread=False, isolation_level=None
        )
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.execute("PRAGMA foreign_keys=ON")
            self._db.execute("PRAGMA busy_timeout=10000")
            if self.path:
                self._db.execute("PRAGMA journal_mode=WAL")
            self._create_schema()

    def _create_schema(self) -> None:
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY, value TEXT NOT NULL
            );
            INSERT OR IGNORE INTO metadata(key, value) VALUES ('schema_version', '1');
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY, value_json TEXT NOT NULL, updated_utc TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY,
                node_id INTEGER NOT NULL,
                timestamp INTEGER NOT NULL,
                received_utc TEXT NOT NULL,
                source TEXT NOT NULL,
                x_deg REAL, y_deg REAL, z_deg REAL,
                x_stddev_g REAL, y_stddev_g REAL, z_stddev_g REAL,
                temperature_c REAL,
                error_code INTEGER,
                UNIQUE(node_id, timestamp)
            );
            CREATE INDEX IF NOT EXISTS samples_time_idx ON samples(timestamp DESC);
            CREATE TABLE IF NOT EXISTS health (
                id INTEGER PRIMARY KEY,
                node_id INTEGER NOT NULL,
                timestamp INTEGER NOT NULL,
                received_utc TEXT NOT NULL,
                source TEXT NOT NULL,
                battery_v REAL, temperature_c REAL, uptime INTEGER,
                firmware TEXT, error_code INTEGER,
                UNIQUE(node_id, timestamp)
            );
            CREATE INDEX IF NOT EXISTS health_time_idx ON health(timestamp DESC);
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY,
                node_id INTEGER NOT NULL,
                rule TEXT NOT NULL,
                severity TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('open', 'resolved')),
                message TEXT NOT NULL,
                observed REAL, threshold_value REAL,
                sample_timestamp INTEGER,
                opened_utc TEXT NOT NULL,
                updated_utc TEXT NOT NULL,
                resolved_utc TEXT,
                acknowledged_utc TEXT
            );
            CREATE UNIQUE INDEX IF NOT EXISTS alerts_one_open_rule
                ON alerts(node_id, rule) WHERE state='open';
            CREATE INDEX IF NOT EXISTS alerts_state_idx ON alerts(state, updated_utc DESC);
            CREATE TABLE IF NOT EXISTS history_jobs (
                id INTEGER PRIMARY KEY,
                node_id INTEGER,
                start_epoch INTEGER NOT NULL,
                end_epoch INTEGER NOT NULL,
                cursor_epoch INTEGER NOT NULL,
                chunk_seconds INTEGER NOT NULL,
                max_records_per_chunk INTEGER NOT NULL,
                status TEXT NOT NULL,
                chunks_completed INTEGER NOT NULL DEFAULT 0,
                records_received INTEGER NOT NULL DEFAULT 0,
                records_imported INTEGER NOT NULL DEFAULT 0,
                duplicates INTEGER NOT NULL DEFAULT 0,
                error TEXT,
                created_utc TEXT NOT NULL,
                updated_utc TEXT NOT NULL
            );
            """
        )
        if self._db.execute("SELECT 1 FROM settings WHERE key='monitor'").fetchone() is None:
            self.set_monitor_config(DEFAULT_MONITOR_CONFIG)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def get_monitor_config(self) -> dict[str, Any]:
        with self._lock:
            row = self._db.execute(
                "SELECT value_json FROM settings WHERE key='monitor'"
            ).fetchone()
        return json.loads(row[0]) if row else json.loads(json.dumps(DEFAULT_MONITOR_CONFIG))

    def set_monitor_config(self, config: dict[str, Any]) -> None:
        value = json.dumps(config, sort_keys=True, separators=(",", ":"))
        with self._lock:
            self._db.execute(
                "INSERT INTO settings(key,value_json,updated_utc) VALUES('monitor',?,?) "
                "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, "
                "updated_utc=excluded.updated_utc",
                (value, utc_now()),
            )

    @staticmethod
    def _node_id(record: dict[str, Any]) -> int:
        header = record.get("header") or record.get("inner_header") or {}
        return int(header.get("node_id", 0))

    def insert_record(self, record: dict[str, Any], source: str) -> tuple[str | None, bool]:
        data = record.get("data") or {}
        timestamp = data.get("timestamp")
        if timestamp is None:
            return None, False
        node_id = self._node_id(record)
        if not node_id and isinstance(data.get("header"), dict):
            node_id = int(data["header"].get("node_id", 0))
        received = utc_now()
        axes = data.get("axes")
        if isinstance(axes, dict):
            values: list[Any] = []
            for axis in "xyz":
                item = axes.get(axis) or {}
                values.extend((item.get("angle_deg"), item.get("stddev_g")))
            with self._lock:
                cursor = self._db.execute(
                    "INSERT OR IGNORE INTO samples(node_id,timestamp,received_utc,source,"
                    "x_deg,x_stddev_g,y_deg,y_stddev_g,z_deg,z_stddev_g,temperature_c,error_code) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (node_id, int(timestamp), received, source, *values,
                     data.get("temperature_c"), data.get("error_code")),
                )
            return "sample", cursor.rowcount == 1
        if "battery_v" in data or "uptime" in data:
            firmware = None
            if data.get("firmware_major") is not None:
                firmware = f"{data['firmware_major']}.{data.get('firmware_minor', 0)}"
            with self._lock:
                cursor = self._db.execute(
                    "INSERT OR IGNORE INTO health(node_id,timestamp,received_utc,source,"
                    "battery_v,temperature_c,uptime,firmware,error_code) VALUES(?,?,?,?,?,?,?,?,?)",
                    (node_id, int(timestamp), received, source, data.get("battery_v"),
                     data.get("temperature_c"), data.get("uptime"), firmware,
                     data.get("error_code")),
                )
            return "health", cursor.rowcount == 1
        return None, False

    def measurements(
        self, start_epoch: int | None = None, end_epoch: int | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        clauses, values = [], []
        if start_epoch is not None:
            clauses.append("timestamp>=?"); values.append(start_epoch)
        if end_epoch is not None:
            clauses.append("timestamp<=?"); values.append(end_epoch)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self._lock:
            rows = self._db.execute(
                f"SELECT * FROM samples{where} ORDER BY timestamp DESC LIMIT ?",  # noqa: S608
                (*values, min(max(limit, 1), 10000)),
            ).fetchall()
        return [dict(row) for row in rows]

    def latest_sample(self, node_id: int | None = None) -> dict[str, Any] | None:
        sql, args = "SELECT * FROM samples", ()
        if node_id is not None:
            sql += " WHERE node_id=?"; args = (node_id,)
        with self._lock:
            row = self._db.execute(sql + " ORDER BY timestamp DESC LIMIT 1", args).fetchone()
        return dict(row) if row else None

    def latest_health(self, node_id: int | None = None) -> dict[str, Any] | None:
        sql, args = "SELECT * FROM health", ()
        if node_id is not None:
            sql += " WHERE node_id=?"; args = (node_id,)
        with self._lock:
            row = self._db.execute(sql + " ORDER BY timestamp DESC LIMIT 1", args).fetchone()
        return dict(row) if row else None

    def summary(self) -> dict[str, Any]:
        with self._lock:
            sample_count = self._db.execute("SELECT count(*) FROM samples").fetchone()[0]
            health_count = self._db.execute("SELECT count(*) FROM health").fetchone()[0]
            open_alerts = self._db.execute(
                "SELECT count(*) FROM alerts WHERE state='open'"
            ).fetchone()[0]
            bounds = self._db.execute("SELECT min(timestamp),max(timestamp) FROM samples").fetchone()
        return {
            "sample_count": sample_count, "health_count": health_count,
            "open_alert_count": open_alerts,
            "first_sample_epoch": bounds[0], "latest_sample_epoch": bounds[1],
            "database_path": str(self.path) if self.path else ":memory:",
        }

    def set_alert(
        self, node_id: int, rule: str, active: bool, message: str,
        observed: float | None = None, threshold: float | None = None,
        sample_timestamp: int | None = None, severity: str = "warning",
    ) -> None:
        now = utc_now()
        with self._lock:
            row = self._db.execute(
                "SELECT id FROM alerts WHERE node_id=? AND rule=? AND state='open'",
                (node_id, rule),
            ).fetchone()
            if active and row:
                self._db.execute(
                    "UPDATE alerts SET message=?,observed=?,threshold_value=?,sample_timestamp=?,"
                    "updated_utc=? WHERE id=?",
                    (message, observed, threshold, sample_timestamp, now, row[0]),
                )
            elif active:
                self._db.execute(
                    "INSERT INTO alerts(node_id,rule,severity,state,message,observed,threshold_value,"
                    "sample_timestamp,opened_utc,updated_utc) VALUES(?,?,?,'open',?,?,?,?,?,?)",
                    (node_id, rule, severity, message, observed, threshold,
                     sample_timestamp, now, now),
                )
            elif row:
                self._db.execute(
                    "UPDATE alerts SET state='resolved',resolved_utc=?,updated_utc=? WHERE id=?",
                    (now, now, row[0]),
                )

    def alerts(self, state: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
        sql, args = "SELECT * FROM alerts", []
        if state:
            sql += " WHERE state=?"; args.append(state)
        sql += " ORDER BY CASE state WHEN 'open' THEN 0 ELSE 1 END, updated_utc DESC LIMIT ?"
        args.append(min(max(limit, 1), 2000))
        with self._lock:
            rows = self._db.execute(sql, args).fetchall()
        return [dict(row) for row in rows]

    def acknowledge_alert(self, alert_id: int) -> bool:
        with self._lock:
            cursor = self._db.execute(
                "UPDATE alerts SET acknowledged_utc=?,updated_utc=? WHERE id=?",
                (utc_now(), utc_now(), alert_id),
            )
        return cursor.rowcount == 1

    def cleanup(self, retention_days: int) -> dict[str, int]:
        cutoff = int(datetime.now(timezone.utc).timestamp()) - retention_days * 86400
        deleted = {}
        with self._lock:
            for table in ("samples", "health"):
                deleted[table] = self._db.execute(
                    f"DELETE FROM {table} WHERE timestamp<?", (cutoff,)  # noqa: S608
                ).rowcount
        return deleted

    def create_history_job(
        self, start_epoch: int, end_epoch: int, chunk_seconds: int,
        max_records_per_chunk: int,
    ) -> dict[str, Any]:
        now = utc_now()
        with self._lock:
            cursor = self._db.execute(
                "INSERT INTO history_jobs(start_epoch,end_epoch,cursor_epoch,chunk_seconds,"
                "max_records_per_chunk,status,created_utc,updated_utc) VALUES(?,?,?,?,?,'queued',?,?)",
                (start_epoch, end_epoch, start_epoch, chunk_seconds, max_records_per_chunk, now, now),
            )
        return self.history_job(cursor.lastrowid)  # type: ignore[return-value]

    def history_job(self, job_id: int) -> dict[str, Any] | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM history_jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def history_jobs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM history_jobs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def update_history_job(self, job_id: int, **values: Any) -> dict[str, Any]:
        allowed = {
            "node_id", "cursor_epoch", "status", "chunks_completed", "records_received",
            "records_imported", "duplicates", "error",
        }
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"unknown history job fields: {sorted(unknown)}")
        values["updated_utc"] = utc_now()
        assignments = ",".join(f"{key}=?" for key in values)
        with self._lock:
            self._db.execute(
                f"UPDATE history_jobs SET {assignments} WHERE id=?",  # noqa: S608
                (*values.values(), job_id),
            )
        job = self.history_job(job_id)
        if job is None:
            raise KeyError(job_id)
        return job
