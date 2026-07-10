from __future__ import annotations

import csv
import json
from pathlib import Path

from core.result import TaskResult
from core.run_manager import RunManager


class QMTBatchDailyReviewService:
    """Summarize a batch lifecycle report into next-day operational gates."""

    def run(self, batch_lifecycle: str, trade_date: str | None = None, notes: str = "") -> TaskResult:
        lifecycle_path = self._resolve_lifecycle_path(batch_lifecycle)
        lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
        decision = self._decision_for(str(lifecycle.get("status") or "UNKNOWN"), lifecycle)
        row_actions = [self._row_action(item) for item in lifecycle.get("items") or []]
        anomalies = self._anomalies_for(lifecycle, row_actions)
        payload = {
            "status": decision["status"],
            "trade_date": trade_date or "UNSPECIFIED",
            "batch_lifecycle_path": str(lifecycle_path),
            "batch_lifecycle_status": lifecycle.get("status", "UNKNOWN"),
            "candidate_run_id": lifecycle.get("candidate_run_id", ""),
            "qmt_run_id": lifecycle.get("qmt_run_id", ""),
            "summary": lifecycle.get("summary", {}),
            "risk_level": decision["risk_level"],
            "next_day_gate": decision["next_day_gate"],
            "conclusion": decision["summary"],
            "row_actions": row_actions,
            "anomalies": anomalies,
            "notes": notes,
            "hard_boundary": "批量日终复盘只总结证据和下一日边界；它不是新的交易许可。",
        }
        ctx = RunManager().create_run("qmt_batch_daily_review")
        self._write_outputs(ctx.output_dir, payload)
        result_status = "VALID" if payload["status"] in {"BATCH_REVIEW_READY", "BATCH_DRY_RUN_REVIEW"} else "INVALID"
        return TaskResult(
            status=result_status,
            message=f"批量 QMT 日终复盘生成完成：{payload['status']}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=result_status,
            warnings=anomalies,
            artifacts=payload,
        )

    def _resolve_lifecycle_path(self, batch_lifecycle: str) -> Path:
        path = Path(batch_lifecycle)
        if path.is_dir():
            path = path / "QMT_BATCH_ORDER_LIFECYCLE.json"
        if not path.exists():
            raise FileNotFoundError(f"找不到批量 QMT 生命周期报告：{path}")
        return path

    def _decision_for(self, status: str, lifecycle: dict) -> dict:
        if status == "BATCH_BLOCKED_NO_TRACKING":
            return {
                "status": "BATCH_BLOCKED_REVIEW",
                "risk_level": "HIGH",
                "next_day_gate": "STOP_BATCH_UNTIL_UPSTREAM_FIXED",
                "summary": "批量沙盒或生命周期证据未成立，下一日不得推进批量交易演练。",
            }
        if status == "BATCH_DRY_RUN_ONLY":
            return {
                "status": "BATCH_DRY_RUN_REVIEW",
                "risk_level": "LOW",
                "next_day_gate": "CONTINUE_BATCH_DRY_RUN_ONLY",
                "summary": "整批只有 dry-run 证据，下一日继续批量沙盒演练。",
            }
        if status == "BATCH_ORDER_OBSERVED":
            return {
                "status": "BATCH_REVIEW_READY",
                "risk_level": "MEDIUM",
                "next_day_gate": "REVIEW_BATCH_ORDER_STATES",
                "summary": "批量只读快照观察到委托，需要逐笔确认委托状态和未成交原因。",
            }
        if status == "BATCH_TRADE_OBSERVED":
            return {
                "status": "BATCH_REVIEW_READY",
                "risk_level": "MEDIUM",
                "next_day_gate": "REVIEW_BATCH_POSITION_AND_PNL",
                "summary": "批量只读快照观察到成交，下一日先复核持仓、成交价和组合风险敞口。",
            }
        if status == "BATCH_PARTIAL_OBSERVED":
            return {
                "status": "BATCH_REVIEW_READY",
                "risk_level": "HIGH",
                "next_day_gate": "RECONCILE_PARTIAL_BATCH_OBSERVATION",
                "summary": "批量订单只被部分观察到，需要逐笔对账后才能继续。",
            }
        return {
            "status": "BATCH_BLOCKED_REVIEW",
            "risk_level": "HIGH",
            "next_day_gate": "UNKNOWN_BATCH_STATE_REVIEW",
            "summary": f"未知批量生命周期状态：{status}",
        }

    def _row_action(self, item: dict) -> dict:
        order = item.get("order") or {}
        status = item.get("status")
        base = {
            "row": item.get("row"),
            "symbol": order.get("symbol", ""),
            "action": order.get("action", ""),
            "quantity": order.get("quantity", ""),
            "status": status,
        }
        if status == "BLOCKED_NO_TRACKING":
            return dict(base, next_day_action="fix_upstream", gate="STOP_ROW_UNTIL_EVIDENCE_FIXED", detail="该行沙盒或回执未成立，下一日不得推进。")
        if status == "DRY_RUN_ONLY":
            return dict(base, next_day_action="continue_dry_run", gate="DRY_RUN_ONLY", detail="该行只有 dry-run 证据，继续沙盒。")
        if status == "NOT_OBSERVED_IN_QMT":
            return dict(base, next_day_action="reconcile_qmt_snapshot", gate="REQUIRE_QMT_RECONCILIATION", detail="QMT 快照未观察到该行委托/成交。")
        if status == "ORDER_OBSERVED":
            return dict(base, next_day_action="review_order_state", gate="REQUIRE_ORDER_STATE_REVIEW", detail="该行观察到委托但未观察到成交。")
        if status == "TRADE_OBSERVED":
            return dict(base, next_day_action="review_position_pnl", gate="REQUIRE_POSITION_AND_PNL_REVIEW", detail="该行观察到成交，先复核持仓和风险敞口。")
        return dict(base, next_day_action="manual_review", gate="UNKNOWN_ROW_STATE", detail="未知逐笔状态，需要人工复核。")

    def _anomalies_for(self, lifecycle: dict, row_actions: list[dict]) -> list[str]:
        anomalies = list(lifecycle.get("warnings") or [])
        for action in row_actions:
            if action["status"] in {"BLOCKED_NO_TRACKING", "NOT_OBSERVED_IN_QMT"}:
                anomalies.append(f"row {action['row']} {action['symbol']}: {action['detail']}")
        return anomalies

    def _write_outputs(self, output_dir: Path, payload: dict) -> None:
        (output_dir / "QMT_BATCH_DAILY_REVIEW.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        with (output_dir / "batch_next_day_actions.csv").open("w", encoding="utf-8", newline="") as f:
            fieldnames = ["row", "symbol", "action", "quantity", "status", "next_day_action", "gate", "detail"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(payload["row_actions"])
        lines = [
            "# QMT Batch Daily Review",
            "",
            f"status: {payload['status']}",
            f"trade_date: {payload['trade_date']}",
            f"batch_lifecycle_status: {payload['batch_lifecycle_status']}",
            f"risk_level: {payload['risk_level']}",
            f"next_day_gate: {payload['next_day_gate']}",
            "",
            "## 今日结论",
            f"- {payload['conclusion']}",
            "",
            "## 批量汇总",
        ]
        for key, value in payload.get("summary", {}).items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## 逐笔下一日动作"])
        for item in payload["row_actions"]:
            lines.append(
                f"- row {item['row']} {item['symbol']} {item['action']} {item['quantity']}: {item['gate']} / {item['next_day_action']} - {item['detail']}"
            )
        lines.extend(["", "## 异常与风险"])
        lines.extend([f"- {item}" for item in payload["anomalies"]] or ["- 当前批量复盘未发现新的异常。"])
        if payload.get("notes"):
            lines.extend(["", "## 人工备注", f"- {payload['notes']}"])
        lines.extend([
            "",
            "## 硬边界",
            f"- {payload['hard_boundary']}",
            "- 下一日仍必须从 QMT 只读、pretrade-check、Runbook 和人工确认重新开始。",
        ])
        (output_dir / "QMT_BATCH_DAILY_REVIEW.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
