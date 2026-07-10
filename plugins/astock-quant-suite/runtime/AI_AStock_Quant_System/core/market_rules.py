from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class MarketRuleResult:
    ok: bool
    reason: str = ""


class MarketRules:
    def __init__(self, config_path: str | Path = "config/market_rules.yaml") -> None:
        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _load_config(self) -> dict[str, Any]:
        if self.config_path.exists():
            return yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        return {
            "boards": {"main": {"limit_pct": 0.10}, "star": {"limit_pct": 0.20}, "chi_next": {"limit_pct": 0.20}},
            "st_limit_pct": 0.05,
            "lot_size": 100,
            "allow_odd_lot_sell": True,
        }

    @property
    def lot_size(self) -> int:
        return int(self.config.get("lot_size", 100))

    @property
    def allow_odd_lot_sell(self) -> bool:
        return bool(self.config.get("allow_odd_lot_sell", True))

    def limit_pct(self, row: dict[str, Any]) -> float:
        if row.get("is_st"):
            return float(self.config.get("st_limit_pct", 0.05))
        board = row.get("board", "main")
        return float(self.config.get("boards", {}).get(board, {}).get("limit_pct", 0.10))

    def limit_prices(self, prev_close: float, row: dict[str, Any]) -> tuple[float, float]:
        pct = self.limit_pct(row)
        return round(prev_close * (1 + pct), 2), round(prev_close * (1 - pct), 2)

    def is_tradable_bar(self, row: dict[str, Any]) -> MarketRuleResult:
        if row.get("paused"):
            return MarketRuleResult(False, "停牌日不允许成交")
        if int(row.get("volume", 0)) <= 0:
            return MarketRuleResult(False, "成交量为 0，不允许成交")
        for col in ["open", "high", "low", "close"]:
            if row.get(col) in {None, ""}:
                return MarketRuleResult(False, f"{col} 缺失，不允许成交")
        return MarketRuleResult(True)

    def is_limit_up(self, prev_close: float, row: dict[str, Any], price: float | None = None) -> bool:
        up, _ = self.limit_prices(prev_close, row)
        check_price = float(row["open"] if price is None else price)
        return check_price >= up - 1e-6

    def is_limit_down(self, prev_close: float, row: dict[str, Any], price: float | None = None) -> bool:
        _, down = self.limit_prices(prev_close, row)
        check_price = float(row["open"] if price is None else price)
        return check_price <= down + 1e-6

    def validate_lot(self, action: str, quantity: int) -> MarketRuleResult:
        if quantity <= 0:
            return MarketRuleResult(False, "数量必须大于 0")
        if action == "BUY" and quantity % self.lot_size != 0:
            return MarketRuleResult(False, "买入数量必须是 100 股整数倍")
        if action == "BUY" and quantity < self.lot_size:
            return MarketRuleResult(False, "不允许买入不足一手")
        if action == "SELL" and not self.allow_odd_lot_sell and quantity % self.lot_size != 0:
            return MarketRuleResult(False, "卖出数量必须是 100 股整数倍")
        return MarketRuleResult(True)

