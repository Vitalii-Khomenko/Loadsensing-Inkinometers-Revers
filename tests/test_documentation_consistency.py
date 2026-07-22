import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_documentation_entry_points_exist() -> None:
    required = (
        "README.md",
        "AGENTS.md",
        "Goal.md",
        "ROADMAP.md",
        "docs/README.md",
        "docs/protocol.md",
        "docs/passive-capture-plan.md",
        "docs/cli-usage.md",
        "docs/radio.md",
        "docs/testing-plan.md",
        "docs/web-app.md",
        "docs/docker-deployment.md",
        "docs/node-identity.md",
        "docs/android-feature-parity.md",
        "docs/gateway-feasibility.md",
        "Dockerfile",
        "compose.yaml",
        "compose.write.yaml",
        "requirements.txt",
        "tests/test_language_policy.py",
        "captures/README.md",
        "captures/session-metadata-template.md",
        "analysis/protocol/message_registry.csv",
        "analysis/protocol/request_response_pairs.csv",
    )
    assert all((ROOT / path).is_file() for path in required)


def test_protocol_counts_match_documentation() -> None:
    with (ROOT / "analysis/protocol/message_registry.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        messages = list(csv.DictReader(stream))
    with (ROOT / "analysis/protocol/request_response_pairs.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        operations = list(csv.DictReader(stream))

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
    assert len(messages) == 60
    assert len(operations) == 19
    assert "contains 60 AM types" in readme
    assert "contains 19 operations" in readme
    assert "19 read-only operations registered" in roadmap


def test_current_docs_do_not_repeat_superseded_registry_descriptions() -> None:
    current = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "docs").glob("*.md")
    )
    forbidden = (
        "59 unique response",
        "write operations only",
        "generic/unused",
        "AbstractC8885d synthetic",
    )
    assert not any(phrase in current for phrase in forbidden)
