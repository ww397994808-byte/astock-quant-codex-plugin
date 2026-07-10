from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class BacktestPlan:
    strategy_pattern: str
    template_name: str | None
    symbol_scope: str
    timeframe: str
    adjust: str
    data_required: list[str]
    execution_model: dict
    audit_required: list[str]
    promotion_policy: dict
    status: str = "VALID"
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def can_run_backtest(self) -> bool:
        return self.status == "VALID" and self.template_name is not None and not self.blockers

    @property
    def qmt_allowed(self) -> bool:
        return bool(self.promotion_policy.get("qmt_allowed", False)) and self.can_run_backtest

    def to_dict(self) -> dict:
        return asdict(self)

    def write_yaml(self, path: str | Path) -> None:
        Path(path).write_text(yaml.safe_dump(self.to_dict(), allow_unicode=True, sort_keys=False), encoding="utf-8")
