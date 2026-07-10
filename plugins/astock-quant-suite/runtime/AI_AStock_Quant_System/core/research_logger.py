from __future__ import annotations

from pathlib import Path


class ResearchLogger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.lines: list[str] = []

    def log(self, message: str) -> None:
        self.lines.append(message)

    def save(self) -> None:
        self.path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")
