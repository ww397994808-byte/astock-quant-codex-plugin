from __future__ import annotations

from pathlib import Path

import yaml

from intake.strategy_requirement import StrategyRequirement


class DSLBuilder:
    def build(self, req: StrategyRequirement) -> dict:
        pattern = req.strategy_pattern or "swing"
        dsl = {
            "market": req.market,
            "symbols": req.symbols,
            "timeframe": req.timeframe or "1d",
            "adjust": req.data_adjustment,
            "pattern": pattern,
            "entry": self._entry(req),
            "exit": self._exit(req),
            "sizing": self._sizing(req),
            "objective": {
                "primary": req.objective.get("primary", "calmar"),
                "target_annual_return": req.objective.get("target_annual_return", [0.15, 0.25]),
                "min_annual_return": req.objective.get("min_annual_return"),
                "max_drawdown": req.risk_control.get("max_drawdown", 0.15),
            },
            "constraints": {
                **req.constraints,
                "max_experiments": req.constraints.get("max_experiments", 300),
                "min_trades": req.constraints.get("min_trades", 10),
            },
        }
        return dsl

    def write_yaml(self, path: str | Path, req: StrategyRequirement) -> dict:
        dsl = self.build(req)
        Path(path).write_text(yaml.safe_dump(dsl, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return dsl

    def _entry(self, req: StrategyRequirement) -> dict:
        if req.strategy_pattern == "grid":
            idea = req.original_idea.upper()
            params = {"grid_step": [0.02, 0.03], "levels": [2, 3]}
            if "MA5" in idea or "均线" in req.original_idea:
                intraday = req.timeframe in {"10m", "30m", "1h"} or any(word in req.original_idea for word in ["10分钟", "10min", "30分钟", "1小时", "1h"])
                params = {
                    "grid_base": ["ma"],
                    "ma_window": [5],
                    "grid_step": [0.001, 0.002, 0.003, 0.004, 0.005] if intraday else [0.005, 0.01, 0.015, 0.02, 0.03],
                    "levels": [3, 5],
                    "layer_percent": [0.1, 0.2],
                    "max_position_percent": [0.5, 0.7, 1.0],
                }
            return {"type": "GridLayerEntry", "params": params}
        if req.entry_logic and "布林" in req.entry_logic:
            return {"type": "BollLowerEntry", "params": {"window": [20, 30], "num_std": [1.8, 2.0, 2.2]}}
        if req.entry_logic and "回撤" in req.entry_logic:
            return {"type": "DrawdownEntry", "params": {"drawdown_threshold": [0.08, 0.12]}}
        return {"type": "SignalEntry", "description": req.entry_logic or "待补充"}

    def _exit(self, req: StrategyRequirement) -> list[dict]:
        exits = []
        if req.exit_logic and ("中轨" in req.exit_logic or "均值" in req.exit_logic):
            exits.append({"type": "BollMiddleExit"})
        if req.risk_control.get("stop_loss_required") or req.risk_control.get("max_drawdown"):
            exits.append({"type": "FixedStopLossExit", "params": {"stop_loss": [0.06, 0.08, 0.10]}})
        if not exits:
            exits.append({"type": "ExitLogic", "description": req.exit_logic or "待补充"})
        return exits

    def _sizing(self, req: StrategyRequirement) -> dict:
        if req.sizing_logic == "分批仓位":
            return {"type": "LayeredSizing", "params": {"percent": [0.1, 0.2, 0.3]}}
        return {"type": "FixedPercentSizing", "params": {"percent": [0.1, 0.2, 0.3]}}
