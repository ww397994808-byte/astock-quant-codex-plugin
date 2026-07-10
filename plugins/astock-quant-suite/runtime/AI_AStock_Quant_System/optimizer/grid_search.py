from __future__ import annotations

from itertools import product
from pathlib import Path

from backtest.engine import BacktestEngine
from core.run_manager import RunManager


def default_param_grid(strategy_name: str) -> dict[str, list]:
    if strategy_name == "boll_mean_reversion":
        return {"window": [10, 20], "num_std": [1.5, 2.0], "stop_loss": [0.06, 0.08]}
    if strategy_name == "ma_cross":
        return {"short_window": [3, 5], "long_window": [10, 20]}
    if strategy_name == "dividend_drawdown":
        return {"lookback": [30, 60], "drawdown_threshold": [0.08, 0.12]}
    return {}


class GridSearchOptimizer:
    def run(self, strategy_name: str, symbol: str, data_path: str | Path, output_dir: Path, param_grid: dict | None = None) -> dict:
        grid = param_grid or default_param_grid(strategy_name)
        keys = list(grid)
        results = []
        manager = RunManager(base_dir=output_dir / "runs")
        for values in product(*[grid[k] for k in keys]):
            params = dict(zip(keys, values))
            ctx = manager.create_run("opt_bt")
            result = BacktestEngine().run(ctx, strategy_name, symbol, data_path, params)
            results.append({"params": params, "status": result.status, **result.performance})
        valid = [r for r in results if r["status"] == "VALID"]
        best = max(valid, key=lambda r: r.get("total_return", -999)) if valid else None
        return {"results": results, "best": best, "param_grid": grid}

