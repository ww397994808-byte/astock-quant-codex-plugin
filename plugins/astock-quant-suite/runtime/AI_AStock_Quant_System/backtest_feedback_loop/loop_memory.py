from __future__ import annotations

import json
from pathlib import Path


class LoopMemory:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def add(self, record: dict) -> None:
        self.records.append(record)

    def no_improve_rounds(self, threshold: float = 0.03) -> int:
        if len(self.records) < 2:
            return 0
        count = 0
        best = self.records[0].get("score", -999)
        for record in self.records[1:]:
            if record.get("score", -999) <= best + threshold:
                count += 1
            else:
                best = record.get("score", -999)
                count = 0
        return count

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.records, ensure_ascii=False, indent=2), encoding="utf-8")

