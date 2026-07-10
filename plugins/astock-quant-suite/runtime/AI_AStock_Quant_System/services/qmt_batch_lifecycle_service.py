from __future__ import annotations

import csv
import json
from pathlib import Path

from core.result import TaskResult
from core.run_manager import RunManager
from services.qmt_order_lifecycle_service import QMTOrderLifecycleService


class QMTBatchLifecycleService:
    """Track batch dry-run receipts against readonly QMT snapshots."""

    def run(self, batch_sandbox: str, qmt_run_id: str | None = None) -> TaskResult:
        sandbox_path = self._resolve_batch_sandbox_path(batch_sandbox)
        sandbox = json.loads(sandbox_path.read_text(encoding="utf-8"))
        selected_qmt_run_id = (sandbox.get("qmt_run_id") or "") if qmt_run_id is None else qmt_run_id
        helper = QMTOrderLifecycleService()
        qmt_snapshot = helper._load_qmt_snapshot(selected_qmt_run_id)
        warnings: list[str] = []
        if sandbox.get("status") != "BATCH_DRY_RUN_RECORDED":
            warnings.append(f"批量沙盒未记录 dry-run 回执：{sandbox.get('status')}")
        if selected_qmt_run_id and not qmt_snapshot:
            warnings.append(f"找不到 QMT 只读快照：{selected_qmt_run_id}")
        if qmt_snapshot and not qmt_snapshot.get("ok"):
            warnings.append("QMT 只读快照不是 ok=true，只能作为异常线索，不能作为通过证据。")

        items = []
        for receipt_item in sandbox.get("receipts") or []:
            order = receipt_item.get("order") or {}
            receipt = receipt_item.get("receipt") or {}
            row_warnings = []
            if receipt.get("status") != "DRY_RUN_RECORDED":
                row_warnings.append(f"row {receipt_item.get('row')}: 回执不是 DRY_RUN_RECORDED：{receipt.get('status')}")
            observed_order = helper._find_match(order, qmt_snapshot.get("orders_today") or [])
            observed_trade = helper._find_match(order, qmt_snapshot.get("trades_today") or [])
            row_status = self._row_status(sandbox, receipt, observed_order, observed_trade, qmt_snapshot)
            items.append({
                "row": receipt_item.get("row"),
                "status": row_status,
                "order": order,
                "receipt": receipt,
                "observed_order": observed_order,
                "observed_trade": observed_trade,
                "warnings": row_warnings,
            })
            warnings.extend(row_warnings)

        summary = self._summary(items)
        status = self._batch_status(sandbox, items, qmt_snapshot)
        payload = {
            "status": status,
            "batch_sandbox_path": str(sandbox_path),
            "candidate_run_id": sandbox.get("candidate_run_id", ""),
            "qmt_run_id": selected_qmt_run_id,
            "summary": summary,
            "items": items,
            "warnings": warnings,
            "hard_boundary": "qmt-batch-lifecycle 只做批量只读追踪；它不发送、撤销或修改任何 QMT 委托。",
        }
        ctx = RunManager().create_run("qmt_batch_lifecycle")
        self._write_outputs(ctx.output_dir, payload)
        fatal = sandbox.get("status") != "BATCH_DRY_RUN_RECORDED"
        result_status = "VALID" if status in {"BATCH_DRY_RUN_ONLY", "BATCH_ORDER_OBSERVED", "BATCH_TRADE_OBSERVED", "BATCH_PARTIAL_OBSERVED"} and not fatal else "INVALID"
        return TaskResult(
            status=result_status,
            message=f"批量 QMT 订单生命周期追踪完成：{status}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=result_status,
            warnings=warnings,
            artifacts=payload,
        )

    def _resolve_batch_sandbox_path(self, batch_sandbox: str) -> Path:
        path = Path(batch_sandbox)
        if path.is_dir():
            path = path / "QMT_BATCH_ORDER_SANDBOX.json"
        if not path.exists():
            raise FileNotFoundError(f"找不到批量 QMT 沙盒报告：{path}")
        return path

    def _row_status(self, sandbox: dict, receipt: dict, observed_order: dict | None, observed_trade: dict | None, qmt_snapshot: dict) -> str:
        if sandbox.get("status") != "BATCH_DRY_RUN_RECORDED" or receipt.get("status") != "DRY_RUN_RECORDED":
            return "BLOCKED_NO_TRACKING"
        if observed_trade:
            return "TRADE_OBSERVED"
        if observed_order:
            return "ORDER_OBSERVED"
        if qmt_snapshot:
            return "NOT_OBSERVED_IN_QMT"
        return "DRY_RUN_ONLY"

    def _summary(self, items: list[dict]) -> dict:
        summary = {
            "total_orders": len(items),
            "blocked": 0,
            "dry_run_only": 0,
            "order_observed": 0,
            "trade_observed": 0,
            "not_observed": 0,
        }
        for item in items:
            status = item["status"]
            if status == "BLOCKED_NO_TRACKING":
                summary["blocked"] += 1
            elif status == "DRY_RUN_ONLY":
                summary["dry_run_only"] += 1
            elif status == "ORDER_OBSERVED":
                summary["order_observed"] += 1
            elif status == "TRADE_OBSERVED":
                summary["trade_observed"] += 1
            elif status == "NOT_OBSERVED_IN_QMT":
                summary["not_observed"] += 1
        return summary

    def _batch_status(self, sandbox: dict, items: list[dict], qmt_snapshot: dict) -> str:
        if sandbox.get("status") != "BATCH_DRY_RUN_RECORDED" or any(item["status"] == "BLOCKED_NO_TRACKING" for item in items):
            return "BATCH_BLOCKED_NO_TRACKING"
        statuses = {item["status"] for item in items}
        if statuses == {"DRY_RUN_ONLY"}:
            return "BATCH_DRY_RUN_ONLY"
        if statuses == {"TRADE_OBSERVED"}:
            return "BATCH_TRADE_OBSERVED"
        if statuses <= {"ORDER_OBSERVED", "TRADE_OBSERVED"} and "ORDER_OBSERVED" in statuses:
            return "BATCH_ORDER_OBSERVED"
        if qmt_snapshot and statuses:
            return "BATCH_PARTIAL_OBSERVED"
        return "BATCH_DRY_RUN_ONLY"

    def _write_outputs(self, output_dir: Path, payload: dict) -> None:
        (output_dir / "QMT_BATCH_ORDER_LIFECYCLE.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        with (output_dir / "batch_lifecycle_timeline.csv").open("w", encoding="utf-8", newline="") as f:
            fieldnames = ["row", "status", "symbol", "action", "quantity", "receipt_status", "observed_order", "observed_trade"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in payload["items"]:
                order = item.get("order") or {}
                receipt = item.get("receipt") or {}
                writer.writerow({
                    "row": item.get("row"),
                    "status": item.get("status"),
                    "symbol": order.get("symbol"),
                    "action": order.get("action"),
                    "quantity": order.get("quantity"),
                    "receipt_status": receipt.get("status"),
                    "observed_order": bool(item.get("observed_order")),
                    "observed_trade": bool(item.get("observed_trade")),
                })
        lines = [
            "# QMT Batch Order Lifecycle",
            "",
            f"status: {payload['status']}",
            f"candidate_run_id: {payload.get('candidate_run_id') or 'MISSING'}",
            f"qmt_run_id: {payload.get('qmt_run_id') or 'MISSING'}",
            "",
            "## 汇总",
        ]
        for key, value in payload["summary"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## 逐笔状态"])
        for item in payload["items"]:
            order = item.get("order") or {}
            lines.append(
                f"- row {item.get('row')}: {item.get('status')} {order.get('symbol')} {order.get('action')} {order.get('quantity')}"
            )
        lines.extend(["", "## 警告"])
        lines.extend([f"- {item}" for item in payload["warnings"]] or ["- 当前批量生命周期追踪未发现新的警告。"])
        lines.extend([
            "",
            "## 硬边界",
            f"- {payload['hard_boundary']}",
            "- 批量只读快照只能证明观察到委托/成交信息，不能证明策略可盈利，也不能替代人工复核。",
        ])
        (output_dir / "QMT_BATCH_ORDER_LIFECYCLE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
