"""Restore a factory-reset TIL90 from a validated backup and gateway secret."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from tools.config_backup import BackupError, validate_snapshot
from tools.device_service import DeviceService, DeviceServiceError
from tools.radio_configuration import RadioConfigurationError, restore_after_factory_reset
from tools.til90_cli import _save_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="serial path; auto-detected by default")
    parser.add_argument("--backup", required=True, help="checksummed pre-reset backup")
    parser.add_argument("--network-id", required=True, type=int)
    parser.add_argument(
        "--password-file", required=True,
        help="mode-0600 file containing only the gateway password",
    )
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--output", required=True, help="mode-0600 evidence path")
    args = parser.parse_args(argv)

    try:
        target = json.loads(Path(args.backup).read_text(encoding="utf-8"))
        validate_snapshot(target)
        password_path = Path(args.password_file)
        if password_path.stat().st_mode & 0o077:
            raise RadioConfigurationError("password file permissions must be 0600")
        password = password_path.read_text(encoding="utf-8").strip()
        result = restore_after_factory_reset(
            DeviceService(args.port), target, args.network_id, password, args.confirm
        )
    except (
        BackupError, DeviceServiceError, RadioConfigurationError,
        OSError, json.JSONDecodeError,
    ) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 1

    _save_json(args.output, json.dumps(result, indent=2, sort_keys=True))
    print(json.dumps({
        "status": result["status"],
        "node_id": result["node_id"],
        "network_id": result["network_id"],
        "calibration_write_not_needed": result["calibration_write_not_needed"],
        "output": args.output,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
