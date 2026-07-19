"""Chunked, deduplicated, resumable history recovery into SQLite."""

from __future__ import annotations

import threading
from typing import Any

from tools.monitoring_store import MonitoringStore


class HistoryManager:
    def __init__(self, device: Any, store: MonitoringStore) -> None:
        self.device, self.store = device, store
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._cancel = threading.Event()
        self._active_job_id: int | None = None

    def create(
        self, start_epoch: int, end_epoch: int, *, chunk_seconds: int = 21600,
        max_records_per_chunk: int = 1000,
    ) -> dict[str, Any]:
        if end_epoch < start_epoch:
            raise ValueError("history end must not precede start")
        if end_epoch - start_epoch > 366 * 86400:
            raise ValueError("history job range must not exceed 366 days")
        if not 300 <= chunk_seconds <= 7 * 86400:
            raise ValueError("history chunk must be between 300 seconds and 7 days")
        if not 1 <= max_records_per_chunk <= 2000:
            raise ValueError("maximum records per chunk must be between 1 and 2000")
        job = self.store.create_history_job(
            start_epoch, end_epoch, chunk_seconds, max_records_per_chunk
        )
        self.resume(job["id"])
        return self.store.history_job(job["id"])  # type: ignore[return-value]

    def resume(self, job_id: int) -> dict[str, Any]:
        job = self.store.history_job(job_id)
        if not job:
            raise KeyError(f"history job {job_id} does not exist")
        if job["status"] == "complete":
            return job
        with self._lock:
            if self._thread and self._thread.is_alive():
                if self._active_job_id == job_id:
                    return job
                raise RuntimeError("another history job is running")
            self._cancel.clear()
            self._active_job_id = job_id
            self.store.update_history_job(job_id, status="queued", error=None)
            self._thread = threading.Thread(
                target=self._run, args=(job_id,), name=f"til90-history-{job_id}", daemon=True
            )
            self._thread.start()
        return self.store.history_job(job_id)  # type: ignore[return-value]

    def cancel(self, job_id: int) -> dict[str, Any]:
        if self._active_job_id != job_id:
            job = self.store.history_job(job_id)
            if not job:
                raise KeyError(f"history job {job_id} does not exist")
            return job
        self._cancel.set()
        return self.store.update_history_job(job_id, status="cancelling")

    def stop(self) -> None:
        self._cancel.set()
        thread = self._thread
        if thread:
            thread.join(5)

    def _run(self, job_id: int) -> None:
        job = self.store.update_history_job(job_id, status="running", error=None)
        try:
            while job["cursor_epoch"] <= job["end_epoch"]:
                if self._cancel.is_set():
                    self.store.update_history_job(job_id, status="paused")
                    return
                start = job["cursor_epoch"]
                end = min(start + job["chunk_seconds"] - 1, job["end_epoch"])
                result = self.device.history(
                    start, end, max_records=job["max_records_per_chunk"]
                )
                if result.get("status") != "ok" or not result.get("complete"):
                    raise RuntimeError(
                        f"chunk {start}-{end} incomplete: {result.get('status', 'unknown')}"
                    )
                received = imported = duplicates = 0
                node_id = job["node_id"]
                identity = result.get("identity", {})
                if identity.get("header", {}).get("node_id") is not None:
                    node_id = identity["header"]["node_id"]
                for record in result.get("records", []):
                    received += 1
                    _kind, inserted = self.store.insert_record(record, "history")
                    if inserted:
                        imported += 1
                    else:
                        duplicates += 1
                job = self.store.update_history_job(
                    job_id, node_id=node_id, cursor_epoch=end + 1,
                    chunks_completed=job["chunks_completed"] + 1,
                    records_received=job["records_received"] + received,
                    records_imported=job["records_imported"] + imported,
                    duplicates=job["duplicates"] + duplicates,
                )
            self.store.update_history_job(job_id, status="complete", error=None)
        except Exception as exc:
            self.store.update_history_job(
                job_id, status="paused", error=f"{type(exc).__name__}: {exc}"
            )
        finally:
            with self._lock:
                self._active_job_id = None

