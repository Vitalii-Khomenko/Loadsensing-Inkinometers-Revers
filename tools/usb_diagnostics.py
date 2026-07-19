"""Linux USB serial identity, access, and service conflict diagnostics."""

from __future__ import annotations

import grp
import os
from pathlib import Path
import pwd
import stat
import subprocess
from typing import Any


def stable_alias(port: str) -> str | None:
    target = Path(port)
    if not target.exists():
        return None
    try:
        real = target.resolve()
        aliases = sorted(Path("/dev/serial/by-id").glob("*"))
        return str(next(alias for alias in aliases if alias.resolve() == real))
    except (OSError, StopIteration):
        return None


def modem_manager_status() -> str:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "ModemManager"], capture_output=True,
            text=True, timeout=2, check=False,
        )
        return result.stdout.strip() or "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"


def diagnose(port: str | None) -> dict[str, Any]:
    aliases = sorted(str(item) for item in Path("/dev/serial/by-id").glob("*CP2102N*"))
    selected = port or (aliases[0] if len(aliases) == 1 else None)
    result: dict[str, Any] = {
        "selected_port": selected, "stable_alias": stable_alias(selected) if selected else None,
        "detected_ports": aliases, "modem_manager": modem_manager_status(),
        "recommendations": [],
    }
    if not selected or not Path(selected).exists():
        result.update(exists=False, readable=False, writable=False)
        result["recommendations"].append("Connect one TIL90 USB adapter and refresh diagnostics.")
        return result
    info = Path(selected).stat()
    result.update(
        exists=True, real_path=str(Path(selected).resolve()),
        readable=os.access(selected, os.R_OK), writable=os.access(selected, os.W_OK),
        mode=stat.filemode(info.st_mode), owner=pwd.getpwuid(info.st_uid).pw_name,
        group=grp.getgrgid(info.st_gid).gr_name,
    )
    if not result["stable_alias"]:
        result["recommendations"].append(
            "Use a /dev/serial/by-id path when available so ttyUSB numbering cannot change the device."
        )
    if not result["readable"] or not result["writable"]:
        result["recommendations"].append(
            f'Grant this session access: sudo setfacl -m u:"$(id -un)":rw {selected}'
        )
        result["recommendations"].append(
            "For permanent access, install config/99-til90-cp210x.rules and add the user to dialout."
        )
    if result["modem_manager"] == "active":
        result["recommendations"].append(
            "Stop ModemManager while using the sensor: sudo systemctl stop ModemManager"
        )
    if not result["recommendations"]:
        result["recommendations"].append("USB identity and current Linux permissions look ready.")
    return result

