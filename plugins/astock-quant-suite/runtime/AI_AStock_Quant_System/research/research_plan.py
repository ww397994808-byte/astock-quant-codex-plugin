from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ResearchPlan:
    original_direction: str
    selected_pattern: str
    hypothesis: str
    variables_to_test: list[str]
    entry_logic_candidates: list[str]
    exit_logic_candidates: list[str]
    sizing_candidates: list[str]
    filter_candidates: list[str]
    risk_candidates: list[str]
    search_space: dict[str, list[Any]]
    constraints: list[str]
    evaluation_metrics: list[str]
    timeframe: str = "1d"
    adjust: str = "raw"
    data_source: str = "local"
    blocker_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def write_markdown(self, path: str | Path) -> None:
        lines = [
            "# Research Plan",
            "",
            f"- 原始方向：{self.original_direction}",
            f"- 策略范式：{self.selected_pattern}",
            f"- 周期：{self.timeframe}",
            f"- 复权方式：{self.adjust}",
            f"- 数据来源：{self.data_source}",
            f"- 研究假设：{self.hypothesis}",
            "",
            "## 变量",
            *[f"- {item}" for item in self.variables_to_test],
            "",
            "## 入场候选",
            *[f"- {item}" for item in self.entry_logic_candidates],
            "",
            "## 出场候选",
            *[f"- {item}" for item in self.exit_logic_candidates],
            "",
            "## 风控候选",
            *[f"- {item}" for item in self.risk_candidates],
            "",
            "## 搜索空间",
            "```json",
            json.dumps(self.search_space, ensure_ascii=False, indent=2),
            "```",
            "",
            "## 约束",
            *[f"- {item}" for item in self.constraints],
        ]
        if self.blocker_notes:
            lines.extend(["", "## Blockers", *[f"- {item}" for item in self.blocker_notes]])
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
