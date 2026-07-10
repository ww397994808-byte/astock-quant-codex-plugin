from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.result import TaskResult
from core.run_manager import RunManager


class QMTReadinessDashboardService:
    """Build one conservative dashboard from the latest QMT handoff evidence."""

    SOURCES = {
        "pretrade_package": ("pretrade_package", "PRETRADE_READINESS_PACKAGE.json"),
        "runbook_refresh": ("pretrade_runbook_refresh", "PRETRADE_RUNBOOK_REFRESH.json"),
        "handoff_wizard": ("qmt_handoff_wizard", "QMT_HANDOFF_WIZARD.json"),
        "batch_handoff_wizard": ("qmt_batch_handoff_wizard", "QMT_BATCH_HANDOFF_WIZARD.json"),
        "daily_review": ("qmt_daily_review", "QMT_DAILY_REVIEW.json"),
        "batch_daily_review": ("qmt_batch_daily_review", "QMT_BATCH_DAILY_REVIEW.json"),
    }

    VALID_REVIEW_STATUSES = {
        "DRY_RUN_REVIEW",
        "BATCH_DRY_RUN_REVIEW",
        "REVIEW_READY",
        "BATCH_REVIEW_READY",
    }

    BLOCKED_MARKERS = ("BLOCKED", "STOP", "INVALID")
    BLOCKER_PRIORITY = {
        "pretrade_package": 0,
        "runbook_refresh": 1,
        "handoff_wizard": 2,
        "batch_handoff_wizard": 2,
        "daily_review": 3,
        "batch_daily_review": 3,
    }

    def run(
        self,
        pretrade_package: str | None = None,
        runbook_refresh: str | None = None,
        handoff_wizard: str | None = None,
        batch_handoff_wizard: str | None = None,
        daily_review: str | None = None,
        batch_daily_review: str | None = None,
    ) -> TaskResult:
        provided = {
            "pretrade_package": pretrade_package,
            "runbook_refresh": runbook_refresh,
            "handoff_wizard": handoff_wizard,
            "batch_handoff_wizard": batch_handoff_wizard,
            "daily_review": daily_review,
            "batch_daily_review": batch_daily_review,
        }
        evidence = [self._load_source(name, provided.get(name)) for name in self.SOURCES]
        found = [item for item in evidence if item["found"]]
        decision = self._decide(evidence)
        blocker_checklist = self._build_blocker_checklist(evidence)
        action_cards = self._build_action_cards(decision, evidence, blocker_checklist)
        warnings = self._warnings_for(evidence, decision)

        ctx = RunManager().create_run("qmt_readiness_dashboard")
        payload = {
            "status": decision["status"],
            "risk_level": decision["risk_level"],
            "summary": decision["summary"],
            "next_action": decision["next_action"],
            "next_command": decision["next_command"],
            "current_stage": decision["current_stage"],
            "learner_mode": self._learner_mode(decision),
            "action_cards": action_cards,
            "blocker_checklist": blocker_checklist,
            "evidence_found": len(found),
            "evidence": evidence,
            "warnings": warnings,
            "hard_boundary": "QMT readiness dashboard 只汇总证据和下一步；它不是实盘许可，也不会连接或调用真实 QMT 下单。",
        }
        self._write_outputs(ctx.output_dir, payload)
        result_status = "VALID" if payload["status"] in {"DRY_RUN_ONLY", "REVIEW_READY"} else "INVALID"
        return TaskResult(
            status=result_status,
            message=f"QMT 准备度总览生成完成：{payload['status']}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=result_status,
            warnings=warnings,
            artifacts=payload,
        )

    def _load_source(self, name: str, provided_path: str | None) -> dict[str, Any]:
        prefix, filename = self.SOURCES[name]
        path = self._resolve_path(provided_path, prefix, filename)
        if not path:
            return {
                "name": name,
                "found": False,
                "path": "",
                "status": "MISSING",
                "summary": "未找到该类报告。",
            }
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return {
                "name": name,
                "found": True,
                "path": str(path),
                "status": "UNREADABLE",
                "summary": f"JSON 解析失败：{exc}",
                "data": {},
            }
        status = str(data.get("status") or data.get("pretrade_status") or "UNKNOWN")
        return {
            "name": name,
            "found": True,
            "path": str(path),
            "run_dir": str(path.parent),
            "status": status,
            "summary": self._source_summary(name, data, status),
            "candidate_run_id": data.get("candidate_run_id", ""),
            "qmt_run_id": data.get("qmt_run_id", ""),
            "next_day_gate": data.get("next_day_gate", ""),
            "warnings": list(data.get("warnings") or data.get("anomalies") or []),
            "data": data,
        }

    def _resolve_path(self, provided_path: str | None, prefix: str, filename: str) -> Path | None:
        if provided_path:
            path = Path(provided_path)
            if path.is_dir():
                path = path / filename
            return path if path.exists() else None
        reports = Path("reports")
        candidates = sorted(reports.glob(f"{prefix}_*/{filename}"))
        return candidates[-1] if candidates else None

    def _decide(self, evidence: list[dict[str, Any]]) -> dict[str, str]:
        found = [item for item in evidence if item["found"]]
        if not found:
            return {
                "status": "NO_EVIDENCE",
                "risk_level": "HIGH",
                "current_stage": "NO_QMT_EVIDENCE",
                "summary": "还没有找到 QMT 交接链路证据，不能判断是否可以推进。",
                "next_action": "先生成盘前证据包，再进入 QMT 只读和交接流程。",
                "next_command": "python3 cli.py pretrade-package --promotion <REPAIR_DSL_PROMOTION.json> --qmt-run-id <qmt_run_id>",
            }

        blocked = [item for item in found if self._is_blocked(item["status"])]
        if blocked:
            blocker = sorted(blocked, key=lambda item: self.BLOCKER_PRIORITY.get(item["name"], 99))[0]
            return {
                "status": "BLOCKED",
                "risk_level": "HIGH",
                "current_stage": f"BLOCKED_AT_{blocker['name'].upper()}",
                "summary": f"最新证据中存在阻断：{blocker['name']} = {blocker['status']}。",
                "next_action": self._blocked_next_action(blocker),
                "next_command": self._blocked_next_command(blocker),
            }

        pretrade = self._by_name(evidence, "pretrade_package")
        if pretrade and pretrade["status"] == "READY_FOR_PRETRADE_CHECK":
            review = self._latest_review(evidence)
            if not review:
                return {
                    "status": "READY_FOR_DRY_RUN",
                    "risk_level": "MEDIUM",
                    "current_stage": "PRETRADE_READY_NEEDS_HANDOFF_WIZARD",
                    "summary": "盘前证据包已到可检查状态，但还没有看到交接向导或日终复盘证据。",
                    "next_action": "根据单笔或批量场景运行 QMT 交接向导，先完成 dry-run 沙盒链路。",
                    "next_command": "python3 cli.py qmt-handoff-wizard --package <pretrade_package_dir> --action BUY --quantity 100 --signal-time <ISO> --execute-time <ISO> --trade-date <YYYY-MM-DD>",
                }

        review = self._latest_review(evidence)
        if review and review["status"] in {"DRY_RUN_REVIEW", "BATCH_DRY_RUN_REVIEW"}:
            return {
                "status": "DRY_RUN_ONLY",
                "risk_level": "LOW",
                "current_stage": "SANDBOX_REVIEW_ONLY",
                "summary": "最近复盘只支持继续 dry-run 沙盒演练，不支持实盘。",
                "next_action": "下一日继续 dry-run；重新从 QMT 只读、盘前检查和人工确认边界开始。",
                "next_command": "python3 cli.py qmt-readiness-dashboard",
            }
        if review and review["status"] in {"REVIEW_READY", "BATCH_REVIEW_READY"}:
            return {
                "status": "REVIEW_READY",
                "risk_level": "MEDIUM",
                "current_stage": "MANUAL_REVIEW_REQUIRED",
                "summary": "最近复盘可进入人工复核，但这仍不是实盘许可。",
                "next_action": "人工复核持仓、成交、现金、风险敞口和下一日退出条件；再重新跑盘前检查。",
                "next_command": "python3 cli.py pretrade-runbook-refresh --package <pretrade_package_dir> --qmt-run-id <qmt_run_id>",
            }

        return {
            "status": "EVIDENCE_INCOMPLETE",
            "risk_level": "MEDIUM",
            "current_stage": "QMT_EVIDENCE_INCOMPLETE",
            "summary": "已找到部分证据，但链路还没有形成可复盘状态。",
            "next_action": "补齐盘前包、QMT 交接向导、沙盒、生命周期和日终复盘中的缺口。",
            "next_command": "python3 cli.py qmt-readiness-dashboard",
        }

    def _is_blocked(self, status: str) -> bool:
        upper = status.upper()
        return any(marker in upper for marker in self.BLOCKED_MARKERS) or upper in {"NO_EVIDENCE", "UNREADABLE"}

    def _by_name(self, evidence: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
        for item in evidence:
            if item["name"] == name and item["found"]:
                return item
        return None

    def _latest_review(self, evidence: list[dict[str, Any]]) -> dict[str, Any] | None:
        reviews = [item for item in evidence if item["name"] in {"daily_review", "batch_daily_review"} and item["found"]]
        return reviews[-1] if reviews else None

    def _blocked_next_action(self, blocker: dict[str, Any]) -> str:
        name = blocker["name"]
        if name == "pretrade_package":
            return "打开 PRETRADE_READINESS_PACKAGE.md 和 PRETRADE_RUNBOOK.md，先修复盘前阻断。"
        if name == "runbook_refresh":
            return "继续按 runbook 的 blocked/pending 项修复；不要进入交接或实盘。"
        if "wizard" in name:
            return "打开对应 QMT 向导报告，停在第一个失败步骤处修复。"
        if "daily_review" in name:
            return "按日终复盘的 next_day_gate 处理；阻断未关闭前下一日不推进。"
        return "先修复阻断报告中列出的风险项。"

    def _blocked_next_command(self, blocker: dict[str, Any]) -> str:
        path = blocker.get("run_dir") or blocker.get("path") or "<report_dir>"
        name = blocker["name"]
        if name == "pretrade_package":
            return f"python3 cli.py pretrade-runbook-refresh --package {path} --qmt-run-id <qmt_run_id>"
        if "daily_review" in name:
            return "python3 cli.py qmt-check"
        return f"打开报告目录：{path}"

    def _source_summary(self, name: str, data: dict[str, Any], status: str) -> str:
        if name == "pretrade_package":
            return f"stage={data.get('stage', 'UNKNOWN')}, pretrade_status={data.get('pretrade_status', 'UNKNOWN')}, status={status}"
        if name == "runbook_refresh":
            summary = data.get("summary") or {}
            if isinstance(summary, dict):
                return f"verified={summary.get('verified', 0)}, pending={summary.get('pending', 0)}, blocked={summary.get('blocked', 0)}"
        if "wizard" in name:
            steps = data.get("steps") or []
            return f"status={status}, steps={len(steps)}"
        if "daily_review" in name:
            return f"status={status}, next_day_gate={data.get('next_day_gate', 'UNKNOWN')}"
        return f"status={status}"

    def _warnings_for(self, evidence: list[dict[str, Any]], decision: dict[str, str]) -> list[str]:
        warnings = []
        for item in evidence:
            if item["found"] and self._is_blocked(item["status"]):
                warnings.append(f"{item['name']} 阻断：{item['status']}。")
            if item["found"] and item.get("warnings"):
                warnings.extend([f"{item['name']}: {warning}" for warning in item["warnings"]])
        if decision["status"] not in {"DRY_RUN_ONLY", "REVIEW_READY"}:
            warnings.append(decision["summary"])
        return warnings

    def _learner_mode(self, decision: dict[str, str]) -> dict[str, Any]:
        status = decision["status"]
        return {
            "can_continue_research": True,
            "can_continue_qmt_dry_run": status in {"READY_FOR_DRY_RUN", "DRY_RUN_ONLY", "REVIEW_READY"},
            "live_trade_allowed": False,
            "human_review_required": status in {"BLOCKED", "REVIEW_READY", "EVIDENCE_INCOMPLETE"},
            "plain_language": self._plain_language_for(status),
        }

    def _plain_language_for(self, status: str) -> str:
        if status == "NO_EVIDENCE":
            return "还没到 QMT 交接阶段，先把研究证据和盘前包补出来。"
        if status == "BLOCKED":
            return "现在有硬阻断，先修最上游阻断，不要继续交接或实盘。"
        if status == "READY_FOR_DRY_RUN":
            return "可以准备 dry-run 沙盒演练，但还不能实盘。"
        if status == "DRY_RUN_ONLY":
            return "今天只允许继续 dry-run，不能实盘。"
        if status == "REVIEW_READY":
            return "可以进入人工复核，但复核通过前仍不能实盘。"
        return "证据不完整，先补齐报告链路。"

    def _build_action_cards(
        self,
        decision: dict[str, str],
        evidence: list[dict[str, Any]],
        blocker_checklist: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        primary_command = decision["next_command"]
        cards = [
            {
                "id": "primary_next_step",
                "title": "下一步",
                "status": "blocked" if decision["status"] in {"NO_EVIDENCE", "BLOCKED", "EVIDENCE_INCOMPLETE"} else "pending",
                "audience": "learner",
                "action": decision["next_action"],
                "command": primary_command,
                "safe_to_copy": self._is_concrete_command(primary_command),
                "requires_manual_input": not self._is_concrete_command(primary_command),
                "why": decision["summary"],
            }
        ]

        pretrade = self._by_name(evidence, "pretrade_package")
        if pretrade and pretrade["found"]:
            cards.append({
                "id": "open_pretrade_package",
                "title": "打开盘前证据包",
                "status": "pending" if self._is_blocked(pretrade["status"]) else "done",
                "audience": "learner",
                "action": "先看盘前证据包的修复清单，再决定是否复查 Runbook。",
                "command": f"打开报告目录：{pretrade.get('run_dir')}",
                "safe_to_copy": False,
                "requires_manual_input": True,
                "why": pretrade["summary"],
            })

        unresolved = [item for item in blocker_checklist if item.get("status") != "verified"]
        if unresolved:
            first = unresolved[0]
            cards.append({
                "id": "first_unresolved_blocker",
                "title": "先修第一个阻断",
                "status": "blocked",
                "audience": "operator",
                "action": first.get("action") or first.get("reason") or "先处理该阻断项。",
                "command": first.get("command") or "无可直接执行命令，需要人工处理。",
                "safe_to_copy": self._is_concrete_command(first.get("command") or ""),
                "requires_manual_input": not self._is_concrete_command(first.get("command") or ""),
                "why": first.get("reason") or first.get("title") or "存在未解除阻断。",
            })
        cards.append({
            "id": "hard_boundary",
            "title": "硬边界",
            "status": "always_on",
            "audience": "mentor",
            "action": "不要把 dashboard、dry-run、QMT 只读或成交观察解释成实盘许可。",
            "command": "",
            "safe_to_copy": False,
            "requires_manual_input": True,
            "why": "实盘必须另有 pretrade-check、Runbook 复查和人工确认。",
        })
        return cards

    def _build_blocker_checklist(self, evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for source in evidence:
            if not source["found"]:
                continue
            status = source["status"]
            if self._is_blocked(status):
                items.append({
                    "source": source["name"],
                    "title": f"{source['name']} 阻断",
                    "status": "blocked",
                    "severity": "HIGH",
                    "reason": status,
                    "action": self._blocked_next_action(source),
                    "command": self._blocked_next_command(source),
                    "report_path": source.get("path", ""),
                })
            data = source.get("data") or {}
            if source["name"] == "pretrade_package":
                items.extend(self._runbook_items_from(source, data.get("fix_plan") or []))
            if source["name"] == "runbook_refresh":
                items.extend(self._runbook_items_from(source, data.get("runbook_items") or []))
            if "wizard" in source["name"]:
                items.extend(self._wizard_items_from(source, data.get("steps") or []))
        return self._sort_blockers(items)

    def _runbook_items_from(self, source: dict[str, Any], items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        for item in items:
            result.append({
                "source": source["name"],
                "title": item.get("title") or item.get("failure") or "未命名阻断",
                "status": item.get("status") or "pending",
                "severity": item.get("severity") or "MEDIUM",
                "category": item.get("category") or "",
                "reason": item.get("failure") or "",
                "action": item.get("action") or "",
                "command": item.get("command") or "",
                "verification": item.get("verification") or "",
                "stop_trading": bool(item.get("stop_trading")),
                "report_path": source.get("path", ""),
            })
        return result

    def _wizard_items_from(self, source: dict[str, Any], steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        for step in steps:
            if str(step.get("status")) == "VALID":
                continue
            warnings = step.get("warnings") or []
            result.append({
                "source": source["name"],
                "title": f"{step.get('name', 'wizard_step')} 未通过",
                "status": "blocked",
                "severity": "HIGH",
                "reason": "；".join(str(item) for item in warnings) or str(step.get("artifacts_status") or "INVALID"),
                "action": "停在该步骤，先修复上游证据或安全配置。",
                "command": f"打开报告目录：{step.get('report_path') or source.get('run_dir')}",
                "verification": "重新运行对应 QMT 向导，直到该步骤不再阻断。",
                "stop_trading": True,
                "report_path": step.get("report_path") or source.get("path", ""),
            })
        return result

    def _sort_blockers(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        status_order = {"blocked": 0, "pending": 1, "verified": 2}
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        return sorted(
            items,
            key=lambda item: (
                self.BLOCKER_PRIORITY.get(str(item.get("source")), 99),
                status_order.get(str(item.get("status")), 9),
                severity_order.get(str(item.get("severity")), 9),
                str(item.get("title") or ""),
            ),
        )

    def _is_concrete_command(self, command: str) -> bool:
        if not command:
            return False
        return command.startswith("python3 ") and "<" not in command and ">" not in command

    def _write_outputs(self, output_dir: Path, payload: dict[str, Any]) -> None:
        (output_dir / "QMT_READINESS_DASHBOARD.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        (output_dir / "qmt_action_cards.json").write_text(
            json.dumps(payload["action_cards"], ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        (output_dir / "qmt_blocker_checklist.json").write_text(
            json.dumps(payload["blocker_checklist"], ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        self._write_next_actions(output_dir, payload)
        lines = [
            "# QMT Readiness Dashboard",
            "",
            f"status: {payload['status']}",
            f"risk_level: {payload['risk_level']}",
            f"current_stage: {payload['current_stage']}",
            f"evidence_found: {payload['evidence_found']}",
            "",
            "## 当前结论",
            f"- {payload['summary']}",
            f"- {payload['learner_mode']['plain_language']}",
            "",
            "## 下一步",
            f"- action: {payload['next_action']}",
            f"- command: `{payload['next_command']}`",
            "",
            "## 行动卡",
        ]
        for card in payload["action_cards"]:
            lines.extend([
                f"### {card['title']}",
                f"- status: {card['status']}",
                f"- audience: {card['audience']}",
                f"- action: {card['action']}",
                f"- command: `{card['command']}`" if card.get("command") else "- command: MISSING",
                f"- safe_to_copy: {card['safe_to_copy']}",
                f"- requires_manual_input: {card['requires_manual_input']}",
                "",
            ])
        lines.extend([
            "",
            "## 证据清单",
        ])
        for item in payload["evidence"]:
            lines.extend([
                f"### {item['name']}",
                f"- found: {'YES' if item['found'] else 'NO'}",
                f"- status: {item['status']}",
                f"- path: {item.get('path') or 'MISSING'}",
                f"- summary: {item['summary']}",
                "",
            ])
        lines.extend(["## 警告"])
        lines.extend([f"- {warning}" for warning in payload["warnings"]] or ["- 当前总览未发现新的警告。"])
        lines.extend([
            "",
            "## 硬边界",
            f"- {payload['hard_boundary']}",
            "- dry-run、观察到委托、观察到成交，都不是自动实盘许可。",
        ])
        (output_dir / "QMT_READINESS_DASHBOARD.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_next_actions(self, output_dir: Path, payload: dict[str, Any]) -> None:
        lines = [
            "# QMT Next Actions",
            "",
            f"status: {payload['status']}",
            f"current_stage: {payload['current_stage']}",
            f"risk_level: {payload['risk_level']}",
            "",
            "## 给学员的结论",
            f"- {payload['learner_mode']['plain_language']}",
            f"- {payload['summary']}",
            "",
            "## 现在做什么",
            f"- {payload['next_action']}",
            f"- `{payload['next_command']}`",
            "",
            "## 先处理的阻断",
        ]
        unresolved = [item for item in payload["blocker_checklist"] if item.get("status") != "verified"]
        for item in unresolved[:10]:
            lines.extend([
                f"### {item.get('title')}",
                f"- source: {item.get('source')}",
                f"- status: {item.get('status')}",
                f"- severity: {item.get('severity')}",
                f"- reason: {item.get('reason')}",
                f"- action: {item.get('action')}",
            ])
            if item.get("command"):
                lines.append(f"- command: `{item['command']}`")
            if item.get("verification"):
                lines.append(f"- verification: {item['verification']}")
            lines.append("")
        if not unresolved:
            lines.append("- 当前没有未解除阻断；仍需人工复核，不能自动实盘。")
        lines.extend([
            "",
            "## 老师提示",
            "- 先讲最上游阻断，不要从下游报错开始讲。",
            "- 有占位符的命令不能直接复制执行，必须补齐 run id、日期、标的或订单参数。",
            "- 任何 dry-run 或 QMT 只读证据，都只用于教学和对账，不是实盘许可。",
        ])
        (output_dir / "QMT_NEXT_ACTIONS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
