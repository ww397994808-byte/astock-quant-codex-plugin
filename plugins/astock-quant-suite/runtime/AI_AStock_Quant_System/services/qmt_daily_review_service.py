from __future__ import annotations

import json
from pathlib import Path

from core.result import TaskResult
from core.run_manager import RunManager


class QMTDailyReviewService:
    """Summarize the post-session state from a QMT order lifecycle report."""

    def run(self, lifecycle: str, trade_date: str | None = None, notes: str = "") -> TaskResult:
        lifecycle_path = self._resolve_lifecycle_path(lifecycle)
        lifecycle_data = json.loads(lifecycle_path.read_text(encoding="utf-8"))
        status = str(lifecycle_data.get("status") or "UNKNOWN")
        decision = self._decision_for(status, lifecycle_data)
        anomalies = self._anomalies_for(status, lifecycle_data)
        next_actions = self._next_actions_for(status, anomalies)
        payload = {
            "status": decision["status"],
            "trade_date": trade_date or "UNSPECIFIED",
            "lifecycle_path": str(lifecycle_path),
            "lifecycle_status": status,
            "candidate_run_id": lifecycle_data.get("candidate_run_id", ""),
            "qmt_run_id": lifecycle_data.get("qmt_run_id", ""),
            "observed_order": bool(lifecycle_data.get("observed_order")),
            "observed_trade": bool(lifecycle_data.get("observed_trade")),
            "summary": decision["summary"],
            "risk_level": decision["risk_level"],
            "next_day_gate": decision["next_day_gate"],
            "anomalies": anomalies,
            "next_actions": next_actions,
            "notes": notes,
            "hard_boundary": "日终复盘只总结证据和下一日边界；它不是新的交易许可。",
        }
        ctx = RunManager().create_run("qmt_daily_review")
        self._write_outputs(ctx.output_dir, payload, lifecycle_data)
        result_status = "VALID" if payload["status"] in {"REVIEW_READY", "DRY_RUN_REVIEW"} else "INVALID"
        return TaskResult(
            status=result_status,
            message=f"QMT 日终复盘生成完成：{payload['status']}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=result_status,
            warnings=anomalies,
            artifacts=payload,
        )

    def _resolve_lifecycle_path(self, lifecycle: str) -> Path:
        path = Path(lifecycle)
        if path.is_dir():
            path = path / "QMT_ORDER_LIFECYCLE.json"
        if not path.exists():
            raise FileNotFoundError(f"找不到 QMT 生命周期报告：{path}")
        return path

    def _decision_for(self, status: str, lifecycle: dict) -> dict:
        if status == "BLOCKED_NO_TRACKING":
            return {
                "status": "BLOCKED_REVIEW",
                "risk_level": "HIGH",
                "next_day_gate": "STOP_UNTIL_UPSTREAM_FIXED",
                "summary": "上游沙盒或生命周期证据未成立，不能进入下一日交易演练。",
            }
        if status == "NOT_OBSERVED_IN_QMT":
            return {
                "status": "BLOCKED_REVIEW",
                "risk_level": "HIGH",
                "next_day_gate": "REQUIRE_QMT_RECONCILIATION",
                "summary": "QMT 只读快照存在，但未观察到对应委托或成交，需要复核代码映射、账户和时间窗口。",
            }
        if status == "DRY_RUN_ONLY":
            return {
                "status": "DRY_RUN_REVIEW",
                "risk_level": "LOW",
                "next_day_gate": "CONTINUE_DRY_RUN_ONLY",
                "summary": "今天只有 dry-run 证据，没有 QMT 委托/成交观察，下一日仍只允许继续沙盒演练。",
            }
        if status == "ORDER_OBSERVED":
            return {
                "status": "REVIEW_READY",
                "risk_level": "MEDIUM",
                "next_day_gate": "REQUIRE_TRADE_OR_CANCEL_REVIEW",
                "summary": "QMT 只读快照观察到对应委托，但没有观察到对应成交，需要确认委托状态。",
            }
        if status == "TRADE_OBSERVED":
            return {
                "status": "REVIEW_READY",
                "risk_level": "MEDIUM",
                "next_day_gate": "REQUIRE_POSITION_AND_PNL_REVIEW",
                "summary": "QMT 只读快照观察到对应成交，下一日必须先复核持仓、成交价和风险敞口。",
            }
        return {
            "status": "BLOCKED_REVIEW",
            "risk_level": "HIGH",
            "next_day_gate": "UNKNOWN_STATE_REVIEW",
            "summary": f"未知生命周期状态：{status}",
        }

    def _anomalies_for(self, status: str, lifecycle: dict) -> list[str]:
        anomalies = list(lifecycle.get("warnings") or [])
        if status == "NOT_OBSERVED_IN_QMT":
            anomalies.append("QMT 快照未观察到对应委托/成交。")
        if status == "ORDER_OBSERVED" and not lifecycle.get("observed_trade"):
            anomalies.append("已观察到委托但未观察到成交，需要确认是否撤单、废单、未成交或延迟成交。")
        if status == "TRADE_OBSERVED" and not lifecycle.get("observed_order"):
            anomalies.append("观察到成交但没有匹配到委托记录，需要核对 QMT 委托读取字段。")
        return anomalies

    def _next_actions_for(self, status: str, anomalies: list[str]) -> list[dict]:
        actions = []
        if anomalies:
            actions.append({
                "type": "review_anomalies",
                "status": "pending",
                "action": "逐条复核异常；异常未关闭前，下一日不得推进真实下单。",
            })
        if status == "BLOCKED_NO_TRACKING":
            actions.append({
                "type": "fix_upstream",
                "status": "blocked",
                "action": "回到 qmt-handoff 或 qmt-order-sandbox，先让上游证据成立。",
            })
        elif status == "NOT_OBSERVED_IN_QMT":
            actions.append({
                "type": "rerun_qmt_readonly",
                "status": "pending",
                "action": "重新运行 qmt-check，并确认只读快照覆盖本次委托/成交时间窗口。",
            })
        elif status == "DRY_RUN_ONLY":
            actions.append({
                "type": "continue_sandbox",
                "status": "pending",
                "action": "下一日继续 dry-run 沙盒，不讨论真实下单。",
            })
        elif status == "ORDER_OBSERVED":
            actions.append({
                "type": "review_order_state",
                "status": "pending",
                "action": "确认委托状态、撤单/废单/未成交原因，再决定是否需要新的盘前检查。",
            })
        elif status == "TRADE_OBSERVED":
            actions.append({
                "type": "review_position_pnl",
                "status": "pending",
                "action": "复核成交价、持仓、现金、风险敞口和下一日止损/退出条件。",
            })
        return actions

    def _write_outputs(self, output_dir: Path, payload: dict, lifecycle: dict) -> None:
        (output_dir / "QMT_DAILY_REVIEW.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        (output_dir / "next_day_actions.json").write_text(
            json.dumps(payload["next_actions"], ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        lines = [
            "# QMT Daily Review",
            "",
            f"status: {payload['status']}",
            f"trade_date: {payload['trade_date']}",
            f"lifecycle_status: {payload['lifecycle_status']}",
            f"risk_level: {payload['risk_level']}",
            f"next_day_gate: {payload['next_day_gate']}",
            "",
            "## 今日结论",
            f"- {payload['summary']}",
            f"- observed_order: {'YES' if payload['observed_order'] else 'NO'}",
            f"- observed_trade: {'YES' if payload['observed_trade'] else 'NO'}",
            "",
            "## 生命周期证据",
        ]
        for item in lifecycle.get("timeline") or []:
            lines.append(f"- {item.get('step')}: {item.get('status')}")
        lines.extend(["", "## 异常与风险"])
        lines.extend([f"- {item}" for item in payload["anomalies"]] or ["- 当前复盘未发现新的异常。"])
        lines.extend(["", "## 下一日动作"])
        for item in payload["next_actions"]:
            lines.append(f"- [{item['status']}] {item['type']}: {item['action']}")
        if payload.get("notes"):
            lines.extend(["", "## 人工备注", f"- {payload['notes']}"])
        lines.extend([
            "",
            "## 硬边界",
            f"- {payload['hard_boundary']}",
            "- 下一日仍必须从 QMT 只读、pretrade-check、Runbook 和人工确认重新开始。",
        ])
        (output_dir / "QMT_DAILY_REVIEW.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
