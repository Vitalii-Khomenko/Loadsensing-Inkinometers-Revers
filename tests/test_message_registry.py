import csv
from pathlib import Path


REGISTRY = Path("analysis/protocol/message_registry.csv")


def _rows() -> list[dict[str, str]]:
    with REGISTRY.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def test_dispatch_registry_contains_60_unique_am_types() -> None:
    rows = _rows()
    values = [int(row["am_type_dec"]) for row in rows]

    assert len(rows) == 60
    assert len(values) == len(set(values))
    assert values == sorted(values)


def test_decimal_and_hex_columns_agree() -> None:
    for row in _rows():
        assert int(row["am_type_dec"]) == int(row["am_type_hex"], 16)


def test_core_til90_dispatch_mappings() -> None:
    by_type = {int(row["am_type_dec"]): row for row in _rows()}

    assert by_type[0x4C]["response_class"] == "C8880b0"
    assert by_type[0x01]["response_class"] == "C8911n0"
    assert by_type[0x02]["response_class"] == "C8926u"
    assert by_type[0x50]["response_class"] == "C8877a0"
    assert by_type[0x82]["response_class"] == "C8916p0"
    assert by_type[0x98]["response_class"] == "C8919r"
    assert by_type[0x9B]["response_class"] == "C8917q"
    assert by_type[0xA5]["response_class"] == "C9026a"


def test_health_and_info_aliases_use_the_same_classes() -> None:
    by_type = {int(row["am_type_dec"]): row for row in _rows()}

    assert {by_type[value]["response_class"] for value in (0x40, 0x46, 0x4F)} == {
        "C8912o"
    }
    assert {by_type[value]["response_class"] for value in (0x03, 0x09)} == {
        "C8924t"
    }
