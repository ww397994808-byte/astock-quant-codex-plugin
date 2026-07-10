from __future__ import annotations

import json
import yaml
from pathlib import Path

from audit.pre_trade_check import PreTradeChecker
from core.result import TaskResult
from core.run_manager import RunManager
from services.stage_check_service import StageCheckService


class PreTradeService:
    def run(
        self,
        strategy: str,
        symbol: str,
        confirmation: str = "",
        run_id: str = "latest",
        plan_run_id: str | None = None,
        qmt_run_id: str | None = None,
    ) -> TaskResult:
        path = Path("config/qmt_config.yaml")
        config = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
        defaults = {
            "qmt_connected": False,
            "account_available": False,
            "dry_run": True,
            "enable_real_trade": False,
            "data_latest": False,
            "symbol_tradable": False,
            "not_limit_price": False,
            "daily_loss_ok": False,
            "single_position_ok": False,
            "total_position_ok": False,
            "no_duplicate_order": False,
            "no_abnormal_order": False,
        }
        defaults.update(config or {})

        stage_result = StageCheckService().run(run_id=run_id, plan_run_id=plan_run_id, qmt_run_id=qmt_run_id)
        stage = stage_result.artifacts.get("stage_gate", {}).get("stage", "INVALID")
        stage_failures = list(stage_result.warnings)
        qmt_snapshot = self._load_qmt_snapshot(stage_result.artifacts.get("qmt_run_id", ""))
        if qmt_snapshot:
            checks = qmt_snapshot.get("checks", {})
            defaults["qmt_connected"] = bool(checks.get("qmt_connected") or qmt_snapshot.get("connected"))
            defaults["account_available"] = bool(checks.get("account_available"))

        result = PreTradeChecker().check(defaults, audit_status=stage_result.audit_status or "INVALID", confirmation=confirmation)
        if stage != "QMT_READONLY_READY":
            result.failures.insert(0, f"阶段未达到 QMT_READONLY_READY：{stage}")
            result.failures.extend([f"阶段阻断：{item}" for item in stage_failures])
        status = "VALID" if result.ok else "INVALID"
        ctx = RunManager().create_run("pretrade")
        self._write_report(ctx.output_dir, strategy, symbol, status, stage, result.failures)
        return TaskResult(
            status,
            "实盘前检查完成",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=status,
            warnings=result.failures,
            artifacts={"strategy": strategy, "symbol": symbol, "stage": stage},
        )

    def _load_qmt_snapshot(self, qmt_run_id: str) -> dict:
        if not qmt_run_id:
            return {}
        path = Path("reports") / qmt_run_id / "qmt_account_snapshot.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_report(self, output_dir: Path, strategy: str, symbol: str, status: str, stage: str, failures: list[str]) -> None:
        lines = [
            "# Pretrade Report",
            "",
            f"status: {status}",
            f"strategy: {strategy}",
            f"symbol: {symbol}",
            f"stage: {stage}",
            "",
            "## Failures",
        ]
        lines.extend([f"- {item}" for item in failures] or ["- 未发现实盘前阻断项。"])
        lines.extend([
            "",
            "说明：pretrade VALID 也不代表策略一定盈利；它只表示本次下单前安全检查通过。",
        ])
        (output_dir / "pretrade_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
