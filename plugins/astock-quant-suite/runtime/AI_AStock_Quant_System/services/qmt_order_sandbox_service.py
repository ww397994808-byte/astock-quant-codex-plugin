from __future__ import annotations

import json
import yaml
from datetime import datetime
from pathlib import Path

from core.order import Order
from core.result import TaskResult
from core.run_manager import RunManager
from qmt.qmt_broker_stub import QMTBrokerStub


class QMTOrderSandboxService:
    """Record a dry-run receipt from a handoff draft without touching real QMT."""

    def run(
        self,
        handoff: str,
        config: str = "config/qmt_config.yaml",
        confirmation: str = "",
    ) -> TaskResult:
        handoff_path = self._resolve_handoff_path(handoff)
        handoff_data = json.loads(handoff_path.read_text(encoding="utf-8"))
        safety_warnings = self._safety_warnings(handoff_data, Path(config))
        order = self._order_from_handoff(handoff_data)

        status = "DRY_RUN_RECORDED" if not safety_warnings else "BLOCKED_SANDBOX_ONLY"
        receipt = self._dry_run_receipt(order, confirmation) if not safety_warnings else {
            "status": "NOT_SENT",
            "message": "sandbox 阻断，未记录 dry-run 委托。",
        }
        ctx = RunManager().create_run("qmt_order_sandbox")
        payload = {
            "status": status,
            "handoff_path": str(handoff_path),
            "candidate_run_id": handoff_data.get("candidate_run_id", ""),
            "qmt_run_id": handoff_data.get("qmt_run_id", ""),
            "order": handoff_data.get("order", {}),
            "receipt": receipt,
            "warnings": safety_warnings,
            "confirmation_supplied": bool(confirmation),
            "hard_boundary": "qmt-order-sandbox 只生成 dry-run 回执；它不连接真实 QMT，不发送真实委托。",
        }
        self._write_outputs(ctx.output_dir, payload)
        result_status = "VALID" if status == "DRY_RUN_RECORDED" else "INVALID"
        return TaskResult(
            status=result_status,
            message=f"QMT 订单沙盒检查完成：{status}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=result_status,
            warnings=safety_warnings,
            artifacts=payload,
        )

    def _resolve_handoff_path(self, handoff: str) -> Path:
        path = Path(handoff)
        if path.is_dir():
            path = path / "QMT_HANDOFF_PACKAGE.json"
        if not path.exists():
            raise FileNotFoundError(f"找不到 QMT 交接包：{path}")
        return path

    def _safety_warnings(self, handoff: dict, config_path: Path) -> list[str]:
        warnings: list[str] = []
        if handoff.get("status") != "DRAFT_READY":
            warnings.append(f"QMT 交接草案未到 DRAFT_READY：{handoff.get('status')}")
        for blocker in handoff.get("blockers") or []:
            warnings.append(f"交接草案仍有阻断项：{blocker}")
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
        dry_run = bool(config.get("dry_run", True))
        enable_real_trade = bool(config.get("enable_real_trade", False))
        if dry_run is not True:
            warnings.append("sandbox 要求 dry_run=true，当前配置不是安全沙盒状态。")
        if enable_real_trade:
            warnings.append("sandbox 要求 enable_real_trade=false，当前配置打开了真实交易开关。")
        if config.get("emergency_stop"):
            warnings.append("emergency_stop 已触发，停止任何订单演练。")
        return warnings

    def _order_from_handoff(self, handoff: dict) -> Order:
        order = handoff.get("order") or {}
        return Order(
            symbol=str(order.get("symbol") or ""),
            action=str(order.get("action") or ""),
            quantity=int(order.get("quantity") or 0),
            signal_time=datetime.fromisoformat(order["signal_time"]),
            execute_time=datetime.fromisoformat(order["execute_time"]),
            price=order.get("price"),
            status=str(order.get("status") or "PENDING"),
            reason=str(order.get("reason") or "qmt_order_sandbox"),
            timeframe=str(order.get("timeframe") or "1d"),
        )

    def _dry_run_receipt(self, order: Order, confirmation: str) -> dict:
        broker = QMTBrokerStub(dry_run=True)
        raw = broker.place_order(order)
        return {
            "status": "DRY_RUN_RECORDED",
            "broker_status": raw.get("status"),
            "broker_message": raw.get("message"),
            "confirmation_ignored": confirmation == "CONFIRM_REAL_TRADE",
            "order_id": f"DRYRUN-{order.symbol}-{order.execute_time.strftime('%Y%m%d%H%M%S')}",
        }

    def _write_outputs(self, output_dir: Path, payload: dict) -> None:
        (output_dir / "QMT_ORDER_SANDBOX.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output_dir / "order_receipt.json").write_text(
            json.dumps(payload["receipt"], ensure_ascii=False, indent=2), encoding="utf-8"
        )
        order = payload.get("order") or {}
        receipt = payload.get("receipt") or {}
        lines = [
            "# QMT Order Sandbox",
            "",
            f"status: {payload['status']}",
            f"candidate_run_id: {payload.get('candidate_run_id') or 'MISSING'}",
            f"qmt_run_id: {payload.get('qmt_run_id') or 'MISSING'}",
            "",
            "## 订单草案",
            f"- symbol: {order.get('symbol')}",
            f"- action: {order.get('action')}",
            f"- quantity: {order.get('quantity')}",
            f"- price: {order.get('price')}",
            f"- signal_time: {order.get('signal_time')}",
            f"- execute_time: {order.get('execute_time')}",
            "",
            "## 沙盒回执",
            f"- receipt_status: {receipt.get('status')}",
            f"- broker_status: {receipt.get('broker_status', 'MISSING')}",
            f"- order_id: {receipt.get('order_id', 'MISSING')}",
            f"- confirmation_ignored: {receipt.get('confirmation_ignored', False)}",
            "",
            "## 阻断项",
        ]
        lines.extend([f"- {item}" for item in payload["warnings"]] or ["- 当前沙盒未发现阻断项，已记录 dry-run 回执。"])
        lines.extend([
            "",
            "## 硬边界",
            f"- {payload['hard_boundary']}",
            "- 即使传入 CONFIRM_REAL_TRADE，本命令也只记录 dry-run，不允许真实下单。",
            "- 真实下单适配必须另行实现，并重新经过 pretrade-check、人工确认和 QMT 安全门。",
        ])
        (output_dir / "QMT_ORDER_SANDBOX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
