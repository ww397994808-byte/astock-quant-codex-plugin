from __future__ import annotations

from core.result import TaskResult
from services.core5_live_signal_service import Core5LiveSignalService
from tasks.base_task import BaseTask


class Core5LiveSignalTask(BaseTask):
    def run(self, **kwargs) -> TaskResult:
        try:
            return Core5LiveSignalService().run(
                data_dir=kwargs.get("data_dir"),
                as_of=kwargs.get("as_of"),
                current_symbol=kwargs.get("current_symbol"),
                current_shares=kwargs.get("current_shares"),
                cash=kwargs.get("cash"),
                equity=kwargs.get("equity"),
                current_drawdown=kwargs.get("current_drawdown"),
                start_date=kwargs.get("start_date") or "2017-01-01",
                end_date=kwargs.get("end_date") or "2026-06-26",
                allow_historical=bool(kwargs.get("allow_historical")),
            )
        except Exception as exc:
            return TaskResult(
                status="INVALID",
                message=f"Core5+601225 实盘信号生成失败：{exc}",
                audit_status="LIVE_SIGNAL_INVALID",
                warnings=[str(exc)],
            )
