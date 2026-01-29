"""Title list loader for batch runs."""
from __future__ import annotations

from pathlib import Path


def load_titles(path: str) -> list[str]:
    titles_path = Path(path)
    if not titles_path.exists():
        raise FileNotFoundError(f"Titles file not found: {path}")

    titles: list[str] = []
    with titles_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                continue
            titles.append(line)
    return titles
