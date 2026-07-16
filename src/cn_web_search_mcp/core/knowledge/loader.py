"""Parse the existing authority Markdown without loading it into model context."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


_URL_RE = re.compile(r"https?://[^\s)]+")


@dataclass(slots=True)
class AuthorityEntry:
    category: str
    entity: str
    keywords: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)


def load_authority_entries(path: str | Path) -> list[AuthorityEntry]:
    """Read the complete file and parse every entity entry in source order."""

    source = Path(path)
    lines = source.read_text(encoding="utf-8").splitlines()
    entries: list[AuthorityEntry] = []
    category = "未分类"
    current: AuthorityEntry | None = None

    def flush() -> None:
        nonlocal current
        if current and (current.keywords or current.urls):
            entries.append(current)
        current = None

    for line in lines:  # Deliberately traverse to EOF; never stop on first match.
        stripped = line.strip()
        if stripped.startswith("## ") and not stripped.startswith("### "):
            flush()
            category = stripped[3:].strip(" -")
        elif stripped.startswith("### "):
            flush()
            current = AuthorityEntry(category=category, entity=stripped[4:].strip())
        elif current and stripped.startswith("- 关键词:"):
            raw = stripped.split(":", 1)[1]
            current.keywords = [item.strip().casefold() for item in raw.split(",") if item.strip()]
        elif current and stripped.startswith("-"):
            current.urls.extend(_URL_RE.findall(stripped))

    flush()
    return entries
