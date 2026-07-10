from __future__ import annotations

from dataclasses import dataclass

from backtest_templates.base_template import BaseBacktestTemplate, OrderIntent
from core.portfolio import Portfolio


@dataclass
class GridLevel:
    level: int
    buy_price: float
    sell_price: float
    target_percent: float
    filled: bool = False
    filled_quantity: int = 0


class GridTemplate(BaseBacktestTemplate):
    template_name = "grid"

    def __init__(
        self,
        strategy,
        symbol: str,
        initial_cash: float = 1000000,
        grid_step: float = 0.03,
        levels: int = 3,
        layer_percent: float = 0.1,
        base_price: float | None = None,
        grid_base: str = "fixed",
        ma_window: int = 5,
        max_position_percent: float = 0.95,
    ) -> None:
        super().__init__(strategy, symbol, initial_cash)
        self.grid_step = grid_step
        self.levels = levels
        self.layer_percent = layer_percent
        self.base_price = base_price
        self.grid_base = grid_base
        self.ma_window = ma_window
        self.max_position_percent = max_position_percent
        self.grid_levels: list[GridLevel] = []
        self.grid_trades: list[dict] = []

    def initialize_grid(self, base_price: float) -> None:
        self.base_price = base_price
        existing = {level.level: level for level in self.grid_levels}
        self.grid_levels = [
            GridLevel(
                level=level,
                buy_price=round(base_price * (1 - self.grid_step * level), 4),
                sell_price=round(base_price * (1 + self.grid_step * level), 4),
                target_percent=round(self.layer_percent * level, 6),
                filled=existing.get(level, GridLevel(level, 0, 0, 0)).filled,
                filled_quantity=existing.get(level, GridLevel(level, 0, 0, 0)).filled_quantity,
            )
            for level in range(1, self.levels + 1)
        ]

    def _current_base_price(self, history_data: list[dict]) -> float | None:
        if self.grid_base.lower() not in {"ma", "ma5", "moving_average"}:
            return self.base_price or float(history_data[-1]["close"])
        if len(history_data) < self.ma_window:
            return None
        closes = [float(row["close"]) for row in history_data[-self.ma_window:]]
        return sum(closes) / len(closes)

    def _record_grid_trade(self, row: dict, action: str, level: GridLevel, price: float) -> None:
        self.grid_trades.append({
            "date": row["date"],
            "symbol": self.symbol,
            "action": action,
            "grid_level": level.level,
            "price": price,
            "buy_price": level.buy_price,
            "sell_price": level.sell_price,
            "target_percent": level.target_percent,
        })

    def create_intents(self, index: int, history_data: list[dict], portfolio: Portfolio) -> list[OrderIntent]:
        row = history_data[-1]
        close = float(row["close"])
        prev_close = float(history_data[-2]["close"]) if len(history_data) >= 2 else close
        base_price = self._current_base_price(history_data)
        if base_price is None:
            return []
        if not self.grid_levels or self.grid_base.lower() in {"ma", "ma5", "moving_average"}:
            self.initialize_grid(base_price)
        if len(history_data) < 2:
            return []
        intents: list[OrderIntent] = []
        for level in self.grid_levels:
            crossed_down = prev_close > level.buy_price >= close
            crossed_up = prev_close < level.sell_price <= close
            if crossed_down and not level.filled:
                level.filled = True
                level.filled_quantity = portfolio.positions.total(self.symbol)
                self._record_grid_trade(row, "BUY", level, close)
                target_percent = min(self.max_position_percent, level.target_percent)
                intents.append(OrderIntent(self.symbol, row["date"], "BUY", f"价格下穿网格买入层级 {level.level}", target_percent=target_percent, metadata={"grid_level": level.level, "grid_price": level.buy_price, "grid_base": round(base_price, 6), "timeframe": row.get("timeframe", "1d")}))
            elif crossed_up and level.filled:
                level.filled = False
                level.filled_quantity = 0
                remaining_percent = sum(item.target_percent for item in self.grid_levels if item.filled)
                self._record_grid_trade(row, "SELL", level, close)
                intents.append(OrderIntent(self.symbol, row["date"], "SELL", f"价格上穿网格卖出层级 {level.level}", target_percent=min(self.max_position_percent, remaining_percent), metadata={"grid_level": level.level, "grid_price": level.sell_price, "grid_base": round(base_price, 6), "timeframe": row.get("timeframe", "1d")}))
        return intents
