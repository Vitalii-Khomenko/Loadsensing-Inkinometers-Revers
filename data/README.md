# Runtime Data

The browser service creates `til90.sqlite3` here by default. It contains local measurements, health records, alert state, monitoring settings, and resumable history-job progress.

The SQLite database and its WAL/SHM sidecars are runtime data, not source files. Back them up before deleting them. Select a different location with `python -m tools.web_service --database PATH`.
