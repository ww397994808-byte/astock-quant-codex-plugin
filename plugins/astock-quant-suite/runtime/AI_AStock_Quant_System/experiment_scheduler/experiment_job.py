from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass
class ExperimentJob:
    job_id: str
    parent_iteration: int
    experiment_type: str
    symbol: str
    timeframe: str
    adjust: str
    strategy_dsl: dict
    data_path: str = ""
    regime: str = ""
    parameters: dict = field(default_factory=dict)
    status: str = "PENDING"
    result_path: str = ""
    audit_status: str = ""
    readiness: str = ""
    score: float = 0.0
    failure_reason: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["strategy_dsl"] = str(self.strategy_dsl)
        return data
