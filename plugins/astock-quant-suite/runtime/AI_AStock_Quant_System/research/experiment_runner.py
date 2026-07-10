from __future__ import annotations

import csv
from pathlib import Path

from backtest.engine import BacktestEngine
from backtest_templates.grid_template import GridTemplate
from core.data_loader import load_csv_data
from core.run_manager import RunManager
from research.strategy_variant_generator import StrategyVariant
from strategies.strategy_registry import create_strategy


class ExperimentRunner:
    def run(self, variants: list[StrategyVariant], symbol: str, data_path: str | Path, output_dir: str | Path, timeframe: str = "1d", adjust: str = "raw") -> list[dict]:
        output_dir = Path(output_dir)
        rows = load_csv_data(data_path, symbol)
        split_at = max(3, int(len(rows) * 0.7))
        in_path = output_dir / "in_sample.csv"
        out_path = output_dir / "out_sample.csv"
        self._write_rows(in_path, rows[:split_at])
        self._write_rows(out_path, rows[split_at - 2:])
        results: list[dict] = []
        experiments_dir = output_dir / "experiments"
        manager = RunManager(base_dir=experiments_dir)
        for variant in variants:
            result = self._run_variant(variant, symbol, data_path, manager, "full", timeframe, adjust)
            in_result = self._run_variant(variant, symbol, in_path, manager, "in", timeframe, adjust)
            out_result = self._run_variant(variant, symbol, out_path, manager, "out", timeframe, adjust)
            row = {
                "variant_id": variant.variant_id,
                "pattern": variant.pattern,
                "template_name": variant.template_name,
                "strategy_name": variant.strategy_name,
                "params": str(variant.params),
                "run_id": result["run_id"],
                "report_path": result["report_path"],
                "audit_status": result["audit_status"],
                "total_return": result["performance"].get("total_return", 0),
                "max_drawdown": result["performance"].get("max_drawdown", 0),
                "trade_count": result["performance"].get("trade_count", 0),
                "in_sample_return": in_result["performance"].get("total_return", 0),
                "out_sample_return": out_result["performance"].get("total_return", 0),
                "out_sample_drawdown": out_result["performance"].get("max_drawdown", 0),
            }
            results.append(row)
        self._write_results(output_dir / "experiment_results.csv", results)
        return results

    def _run_variant(self, variant: StrategyVariant, symbol: str, data_path: str | Path, manager: RunManager, suffix: str, timeframe: str, adjust: str) -> dict:
        ctx = manager.create_run(f"{variant.variant_id}_{suffix}")
        if variant.pattern == "grid":
            rows = load_csv_data(data_path, symbol)
            strategy = create_strategy("ma_cross")
            template = GridTemplate(
                strategy,
                symbol,
                grid_step=float(variant.params.get("grid_step", 0.03)),
                levels=int(variant.params.get("levels", 3)),
                layer_percent=float(variant.params.get("layer_percent", 0.1)),
                grid_base=str(variant.params.get("grid_base", "fixed")),
                ma_window=int(variant.params.get("ma_window", 5)),
                max_position_percent=float(variant.params.get("max_position_percent", 0.95)),
            )
            for row in rows:
                row["timeframe"] = timeframe
                row["adjust_type"] = adjust
            result = template.run(ctx, rows, source_paths=[])
        else:
            params = self._strategy_params(variant)
            result = BacktestEngine().run(ctx, variant.strategy_name, symbol, data_path, params, timeframe=timeframe, adjust=adjust)
        return {"run_id": result.run_id, "report_path": str(result.output_dir), "audit_status": result.audit_status, "performance": result.performance}

    def _strategy_params(self, variant: StrategyVariant) -> dict:
        if variant.strategy_name == "boll_mean_reversion":
            return {k: v for k, v in variant.params.items() if k in {"window", "num_std", "stop_loss"}}
        if variant.strategy_name == "ma_cross":
            return {k: v for k, v in variant.params.items() if k in {"short_window", "long_window"}}
        return {}

    def _write_rows(self, path: Path, rows: list[dict]) -> None:
        fieldnames = ["datetime", "date", "time", "timeframe", "open", "high", "low", "close", "volume", "amount", "symbol", "name", "is_st", "board", "paused", "source", "adjust_type", "adjust_factor", "corporate_action_flag"]
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                item = dict(row)
                if hasattr(item.get("datetime"), "strftime"):
                    item["datetime"] = item["datetime"].strftime("%Y-%m-%d %H:%M:%S")
                item["date"] = item["date"].strftime("%Y-%m-%d") if hasattr(item["date"], "strftime") else item["date"]
                writer.writerow({key: item.get(key, "") for key in fieldnames})

    def _write_results(self, path: Path, results: list[dict]) -> None:
        fieldnames = ["variant_id", "pattern", "template_name", "strategy_name", "params", "run_id", "report_path", "audit_status", "total_return", "max_drawdown", "trade_count", "in_sample_return", "out_sample_return", "out_sample_drawdown"]
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
