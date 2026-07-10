from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.result import TaskResult
from core.run_manager import RunManager


class QMTOrderLifecycleService:
    """Track a sandboxed order draft against readonly QMT snapshots."""

    def run(self, sandbox: str, qmt_run_id: str | None = None) -> TaskResult:
        sandbox_path = self._resolve_sandbox_path(sandbox)
        sandbox_data = json.loads(sandbox_path.read_text(encoding="utf-8"))
        order = sandbox_data.get("order") or {}
        receipt = sandbox_data.get("receipt") or {}
        selected_qmt_run_id = (sandbox_data.get("qmt_run_id") or "") if qmt_run_id is None else qmt_run_id
        qmt_snapshot = self._load_qmt_snapshot(selected_qmt_run_id)

        warnings: list[str] = []
        if sandbox_data.get("status") != "DRY_RUN_RECORDED":
            warnings.append(f"沙盒未记录 dry-run 回执：{sandbox_data.get('status')}")
        if receipt.get("status") != "DRY_RUN_RECORDED":
            warnings.append(f"回执不是 DRY_RUN_RECORDED：{receipt.get('status')}")

        observed_order = self._find_match(order, qmt_snapshot.get("orders_today") or [])
        observed_trade = self._find_match(order, qmt_snapshot.get("trades_today") or [])
        if selected_qmt_run_id and not qmt_snapshot:
            warnings.append(f"找不到 QMT 只读快照：{selected_qmt_run_id}")
        if qmt_snapshot and not qmt_snapshot.get("ok"):
            warnings.append("QMT 只读快照不是 ok=true，只能作为异常线索，不能作为通过证据。")

        status = self._status_for(sandbox_data, receipt, observed_order, observed_trade, qmt_snapshot)
        timeline = self._timeline(sandbox_data, receipt, qmt_snapshot, observed_order, observed_trade)
        payload = {
            "status": status,
            "sandbox_path": str(sandbox_path),
            "candidate_run_id": sandbox_data.get("candidate_run_id", ""),
            "qmt_run_id": selected_qmt_run_id,
            "order": order,
            "receipt": receipt,
            "observed_order": observed_order,
            "observed_trade": observed_trade,
            "timeline": timeline,
            "warnings": warnings,
            "hard_boundary": "qmt-order-lifecycle 只做只读追踪；它不发送、撤销或修改任何 QMT 委托。",
        }
        ctx = RunManager().create_run("qmt_order_lifecycle")
        self._write_outputs(ctx.output_dir, payload)
        fatal = sandbox_data.get("status") != "DRY_RUN_RECORDED" or receipt.get("status") != "DRY_RUN_RECORDED"
        result_status = "VALID" if status in {"DRY_RUN_ONLY", "ORDER_OBSERVED", "TRADE_OBSERVED"} and not fatal else "INVALID"
        return TaskResult(
            status=result_status,
            message=f"QMT 订单生命周期追踪完成：{status}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=result_status,
            warnings=warnings,
            artifacts=payload,
        )

    def _resolve_sandbox_path(self, sandbox: str) -> Path:
        path = Path(sandbox)
        if path.is_dir():
            path = path / "QMT_ORDER_SANDBOX.json"
        if not path.exists():
            raise FileNotFoundError(f"找不到 QMT 沙盒报告：{path}")
        return path

    def _load_qmt_snapshot(self, qmt_run_id: str) -> dict:
        if not qmt_run_id:
            return {}
        path = Path("reports") / qmt_run_id / "qmt_account_snapshot.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _status_for(
        self,
        sandbox: dict,
        receipt: dict,
        observed_order: dict | None,
        observed_trade: dict | None,
        qmt_snapshot: dict,
    ) -> str:
        if sandbox.get("status") != "DRY_RUN_RECORDED" or receipt.get("status") != "DRY_RUN_RECORDED":
            return "BLOCKED_NO_TRACKING"
        if observed_trade:
            return "TRADE_OBSERVED"
        if observed_order:
            return "ORDER_OBSERVED"
        if qmt_snapshot:
            return "NOT_OBSERVED_IN_QMT"
        return "DRY_RUN_ONLY"

    def _timeline(
        self,
        sandbox: dict,
        receipt: dict,
        qmt_snapshot: dict,
        observed_order: dict | None,
        observed_trade: dict | None,
    ) -> list[dict]:
        items = [
            {"step": "sandbox", "status": sandbox.get("status", "MISSING")},
            {"step": "receipt", "status": receipt.get("status", "MISSING"), "order_id": receipt.get("order_id", "")},
        ]
        if qmt_snapshot:
            items.append({"step": "qmt_readonly_snapshot", "status": "OK" if qmt_snapshot.get("ok") else "INVALID"})
            items.append({"step": "order_observation", "status": "OBSERVED" if observed_order else "NOT_OBSERVED"})
            items.append({"step": "trade_observation", "status": "OBSERVED" if observed_trade else "NOT_OBSERVED"})
        else:
            items.append({"step": "qmt_readonly_snapshot", "status": "MISSING"})
        return items

    def _find_match(self, draft: dict, rows: list[dict[str, Any]]) -> dict | None:
        for row in rows:
            if self._same_order(draft, row):
                return row
        return None

    def _same_order(self, draft: dict, row: dict[str, Any]) -> bool:
        draft_symbol = str(draft.get("symbol") or "")
        row_symbol = self._first(row, ["symbol", "stock_code", "code", "instrument_id", "security"])
        if draft_symbol and row_symbol and draft_symbol != row_symbol:
            return False
        draft_action = self._normalize_action(draft.get("action"))
        row_action = self._normalize_action(self._first(row, ["action", "side", "direction", "order_type", "trade_type"]))
        if draft_action and row_action and draft_action != row_action:
            return False
        draft_qty = int(float(draft.get("quantity") or 0))
        row_qty_value = self._first(row, ["quantity", "volume", "order_volume", "traded_volume", "filled_volume"])
        if row_qty_value not in {"", None}:
            try:
                row_qty = int(float(row_qty_value))
            except (TypeError, ValueError):
                row_qty = 0
            if draft_qty and row_qty and draft_qty != row_qty:
                return False
        return bool(draft_symbol or row_symbol)

    def _first(self, data: dict, keys: list[str]) -> Any:
        for key in keys:
            if key in data and data[key] not in {"", None}:
                return data[key]
        return ""

    def _normalize_action(self, value: Any) -> str:
        raw = str(value or "").upper()
        if raw in {"BUY", "B", "买", "买入", "XT_BUY"}:
            return "BUY"
        if raw in {"SELL", "S", "卖", "卖出", "XT_SELL"}:
            return "SELL"
        return raw

    def _write_outputs(self, output_dir: Path, payload: dict) -> None:
        (output_dir / "QMT_ORDER_LIFECYCLE.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        (output_dir / "lifecycle_timeline.json").write_text(
            json.dumps(payload["timeline"], ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        lines = [
            "# QMT Order Lifecycle",
            "",
            f"status: {payload['status']}",
            f"candidate_run_id: {payload.get('candidate_run_id') or 'MISSING'}",
            f"qmt_run_id: {payload.get('qmt_run_id') or 'MISSING'}",
            "",
            "## 生命周期",
        ]
        for item in payload["timeline"]:
            detail = f" order_id={item.get('order_id')}" if item.get("order_id") else ""
            lines.append(f"- {item['step']}: {item['status']}{detail}")
        lines.extend(["", "## 观察结果"])
        lines.append(f"- observed_order: {'YES' if payload.get('observed_order') else 'NO'}")
        lines.append(f"- observed_trade: {'YES' if payload.get('observed_trade') else 'NO'}")
        lines.extend(["", "## 警告"])
        lines.extend([f"- {item}" for item in payload["warnings"]] or ["- 当前生命周期追踪未发现新的警告。"])
        lines.extend([
            "",
            "## 硬边界",
            f"- {payload['hard_boundary']}",
            "- 只读快照只能证明观察到委托/成交信息，不能证明策略可盈利，也不能替代人工复核。",
        ])
        (output_dir / "QMT_ORDER_LIFECYCLE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
