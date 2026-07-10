from __future__ import annotations

import json
from pathlib import Path


class ResearchDB:
    def __init__(self, path: str | Path = "storage/research_db.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: dict) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

