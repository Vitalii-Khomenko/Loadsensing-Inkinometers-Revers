"""Repository-wide enforcement of the English-only authored-content policy."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
CYRILLIC = re.compile(r"[\u0400-\u04FF]")
TEXT_SUFFIXES = {
    ".css", ".csv", ".html", ".ini", ".js", ".json", ".md",
    ".py", ".toml", ".txt", ".yaml", ".yml",
}
AUTHORED_ROOT_FILES = {
    ".dockerignore", "AGENTS.md", "APK-Info.md", "Command.md", "Dockerfile",
    "Goal.md", "README.md", "ROADMAP.md", "StartCommands.md", "compose.yaml",
    "docker.env.example", "requirements.txt",
}
AUTHORED_DIRECTORIES = (
    ROOT / "docs",
    ROOT / "tools",
    ROOT / "tests",
    ROOT / "web",
    ROOT / "analysis" / "protocol",
    ROOT / "analysis" / "firmware",
)


def authored_files():
    for name in sorted(AUTHORED_ROOT_FILES):
        path = ROOT / name
        if path.is_file():
            yield path
    for directory in AUTHORED_DIRECTORIES:
        if not directory.exists():
            continue
        yield from sorted(
            path for path in directory.rglob("*")
            if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES
        )


def test_authored_content_contains_no_cyrillic() -> None:
    violations = []
    for path in authored_files():
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if CYRILLIC.search(line):
                violations.append(f"{path.relative_to(ROOT)}:{line_number}: {line.strip()}")
    assert not violations, "English-only policy violations:\n" + "\n".join(violations)


def test_authored_paths_use_ascii_names() -> None:
    violations = [
        str(path.relative_to(ROOT))
        for path in authored_files()
        if not all(ord(character) < 128 for character in str(path.relative_to(ROOT)))
    ]
    assert not violations, "Non-ASCII authored paths:\n" + "\n".join(violations)
