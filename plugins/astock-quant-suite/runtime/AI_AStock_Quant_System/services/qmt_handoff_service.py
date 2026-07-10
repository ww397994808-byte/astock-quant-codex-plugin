from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from core.market_rules import MarketRules
from core.order import Order
from core.result import TaskResult
from core.run_manager import RunManager


class QMTHandoffService:
    """Build an auditable QMT order draft without sending any order."""

    def run(
        self,
        package: str,
        action: str,
        quantity: int,
        price: float | None = None,
        symbol: str | None = None,
        signal_time: str | None = None,
        execute_time: str | None = None,
        reason: str = "",
        timeframe: str = "1d",
    ) -> TaskResult:
        package_path = self._resolve_package_path(package)
        package_data = json.loads(package_path.read_text(encoding="utf-8"))
        selected_symbol = symbol or package_data.get("symbol") or self._symbol_from_selected_dsl(package_data.get("selected_dsl_path", ""))
        normalized_action = action.upper()
        signal_dt = self._parse_time(signal_time, "signal_time")
        execute_dt = self._parse_time(execute_time, "execute_time")
        order = Order(
            symbol=selected_symbol,
            action=normalized_action,
            quantity=int(quantity),
            price=price,
            signal_time=signal_dt,
            execute_time=execute_dt,
            reason=reason or "qmt_handoff_order_draft",
            timeframe=timeframe,
        )

        blockers = self._collect_blockers(package_data, order)
        status = "DRAFT_READY" if not blockers else "BLOCKED_DRAFT_ONLY"
        ctx = RunManager().create_run("qmt_handoff")
        payload = {
            "status": status,
            "package_path": str(package_path),
            "candidate_run_id": package_data.get("candidate_run_id", ""),
            "qmt_run_id": package_data.get("qmt_run_id", ""),
            "pretrade_status": package_data.get("pretrade_status", ""),
            "stage": package_data.get("stage", ""),
            "order": self._order_dict(order),
            "blockers": blockers,
            "hard_boundary": "本文件只生成 QMT 订单草案；pretrade-check VALID、人工确认和真实 QMT 下单适配完成前，不允许真实下单。",
        }
        self._write_outputs(ctx.output_dir, payload)
        result_status = "VALID" if status == "DRAFT_READY" else "INVALID"
        return TaskResult(
            status=result_status,
            message=f"QMT 订单交接草案生成完成：{status}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=result_status,
            warnings=blockers,
            artifacts=payload,
        )

    def _resolve_package_path(self, package: str) -> Path:
        path = Path(package)
        if path.is_dir():
            path = path / "PRETRADE_READINESS_PACKAGE.json"
        if path.name in {"PRETRADE_RUNBOOK.json", "PRETRADE_RUNBOOK_REFRESH.json"}:
            path = path.parent / "PRETRADE_READINESS_PACKAGE.json"
        if not path.exists():
            raise FileNotFoundError(f"找不到盘前证据包：{path}")
        return path

    def _symbol_from_selected_dsl(self, dsl_path: str) -> str:
        if not dsl_path:
            return ""
        path = Path(dsl_path)
        if not path.exists():
            return ""
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        symbols = data.get("symbols") or []
        return str(symbols[0]) if symbols else ""

    def _parse_time(self, value: str | None, field: str) -> datetime:
        if not value:
            raise ValueError(f"{field} 不能为空，必须显式给出信号时间和计划执行时间。")
        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{field} 必须使用 ISO 时间格式，例如 2026-06-29T09:35:00。") from exc

    def _collect_blockers(self, package: dict, order: Order) -> list[str]:
        blockers: list[str] = []
        if package.get("status") != "READY_FOR_PRETRADE_CHECK":
            blockers.append(f"盘前证据包未到 READY_FOR_PRETRADE_CHECK：{package.get('status')}")
        if package.get("stage") != "QMT_READONLY_READY":
            blockers.append(f"阶段未到 QMT_READONLY_READY：{package.get('stage')}")
        if package.get("pretrade_status") != "VALID":
            blockers.append(f"pretrade_status 不是 VALID：{package.get('pretrade_status')}")
        for item in package.get("fix_plan") or []:
            if item.get("status") == "blocked" or item.get("stop_trading") is True:
                blockers.append(f"停止推进事项未解除：{item.get('title')} - {item.get('failure')}")
        if not order.symbol:
            blockers.append("订单缺少 symbol。")
        if order.action not in {"BUY", "SELL"}:
            blockers.append("订单方向必须是 BUY 或 SELL。")
        lot = MarketRules().validate_lot(order.action, order.quantity)
        if not lot.ok:
            blockers.append(lot.reason)
        if order.execute_time <= order.signal_time:
            blockers.append("计划执行时间必须晚于信号时间，禁止同一根 K 线内信号即成交。")
        return blockers

    def _order_dict(self, order: Order) -> dict:
        data = asdict(order)
        data["signal_time"] = order.signal_time.isoformat()
        data["execute_time"] = order.execute_time.isoformat()
        return data

    def _write_outputs(self, output_dir: Path, payload: dict) -> None:
        (output_dir / "QMT_HANDOFF_PACKAGE.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        order = payload["order"]
        with (output_dir / "order_draft.csv").open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(order.keys()))
            writer.writeheader()
            writer.writerow(order)
        (output_dir / "order_draft.json").write_text(
            json.dumps(order, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        lines = [
            "# QMT Handoff Package",
            "",
            f"status: {payload['status']}",
            f"candidate_run_id: {payload.get('candidate_run_id') or 'MISSING'}",
            f"qmt_run_id: {payload.get('qmt_run_id') or 'MISSING'}",
            f"stage: {payload.get('stage') or 'MISSING'}",
            f"pretrade_status: {payload.get('pretrade_status') or 'MISSING'}",
            "",
            "## 订单草案",
            f"- symbol: {order['symbol']}",
            f"- action: {order['action']}",
            f"- quantity: {order['quantity']}",
            f"- price: {order.get('price') if order.get('price') is not None else 'MISSING'}",
            f"- signal_time: {order['signal_time']}",
            f"- execute_time: {order['execute_time']}",
            f"- timeframe: {order['timeframe']}",
            f"- reason: {order['reason']}",
            "",
            "## 阻断项",
        ]
        lines.extend([f"- {item}" for item in payload["blockers"]] or ["- 当前订单草案未发现阻断项。"])
        lines.extend([
            "",
            "## 硬边界",
            f"- {payload['hard_boundary']}",
            "- 这个包不调用 QMT broker，不发送委托，只作为人工复核和后续适配输入。",
            "- 若出现 blocked 或 pending 的盘前事项，不允许把本草案转成真实委托。",
        ])
        (output_dir / "QMT_HANDOFF_PACKAGE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
