"""Create and validate a checksummed TIL90 configuration backup."""

from __future__ import annotations

import argparse
import json

from tools.config_backup import validate_snapshot
from tools.device_service import DeviceService
from tools.til90_cli import _save_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="serial path; auto-detected by default")
    parser.add_argument("--output", required=True, help="mode-0600 backup path")
    args = parser.parse_args(argv)
    snapshot = DeviceService(args.port).backup()
    validate_snapshot(snapshot)
    _save_json(args.output, json.dumps(snapshot, indent=2, sort_keys=True))
    print(json.dumps({
        "status": "saved", "path": args.output,
        "node_id": snapshot["device"]["node_id"],
        "firmware": f"{snapshot['device']['firmware_major']}.{snapshot['device']['firmware_minor']}",
        "checksum": snapshot["checksum"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
