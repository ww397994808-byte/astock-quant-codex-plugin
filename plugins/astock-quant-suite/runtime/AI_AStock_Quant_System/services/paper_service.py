from __future__ import annotations

from pathlib import Path

import yaml

from core.result import TaskResult
from core.run_manager import RunManager
from paper_live.observation import PaperObservationChecker
from services.backtest_service import BacktestService


class PaperService:
    def run(
        self,
        strategy: str,
        symbol: str,
        data: str,
        params: dict | None = None,
        timeframe: str = "1d",
        adjust: str = "raw",
        plan_run_id: str | None = None,
    ) -> TaskResult:
        plan = self._load_plan(plan_run_id)
        strategy_pattern = plan.get("strategy_pattern") or "timing"
        timeframe = plan.get("timeframe") or timeframe
        result = BacktestService().run(strategy, symbol, data, params=params, prefix="paper", timeframe=timeframe, adjust=adjust)
        if result.report_path:
            checker = PaperObservationChecker()
            observation = checker.check(result.report_path, strategy_pattern=strategy_pattern, timeframe=timeframe)
            checker.write_report(result.report_path, observation)
            result.artifacts["paper_observation"] = observation.to_dict()
            result.artifacts["paper_policy"] = observation.policy
            if not observation.ok:
                result.status = "INVALID"
                result.audit_status = "INVALID"
                result.warnings.extend(observation.failures)
        result.message = "模拟盘演练完成（使用本地历史数据撮合），已生成模拟观察报告"
        return result

    def _load_plan(self, plan_run_id: str | None) -> dict:
        if not plan_run_id:
            return {}
        plan_path = RunManager().resolve_run_dir(plan_run_id) / "backtest_plan.yaml"
        if not plan_path.exists():
            return {}
        return yaml.safe_load(plan_path.read_text(encoding="utf-8")) or {}
