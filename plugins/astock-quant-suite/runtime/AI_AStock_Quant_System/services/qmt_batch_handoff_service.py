from __future__ import annotations

import csv
import json
from pathlib import Path

from core.order import Order
from core.result import TaskResult
from core.run_manager import RunManager
from services.qmt_handoff_service import QMTHandoffService


class QMTBatchHandoffService:
    """Build an auditable batch of QMT order drafts without sending orders."""

    def run(self, package: str, orders: str, default_timeframe: str = "1d") -> TaskResult:
        helper = QMTHandoffService()
        package_path = helper._resolve_package_path(package)
        package_data = json.loads(package_path.read_text(encoding="utf-8"))
        rows = self._read_orders(Path(orders))
        drafts = []
        all_blockers: list[str] = []
        for index, row in enumerate(rows, start=1):
            order = self._order_from_row(helper, row, default_timeframe)
            blockers = helper._collect_blockers(package_data, order)
            order_dict = helper._order_dict(order)
            draft_status = "DRAFT_READY" if not blockers else "BLOCKED_DRAFT_ONLY"
            draft = {
                "row": index,
                "status": draft_status,
                "order": order_dict,
                "blockers": blockers,
            }
            drafts.append(draft)
            all_blockers.extend([f"row {index}: {item}" for item in blockers])

        status = "BATCH_DRAFT_READY" if not all_blockers else "BATCH_BLOCKED_DRAFT_ONLY"
        ctx = RunManager().create_run("qmt_batch_handoff")
        payload = {
            "status": status,
            "package_path": str(package_path),
            "orders_path": str(Path(orders)),
            "candidate_run_id": package_data.get("candidate_run_id", ""),
            "qmt_run_id": package_data.get("qmt_run_id", ""),
            "pretrade_status": package_data.get("pretrade_status", ""),
            "stage": package_data.get("stage", ""),
            "total_orders": len(drafts),
            "ready_orders": sum(1 for item in drafts if item["status"] == "DRAFT_READY"),
            "blocked_orders": sum(1 for item in drafts if item["status"] != "DRAFT_READY"),
            "drafts": drafts,
            "blockers": all_blockers,
            "hard_boundary": "本文件只生成批量 QMT 订单草案；不调用 QMT broker，不发送委托。",
        }
        self._write_outputs(ctx.output_dir, payload)
        result_status = "VALID" if status == "BATCH_DRAFT_READY" else "INVALID"
        return TaskResult(
            status=result_status,
            message=f"批量 QMT 订单交接草案生成完成：{status}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=result_status,
            warnings=all_blockers,
            artifacts=payload,
        )

    def _read_orders(self, path: Path) -> list[dict]:
        if not path.exists():
            raise FileNotFoundError(f"找不到批量订单 CSV：{path}")
        with path.open("r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            raise ValueError("批量订单 CSV 不能为空。")
        return rows

    def _order_from_row(self, helper: QMTHandoffService, row: dict, default_timeframe: str) -> Order:
        return Order(
            symbol=str(row.get("symbol") or ""),
            action=str(row.get("action") or "").upper(),
            quantity=int(float(row.get("quantity") or 0)),
            price=float(row["price"]) if row.get("price") not in {"", None} else None,
            signal_time=helper._parse_time(row.get("signal_time"), "signal_time"),
            execute_time=helper._parse_time(row.get("execute_time"), "execute_time"),
            reason=str(row.get("reason") or "qmt_batch_handoff_order_draft"),
            timeframe=str(row.get("timeframe") or default_timeframe),
        )

    def _write_outputs(self, output_dir: Path, payload: dict) -> None:
        (output_dir / "QMT_BATCH_HANDOFF_PACKAGE.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        fieldnames = [
            "row",
            "status",
            "symbol",
            "action",
            "quantity",
            "price",
            "signal_time",
            "execute_time",
            "timeframe",
            "reason",
            "blockers",
        ]
        with (output_dir / "batch_order_drafts.csv").open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for draft in payload["drafts"]:
                order = draft["order"]
                writer.writerow({
                    "row": draft["row"],
                    "status": draft["status"],
                    "symbol": order.get("symbol", ""),
                    "action": order.get("action", ""),
                    "quantity": order.get("quantity", ""),
                    "price": order.get("price", ""),
                    "signal_time": order.get("signal_time", ""),
                    "execute_time": order.get("execute_time", ""),
                    "timeframe": order.get("timeframe", ""),
                    "reason": order.get("reason", ""),
                    "blockers": " | ".join(draft.get("blockers") or []),
                })
        lines = [
            "# QMT Batch Handoff Package",
            "",
            f"status: {payload['status']}",
            f"total_orders: {payload['total_orders']}",
            f"ready_orders: {payload['ready_orders']}",
            f"blocked_orders: {payload['blocked_orders']}",
            f"candidate_run_id: {payload.get('candidate_run_id') or 'MISSING'}",
            f"qmt_run_id: {payload.get('qmt_run_id') or 'MISSING'}",
            "",
            "## 批量订单",
        ]
        for draft in payload["drafts"]:
            order = draft["order"]
            lines.append(
                f"- row {draft['row']}: {draft['status']} {order.get('symbol')} {order.get('action')} {order.get('quantity')}"
            )
        lines.extend(["", "## 阻断项"])
        lines.extend([f"- {item}" for item in payload["blockers"]] or ["- 当前批量订单草案未发现阻断项。"])
        lines.extend([
            "",
            "## 硬边界",
            f"- {payload['hard_boundary']}",
            "- 任意一笔订单阻断时，整批都不能转入 QMT 沙盒或真实委托。",
            "- 批量草案仍需后续逐笔沙盒、生命周期追踪和日终复盘。",
        ])
        (output_dir / "QMT_BATCH_HANDOFF_PACKAGE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
