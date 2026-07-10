from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class InterviewState:
    original_idea: str
    current_question_id: str = ""
    answered_questions: dict[str, str] = field(default_factory=dict)
    unanswered_questions: list[str] = field(default_factory=list)
    inferred_fields: dict = field(default_factory=dict)
    confirmed_fields: dict = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)
    completeness_score: int = 0
    research_ready: bool = False
    user_confirmed: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
