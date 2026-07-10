from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from backtest.result import BacktestResult
from backtest_templates.template_registry import create_backtest_template
from core.data_loader import load_csv_data
from core.run_manager import RunContext
from market_data.adjustment import AdjustmentEngine
from market_data.corporate_actions import load_corporate_actions
from strategies.strategy_registry import create_strategy


class BacktestEngine:
    def __init__(self, config_path: str | Path = "config/backtest.yaml") -> None:
        self.config_path = Path(config_path)
        self.config = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) if self.config_path.exists() else {}

    def run(
        self,
        run_context: RunContext,
        strategy_name: str,
        symbol: str,
        data_path: str | Path,
        strategy_params: dict[str, Any] | None = None,
        initial_cash: float | None = None,
        timeframe: str = "1d",
        adjust: str = "raw",
    ) -> BacktestResult:
        initial_cash = float(initial_cash or self.config.get("initial_cash", 1000000))
        strategy = create_strategy(strategy_name, **(strategy_params or {}))
        rows = load_csv_data(data_path, symbol=symbol)
        candidates = [
            Path(f"data/sample/corporate_actions_{symbol.split('.')[0]}.csv"),
            Path(f"data/sample/corporate_actions_{symbol.replace('.', '_')}.csv"),
            Path(f"data/sample/corporate_actions_{symbol}.csv"),
        ]
        action_file = next((p for p in candidates if p.exists()), None)
        actions = load_corporate_actions(action_file, symbol) if action_file else []
        rows = AdjustmentEngine().adjust(rows, actions, adjust)
        for row in rows:
            row["timeframe"] = timeframe or row.get("timeframe", "1d")
        template = create_backtest_template(strategy, strategy_name, symbol, initial_cash, template_params=strategy_params or {})
        return template.run(run_context, rows, source_paths=[Path("strategies") / f"{strategy_name}.py"])
