from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SignalCausalityContract:
    name: str = "signal-causality-v1"
    rule: str = "bar[t] 产生交易信号时，只允许读取 bar[0:t] 的已发生数据。"
    allowed_fields: tuple[str, ...] = ("open", "high", "low", "close", "volume", "amount", "paused", "is_st", "board")
    execution_rule: str = "默认信号在 bar[t] 收盘确认，订单在 bar[t+1] 开盘价成交。"

    def to_dict(self) -> dict:
        return asdict(self)
