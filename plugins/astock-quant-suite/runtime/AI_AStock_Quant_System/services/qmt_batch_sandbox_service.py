from __future__ import annotations

import csv
import json
import yaml
from datetime import datetime
from pathlib import Path

from core.order import Order
from core.result import TaskResult
from core.run_manager import RunManager
from qmt.qmt_broker_stub import QMTBrokerStub


class QMTBatchSandboxService:
    """Record dry-run receipts for a batch handoff without touching real QMT."""

    def run(self, batch_handoff: str, config: str = "config/qmt_config.yaml", confirmation: str = "") -> TaskResult:
        batch_path = self._resolve_batch_path(batch_handoff)
        batch = json.loads(batch_path.read_text(encoding="utf-8"))
        warnings = self._safety_warnings(batch, Path(config))
        receipts = []
        if not warnings:
            for draft in batch.get("drafts") or []:
                order = self._order_from_draft(draft)
                receipts.append({
                    "row": draft.get("row"),
                    "order": draft.get("order") or {},
                    "receipt": self._dry_run_receipt(order, confirmation),
                })
        status = "BATCH_DRY_RUN_RECORDED" if not warnings else "BATCH_BLOCKED_SANDBOX_ONLY"
        if warnings:
            receipts = [
                {
                    "row": draft.get("row"),
                    "order": draft.get("order") or {},
                    "receipt": {"status": "NOT_SENT", "message": "batch sandbox 阻断，未记录 dry-run 委托。"},
                }
                for draft in batch.get("drafts") or []
            ]

        ctx = RunManager().create_run("qmt_batch_sandbox")
        payload = {
            "status": status,
            "batch_handoff_path": str(batch_path),
            "candidate_run_id": batch.get("candidate_run_id", ""),
            "qmt_run_id": batch.get("qmt_run_id", ""),
            "total_orders": len(receipts),
            "recorded_orders": sum(1 for item in receipts if item.get("receipt", {}).get("status") == "DRY_RUN_RECORDED"),
            "blocked_orders": sum(1 for item in receipts if item.get("receipt", {}).get("status") != "DRY_RUN_RECORDED"),
            "receipts": receipts,
            "warnings": warnings,
            "confirmation_supplied": bool(confirmation),
            "hard_boundary": "qmt-batch-sandbox 只生成批量 dry-run 回执；它不连接真实 QMT，不发送真实委托。",
        }
        self._write_outputs(ctx.output_dir, payload)
        result_status = "VALID" if status == "BATCH_DRY_RUN_RECORDED" else "INVALID"
        return TaskResult(
            status=result_status,
            message=f"批量 QMT 订单沙盒检查完成：{status}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=result_status,
            warnings=warnings,
            artifacts=payload,
        )

    def _resolve_batch_path(self, batch_handoff: str) -> Path:
        path = Path(batch_handoff)
        if path.is_dir():
            path = path / "QMT_BATCH_HANDOFF_PACKAGE.json"
        if not path.exists():
            raise FileNotFoundError(f"找不到批量 QMT 交接包：{path}")
        return path

    def _safety_warnings(self, batch: dict, config_path: Path) -> list[str]:
        warnings: list[str] = []
        if batch.get("status") != "BATCH_DRAFT_READY":
            warnings.append(f"批量交接草案未到 BATCH_DRAFT_READY：{batch.get('status')}")
        for blocker in batch.get("blockers") or []:
            warnings.append(f"批量交接草案仍有阻断项：{blocker}")
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
        if bool(config.get("dry_run", True)) is not True:
            warnings.append("batch sandbox 要求 dry_run=true，当前配置不是安全沙盒状态。")
        if bool(config.get("enable_real_trade", False)):
            warnings.append("batch sandbox 要求 enable_real_trade=false，当前配置打开了真实交易开关。")
        if config.get("emergency_stop"):
            warnings.append("emergency_stop 已触发，停止任何批量订单演练。")
        return warnings

    def _order_from_draft(self, draft: dict) -> Order:
        order = draft.get("order") or {}
        return Order(
            symbol=str(order.get("symbol") or ""),
            action=str(order.get("action") or ""),
            quantity=int(order.get("quantity") or 0),
            signal_time=datetime.fromisoformat(order["signal_time"]),
            execute_time=datetime.fromisoformat(order["execute_time"]),
            price=order.get("price"),
            status=str(order.get("status") or "PENDING"),
            reason=str(order.get("reason") or "qmt_batch_sandbox"),
            timeframe=str(order.get("timeframe") or "1d"),
        )

    def _dry_run_receipt(self, order: Order, confirmation: str) -> dict:
        raw = QMTBrokerStub(dry_run=True).place_order(order)
        return {
            "status": "DRY_RUN_RECORDED",
            "broker_status": raw.get("status"),
            "broker_message": raw.get("message"),
            "confirmation_ignored": confirmation == "CONFIRM_REAL_TRADE",
            "order_id": f"DRYRUN-{order.symbol}-{order.execute_time.strftime('%Y%m%d%H%M%S')}",
        }

    def _write_outputs(self, output_dir: Path, payload: dict) -> None:
        (output_dir / "QMT_BATCH_ORDER_SANDBOX.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        with (output_dir / "batch_order_receipts.csv").open("w", encoding="utf-8", newline="") as f:
            fieldnames = ["row", "symbol", "action", "quantity", "receipt_status", "broker_status", "order_id"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in payload["receipts"]:
                order = item.get("order") or {}
                receipt = item.get("receipt") or {}
                writer.writerow({
                    "row": item.get("row"),
                    "symbol": order.get("symbol"),
                    "action": order.get("action"),
                    "quantity": order.get("quantity"),
                    "receipt_status": receipt.get("status"),
                    "broker_status": receipt.get("broker_status", ""),
                    "order_id": receipt.get("order_id", ""),
                })
        lines = [
            "# QMT Batch Order Sandbox",
            "",
            f"status: {payload['status']}",
            f"total_orders: {payload['total_orders']}",
            f"recorded_orders: {payload['recorded_orders']}",
            f"blocked_orders: {payload['blocked_orders']}",
            f"candidate_run_id: {payload.get('candidate_run_id') or 'MISSING'}",
            f"qmt_run_id: {payload.get('qmt_run_id') or 'MISSING'}",
            "",
            "## 批量回执",
        ]
        for item in payload["receipts"]:
            order = item.get("order") or {}
            receipt = item.get("receipt") or {}
            lines.append(
                f"- row {item.get('row')}: {receipt.get('status')} {order.get('symbol')} {order.get('action')} {order.get('quantity')}"
            )
        lines.extend(["", "## 阻断项"])
        lines.extend([f"- {item}" for item in payload["warnings"]] or ["- 当前批量沙盒未发现阻断项，已记录 dry-run 回执。"])
        lines.extend([
            "",
            "## 硬边界",
            f"- {payload['hard_boundary']}",
            "- 即使传入 CONFIRM_REAL_TRADE，本命令也只记录 dry-run，不允许真实下单。",
            "- 批量真实下单适配必须另行实现，并逐笔重新经过 pretrade-check、人工确认和 QMT 安全门。",
        ])
        (output_dir / "QMT_BATCH_ORDER_SANDBOX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
