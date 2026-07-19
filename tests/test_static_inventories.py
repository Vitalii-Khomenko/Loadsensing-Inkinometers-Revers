import csv
import hashlib
from pathlib import Path


def test_firmware_inventory_matches_embedded_files() -> None:
    inventory = Path("analysis/firmware/inventory.csv")
    with inventory.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 15
    for row in rows:
        path = Path("analysis/apktool/unknown/firmwares") / row["filename"]
        data = path.read_bytes()
        assert len(data) == int(row["size_bytes"])
        assert hashlib.sha256(data).hexdigest() == row["sha256"]


def test_read_only_request_response_registry_is_unique() -> None:
    with Path("analysis/protocol/request_response_pairs.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        rows = list(csv.DictReader(stream))
    names = [row["operation"] for row in rows]
    assert len(rows) == 19
    assert len(names) == len(set(names))
    assert all(row["safety"] == "read_only" for row in rows)
