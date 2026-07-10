from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from core.order import Order
from core.result import TaskResult
from core.run_manager import RunManager
from qmt.qmt_broker_stub import QMTBrokerStub


class Core5SignalSandboxService:
    """Record dry-run receipts from a Core5 live-signal package.

    This class is deliberately broker-free. It reads the generated signal package,
    validates the draft orders, and writes simulated receipts only.
    """

    SAFE_SIGNAL_STATUSES = {"SIGNAL_READY"}

    def run(self, signal: str, config: str = "config/qmt_config.yaml", confirmation: str = "") -> TaskResult:
        signal_path = self._resolve_signal_path(signal)
        signal_dir = signal_path.parent
        payload = json.loads(signal_path.read_text(encoding="utf-8"))
        drafts = self._read_order_drafts(signal_dir / "order_drafts.csv")
        warnings = self._safety_warnings(payload, drafts, Path(config))

        receipts = []
        if not warnings:
            for row_no, draft in enumerate(drafts, start=1):
                order = self._order_from_draft(draft)
                receipts.append(
                    {
                        "row": row_no,
                        "order": draft,
                        "receipt": self._dry_run_receipt(order, confirmation),
                    }
                )
        else:
            receipts = [
                {
                    "row": row_no,
                    "order": draft,
                    "receipt": {"status": "NOT_SENT", "message": "模拟盘安全门阻断，未记录委托。"},
                }
                for row_no, draft in enumerate(drafts, start=1)
            ]

        status = "CORE5_SIGNAL_DRY_RUN_RECORDED" if receipts and not warnings else "CORE5_SIGNAL_SANDBOX_BLOCKED"
        ctx = RunManager().create_run("core5_signal_sandbox")
        out = {
            "status": status,
            "source_signal": str(signal_path),
            "source_signal_status": payload.get("status"),
            "source_signal_mode": payload.get("mode", ""),
            "total_orders": len(receipts),
            "recorded_orders": sum(1 for item in receipts if item.get("receipt", {}).get("status") == "DRY_RUN_RECORDED"),
            "blocked_orders": sum(1 for item in receipts if item.get("receipt", {}).get("status") != "DRY_RUN_RECORDED"),
            "receipts": receipts,
            "warnings": warnings,
            "confirmation_supplied": bool(confirmation),
            "hard_boundary": "core5-signal-sandbox 只生成模拟盘 dry-run 回执；不连接 QMT，不发送真实委托。",
        }
        self._write_outputs(ctx.output_dir, out)
        result_status = "VALID" if status == "CORE5_SIGNAL_DRY_RUN_RECORDED" else "INVALID"
        return TaskResult(
            status=result_status,
            message=f"Core5 模拟盘订单演练完成：{status}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=result_status,
            warnings=warnings,
            artifacts=out,
        )

    def _resolve_signal_path(self, signal: str) -> Path:
        path = Path(signal)
        if path.is_dir():
            path = path / "LIVE_SIGNAL.json"
        if not path.exists():
            raise FileNotFoundError(f"找不到 Core5 信号包：{path}")
        return path

    def _read_order_drafts(self, path: Path) -> list[dict[str, str]]:
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def _safety_warnings(self, payload: dict[str, Any], drafts: list[dict[str, str]], config_path: Path) -> list[str]:
        warnings: list[str] = []
        if payload.get("status") not in self.SAFE_SIGNAL_STATUSES:
            warnings.append(f"信号包未到 SIGNAL_READY：{payload.get('status')}")
        for blocker in payload.get("blockers") or []:
            warnings.append(f"信号包仍有阻断项：{blocker}")
        if not drafts:
            warnings.append("order_drafts.csv 为空；没有可以模拟的订单。")

        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
        if bool(config.get("dry_run", True)) is not True:
            warnings.append("模拟盘要求 dry_run=true，当前配置不是安全沙盒状态。")
        if bool(config.get("enable_real_trade", False)):
            warnings.append("模拟盘要求 enable_real_trade=false，当前配置打开了真实交易开关。")
        if config.get("emergency_stop"):
            warnings.append("emergency_stop 已触发，停止任何模拟盘订单演练。")

        for row_no, draft in enumerate(drafts, start=1):
            action = str(draft.get("action") or "").upper()
            quantity = int(float(draft.get("quantity") or 0))
            signal_time = str(draft.get("signal_time") or "")
            execute_time = str(draft.get("execute_time") or "")
            if action not in {"BUY", "SELL"}:
                warnings.append(f"第 {row_no} 行 action 不是 BUY/SELL：{action}")
            if quantity <= 0 or quantity % 100 != 0:
                warnings.append(f"第 {row_no} 行 quantity 必须是正数且为 100 股整数倍：{quantity}")
            if not signal_time or not execute_time:
                warnings.append(f"第 {row_no} 行缺少 signal_time 或 execute_time。")
                continue
            try:
                signal_dt = datetime.fromisoformat(signal_time)
                execute_dt = datetime.fromisoformat(execute_time)
            except ValueError:
                warnings.append(f"第 {row_no} 行时间格式不是 ISO 格式。")
                continue
            if execute_dt <= signal_dt:
                warnings.append(f"第 {row_no} 行执行时间必须晚于信号时间，避免同根K线成交。")
        return warnings

    def _order_from_draft(self, draft: dict[str, str]) -> Order:
        price_text = str(draft.get("price") or "").strip()
        return Order(
            symbol=str(draft.get("symbol") or ""),
            action=str(draft.get("action") or "").upper(),
            quantity=int(float(draft.get("quantity") or 0)),
            signal_time=datetime.fromisoformat(str(draft["signal_time"])),
            execute_time=datetime.fromisoformat(str(draft["execute_time"])),
            price=float(price_text) if price_text else None,
            status="PENDING",
            reason=str(draft.get("reason") or "core5_signal_sandbox"),
            timeframe=str(draft.get("timeframe") or "30m"),
        )

    def _dry_run_receipt(self, order: Order, confirmation: str) -> dict[str, Any]:
        raw = QMTBrokerStub(dry_run=True).place_order(order)
        return {
            "status": "DRY_RUN_RECORDED",
            "broker_status": raw.get("status"),
            "broker_message": raw.get("message"),
            "confirmation_ignored": confirmation == "CONFIRM_REAL_TRADE",
            "order_id": f"CORE5-SIM-{order.symbol}-{order.execute_time.strftime('%Y%m%d%H%M%S')}",
        }

    def _write_outputs(self, output_dir: Path, payload: dict[str, Any]) -> None:
        (output_dir / "CORE5_SIGNAL_SANDBOX.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        with (output_dir / "simulated_order_receipts.csv").open("w", encoding="utf-8", newline="") as f:
            fieldnames = ["row", "symbol", "action", "quantity", "receipt_status", "broker_status", "order_id"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in payload["receipts"]:
                order = item.get("order") or {}
                receipt = item.get("receipt") or {}
                writer.writerow(
                    {
                        "row": item.get("row"),
                        "symbol": order.get("symbol"),
                        "action": order.get("action"),
                        "quantity": order.get("quantity"),
                        "receipt_status": receipt.get("status"),
                        "broker_status": receipt.get("broker_status", ""),
                        "order_id": receipt.get("order_id", ""),
                    }
                )

        lines = [
            "# Core5 Signal Sandbox",
            "",
            f"status: {payload['status']}",
            f"source_signal_status: {payload.get('source_signal_status')}",
            f"source_signal_mode: {payload.get('source_signal_mode') or 'LIVE_DRAFT'}",
            f"total_orders: {payload['total_orders']}",
            f"recorded_orders: {payload['recorded_orders']}",
            f"blocked_orders: {payload['blocked_orders']}",
            "",
            "## 模拟回执",
        ]
        for item in payload["receipts"]:
            order = item.get("order") or {}
            receipt = item.get("receipt") or {}
            lines.append(
                f"- row {item.get('row')}: {receipt.get('status')} {order.get('symbol')} {order.get('action')} {order.get('quantity')}"
            )
        lines.extend(["", "## 阻断项"])
        lines.extend([f"- {item}" for item in payload["warnings"]] or ["- 无，已记录模拟盘 dry-run 回执。"])
        lines.extend(
            [
                "",
                "## 硬边界",
                f"- {payload['hard_boundary']}",
                "- 即使传入 CONFIRM_REAL_TRADE，本命令也只做模拟盘记录。",
                "- 真实交易前必须重新经过 QMT 只读检查、pretrade-check、人工确认和独立安全门。",
            ]
        )
        (output_dir / "CORE5_SIGNAL_SANDBOX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
