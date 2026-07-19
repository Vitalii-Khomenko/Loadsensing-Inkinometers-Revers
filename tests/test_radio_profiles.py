import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "analysis" / "protocol" / "radio_profiles.json"


def load_profiles():
    return json.loads(REGISTRY.read_text(encoding="utf-8"))["profiles"]


def test_original_app_has_20_unique_profiles():
    profiles = load_profiles()
    assert len(profiles) == 20
    assert len({profile["name"] for profile in profiles}) == 20
    assert sum(profile["plan"] == "EDGE" for profile in profiles) == 15
    assert sum(profile["plan"] == "CLOUD" for profile in profiles) == 5


def test_profile_shapes_and_ranges():
    for profile in load_profiles():
        assert profile["band"] in {"CE", "FCC"}
        assert profile["sf"][0] <= profile["sf"][2] <= profile["sf"][1]
        assert profile["tx_power_dbm"] in {14, 20}
        assert 0 <= profile["default_group"] < len(profile["uplink_hz"])
        assert all(len(group) == 8 for group in profile["uplink_hz"])
        assert all(0 <= frequency <= 1_000_000_000 for group in profile["uplink_hz"] for frequency in group)
        assert len(profile["downlink_hz"]) in {0, 8}


def test_hardware_current_configuration_matches_europe_profile():
    europe = next(profile for profile in load_profiles() if profile["name"] == "EUROPE")
    assert europe["mac"] == "EU868_V1"
    assert europe["sf"] == [7, 11, 11]
    assert europe["tx_power_dbm"] == 14
    assert europe["etsi"] == [True, True]
    assert europe["adr"] == [True, True]
    assert europe["uplink_hz"][0] == [
        868_100_000, 868_300_000, 868_500_000, 868_850_000,
        869_050_000, 869_525_000, 0, 0,
    ]
