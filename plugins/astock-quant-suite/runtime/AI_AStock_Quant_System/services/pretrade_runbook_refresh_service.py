from __future__ import annotations

import json
from pathlib import Path

from core.result import TaskResult
from core.run_manager import RunManager
from services.pretrade_package_service import PretradePackageService
from services.pretrade_service import PreTradeService
from services.stage_check_service import StageCheckService


class PretradeRunbookRefreshService:
    """Re-check a pretrade package without rebuilding the whole evidence package."""

    def run(
        self,
        package: str,
        qmt_run_id: str | None = None,
        confirmation: str = "",
        strategy: str | None = None,
        symbol: str | None = None,
    ) -> TaskResult:
        package_path = self._resolve_package_path(package)
        previous = json.loads(package_path.read_text(encoding="utf-8"))
        helper = PretradePackageService()

        candidate_run_id = previous.get("candidate_run_id") or helper._run_id_from_report_path(
            str(previous.get("source_report_path") or "")
        )
        selected_symbol = symbol or previous.get("symbol") or helper._symbol_from_selected_dsl(
            previous.get("selected_dsl_path", "")
        )
        selected_strategy = strategy or previous.get("strategy") or "compiled_repair_dsl"
        selected_qmt_run_id = qmt_run_id or previous.get("qmt_run_id") or None

        stage_result = StageCheckService().run(run_id=candidate_run_id, qmt_run_id=selected_qmt_run_id)
        stage = stage_result.artifacts.get("stage_gate", {}).get("stage", "INVALID")
        pretrade = PreTradeService().run(
            strategy=selected_strategy,
            symbol=selected_symbol,
            confirmation=confirmation,
            run_id=candidate_run_id,
            qmt_run_id=selected_qmt_run_id,
        )

        current_fix_plan = helper._build_fix_plan(stage_result.warnings, pretrade.warnings)
        refresh_items = self._merge_with_previous(previous.get("fix_plan") or [], current_fix_plan)
        refresh = {
            "status": "READY_FOR_PRETRADE_CHECK" if stage == "QMT_READONLY_READY" else "BLOCKED_BEFORE_PRETRADE",
            "previous_package_path": str(package_path),
            "candidate_run_id": candidate_run_id,
            "strategy": selected_strategy,
            "symbol": selected_symbol,
            "qmt_run_id": selected_qmt_run_id or stage_result.artifacts.get("qmt_run_id", ""),
            "stage": stage,
            "stage_reasons": stage_result.warnings,
            "pretrade_status": pretrade.status,
            "pretrade_failures": pretrade.warnings,
            "runbook_items": refresh_items,
            "summary": helper._runbook_summary(refresh_items),
            "hard_boundary": previous.get("hard_boundary", "pretrade-check VALID 且人工确认前，不允许真实下单。"),
        }

        ctx = RunManager().create_run("pretrade_runbook_refresh")
        (ctx.output_dir / "PRETRADE_RUNBOOK_REFRESH.json").write_text(
            json.dumps(refresh, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self._write_report(ctx.output_dir, refresh, helper)
        status = "VALID" if refresh["status"] == "READY_FOR_PRETRADE_CHECK" else "INVALID"
        return TaskResult(
            status=status,
            message=f"盘前清单复查完成：{refresh['status']}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=status,
            warnings=stage_result.warnings + pretrade.warnings,
            artifacts=refresh,
        )

    def _resolve_package_path(self, package: str) -> Path:
        path = Path(package)
        if path.is_dir():
            path = path / "PRETRADE_READINESS_PACKAGE.json"
        if path.name == "PRETRADE_RUNBOOK.json":
            path = path.parent / "PRETRADE_READINESS_PACKAGE.json"
        if not path.exists():
            raise FileNotFoundError(f"找不到盘前证据包：{path}")
        return path

    def _merge_with_previous(self, previous_items: list[dict], current_items: list[dict]) -> list[dict]:
        current_by_key = {self._item_key(item): dict(item, source="current") for item in current_items}
        merged = list(current_by_key.values())
        for old in previous_items:
            key = self._item_key(old)
            if key in current_by_key:
                continue
            verified = dict(old)
            verified["status"] = "verified"
            verified["source"] = "previous_resolved"
            verified["can_auto_fix"] = False
            verified["action"] = "本次复查未再出现该阻断项，保留为已解除记录。"
            verified["verification"] = "该阻断项已从最新 stage/pretrade 检查结果中消失。"
            merged.append(verified)
        return self._sort_items(merged)

    def _item_key(self, item: dict) -> tuple[str, str]:
        title = item.get("title") or ""
        if title and title != "未分类阻断项":
            return (str(item.get("category") or ""), str(title))
        return (str(item.get("category") or ""), str(item.get("failure") or ""))

    def _sort_items(self, items: list[dict]) -> list[dict]:
        order = {"blocked": 0, "pending": 1, "verified": 2}
        severity = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        return sorted(
            items,
            key=lambda item: (
                order.get(str(item.get("status")), 9),
                severity.get(str(item.get("severity")), 9),
                str(item.get("category") or ""),
                str(item.get("title") or ""),
            ),
        )

    def _write_report(self, output_dir: Path, refresh: dict, helper: PretradePackageService) -> None:
        lines = [
            "# Pretrade Runbook Refresh",
            "",
            f"status: {refresh['status']}",
            f"candidate_run_id: {refresh['candidate_run_id']}",
            f"qmt_run_id: {refresh.get('qmt_run_id') or 'MISSING'}",
            f"stage: {refresh.get('stage')}",
            f"pretrade_status: {refresh.get('pretrade_status')}",
            f"verified: {refresh['summary'].get('verified', 0)}",
            f"pending: {refresh['summary'].get('pending', 0)}",
            f"blocked: {refresh['summary'].get('blocked', 0)}",
            "",
            "## 硬边界",
            f"- {refresh['hard_boundary']}",
            "- verified 只表示该阻断项本次未再出现，不代表允许真实下单。",
            "",
            "## 本次仍存在的阻断项",
        ]
        current_blockers = [item for item in refresh["runbook_items"] if item.get("status") != "verified"]
        lines.extend([f"- [{item['status']}] {item['title']}：{item['failure']}" for item in current_blockers] or ["- 当前复查未发现仍存在的阻断项。"])
        lines.extend(["", "## 本次已解除"])
        verified = [item for item in refresh["runbook_items"] if item.get("status") == "verified"]
        lines.extend([f"- {item['title']}：{item['failure']}" for item in verified] or ["- 暂无从旧清单解除的事项。"])
        lines.extend(["", "## 分组清单", ""])
        for section in helper._runbook_sections(refresh["runbook_items"]):
            lines.extend([f"### {section['title']}", ""])
            for item in section["items"]:
                lines.extend([
                    f"- title: {item['title']}",
                    f"  status: {item['status']}",
                    f"  failure: {item['failure']}",
                    f"  action: {item['action']}",
                    f"  verification: {item['verification']}",
                ])
                if item.get("command"):
                    lines.append(f"  command: `{item['command']}`")
                lines.append("")
        (output_dir / "PRETRADE_RUNBOOK_REFRESH.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
