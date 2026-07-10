from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class StrategyRequirement:
    original_idea: str
    market: str = "A股"
    symbols: list[str] = field(default_factory=list)
    asset_type: str = "stock"
    timeframe: str | None = None
    strategy_pattern: str | None = None
    archetype: str | None = None
    entry_logic: str | None = None
    exit_logic: str | None = None
    sizing_logic: str | None = None
    risk_control: dict = field(default_factory=dict)
    holding_period: str | None = None
    rebalance_frequency: str | None = None
    data_adjustment: str = "point_in_time_qfq"
    objective: dict = field(default_factory=dict)
    constraints: dict = field(default_factory=dict)
    unanswered_questions: list[str] = field(default_factory=list)
    completeness_score: int = 0
    readiness_for_research: bool = False
    qmt_safety_note: str = ""
    live_intent: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
