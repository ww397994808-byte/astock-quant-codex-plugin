from __future__ import annotations

import json
import shutil
from pathlib import Path

from core.result import TaskResult
from core.run_manager import RunManager
from services.pretrade_service import PreTradeService
from services.stage_check_service import StageCheckService


class PretradePackageService:
    def run(
        self,
        promotion: str,
        symbol: str | None = None,
        strategy: str = "compiled_repair_dsl",
        qmt_run_id: str | None = None,
        confirmation: str = "",
    ) -> TaskResult:
        promotion_path = Path(promotion)
        promotion_data = json.loads(promotion_path.read_text(encoding="utf-8"))
        selected = promotion_data.get("candidate") or {}
        candidate_run_id = self._run_id_from_report_path(str(selected.get("report_path") or promotion_data.get("source_report_path") or ""))
        selected_symbol = symbol or self._symbol_from_selected_dsl(promotion_data.get("selected_dsl_path", ""))

        stage_result = StageCheckService().run(run_id=candidate_run_id, qmt_run_id=qmt_run_id)
        stage = stage_result.artifacts.get("stage_gate", {}).get("stage", "INVALID")
        pretrade = PreTradeService().run(
            strategy=strategy,
            symbol=selected_symbol,
            confirmation=confirmation,
            run_id=candidate_run_id,
            qmt_run_id=qmt_run_id,
        )

        ctx = RunManager().create_run("pretrade_package")
        package = {
            "status": "READY_FOR_PRETRADE_CHECK" if stage == "QMT_READONLY_READY" else "BLOCKED_BEFORE_PRETRADE",
            "promotion_path": str(promotion_path),
            "selected_variant_id": promotion_data.get("selected_variant_id"),
            "selected_dsl_path": promotion_data.get("selected_dsl_path"),
            "candidate_run_id": candidate_run_id,
            "strategy": strategy,
            "symbol": selected_symbol,
            "qmt_run_id": qmt_run_id or stage_result.artifacts.get("qmt_run_id", ""),
            "stage": stage,
            "stage_reasons": stage_result.warnings,
            "pretrade_status": pretrade.status,
            "pretrade_failures": pretrade.warnings,
            "fix_plan": self._build_fix_plan(stage_result.warnings, pretrade.warnings),
            "required_next_commands": self._required_next_commands(candidate_run_id, qmt_run_id, stage),
            "hard_boundary": "pretrade-check VALID 且人工确认前，不允许真实下单。",
        }
        package["runbook_summary"] = self._runbook_summary(package["fix_plan"])
        self._copy_evidence(ctx.output_dir, promotion_data, candidate_run_id, package["qmt_run_id"], pretrade.report_path)
        (ctx.output_dir / "PRETRADE_READINESS_PACKAGE.json").write_text(
            json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self._write_report(ctx.output_dir, package)
        self._write_runbook(ctx.output_dir, package)
        status = "VALID" if package["status"] == "READY_FOR_PRETRADE_CHECK" else "INVALID"
        return TaskResult(
            status=status,
            message=f"实盘前证据包生成完成：{package['status']}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=status,
            warnings=package["stage_reasons"] + package["pretrade_failures"],
            artifacts=package,
        )

    def _run_id_from_report_path(self, report_path: str) -> str:
        if not report_path:
            raise ValueError("promotion 中缺少候选 report_path，无法生成 pretrade 证据包。")
        return Path(report_path).name

    def _symbol_from_selected_dsl(self, dsl_path: str) -> str:
        if not dsl_path:
            return ""
        path = Path(dsl_path)
        if not path.exists():
            return ""
        import yaml

        dsl = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        symbols = dsl.get("symbols") or []
        return str(symbols[0]) if symbols else ""

    def _required_next_commands(self, candidate_run_id: str, qmt_run_id: str | None, stage: str) -> list[str]:
        if not qmt_run_id:
            return [
                "python3 cli.py qmt-check",
                f"python3 cli.py stage-check --run-id {candidate_run_id} --qmt-run-id <qmt_run_id>",
            ]
        if stage != "QMT_READONLY_READY":
            return [f"python3 cli.py stage-check --run-id {candidate_run_id} --qmt-run-id {qmt_run_id}"]
        return [
            f"python3 cli.py pretrade-check --strategy compiled_repair_dsl --symbol <symbol> --run-id {candidate_run_id} --qmt-run-id {qmt_run_id}",
            "只有 pretrade-check VALID 后，才允许人工输入 CONFIRM_REAL_TRADE 进入最后确认。",
        ]

    def _copy_evidence(self, output_dir: Path, promotion_data: dict, candidate_run_id: str, qmt_run_id: str, pretrade_report_path: str | None) -> None:
        evidence_dir = output_dir / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        sources = [
            Path(promotion_data.get("selected_dsl_path") or ""),
            Path("reports") / candidate_run_id / "audit_report.md",
            Path("reports") / candidate_run_id / "paper_observation_report.md",
            Path("reports") / candidate_run_id / "stage_gate_report.md",
            Path("reports") / candidate_run_id / "performance.json",
            Path("reports") / candidate_run_id / "trades.csv",
            Path("reports") / qmt_run_id / "qmt_readonly_report.md" if qmt_run_id else Path(),
            Path("reports") / qmt_run_id / "qmt_account_snapshot.json" if qmt_run_id else Path(),
            Path(pretrade_report_path or "") / "pretrade_report.md" if pretrade_report_path else Path(),
        ]
        for src in sources:
            if src and src.exists() and src.is_file():
                shutil.copyfile(src, evidence_dir / src.name)

    def _write_report(self, output_dir: Path, package: dict) -> None:
        lines = [
            "# Pretrade Readiness Package",
            "",
            f"status: {package['status']}",
            f"selected_variant_id: {package.get('selected_variant_id')}",
            f"candidate_run_id: {package.get('candidate_run_id')}",
            f"qmt_run_id: {package.get('qmt_run_id') or 'MISSING'}",
            f"stage: {package.get('stage')}",
            f"pretrade_status: {package.get('pretrade_status')}",
            f"runbook_verified: {package.get('runbook_summary', {}).get('verified', 0)}",
            f"runbook_pending: {package.get('runbook_summary', {}).get('pending', 0)}",
            f"runbook_blocked: {package.get('runbook_summary', {}).get('blocked', 0)}",
            "",
            "## 当前结论",
        ]
        if package["status"] == "READY_FOR_PRETRADE_CHECK":
            lines.append("- QMT 只读和阶段门已到 QMT_READONLY_READY，但这仍不是实盘许可。")
        else:
            lines.append("- 证据尚未到 QMT_READONLY_READY，不能进入实盘前确认。")
        lines.extend([
            f"- {package['hard_boundary']}",
            "",
            "## 阻断项",
        ])
        blockers = list(package.get("stage_reasons") or []) + list(package.get("pretrade_failures") or [])
        lines.extend([f"- {item}" for item in blockers] or ["- 当前包未发现新的阻断项。"])
        lines.extend(["", "## 修复清单"])
        for item in package.get("fix_plan") or []:
            lines.extend([
                f"### {item['title']}",
                f"- category: {item['category']}",
                f"- runbook_type: {item['runbook_type']}",
                f"- severity: {item['severity']}",
                f"- stop_trading: {item['stop_trading']}",
                f"- status: {item['status']}",
                f"- owner: {item['owner']}",
                f"- failure: {item['failure']}",
                f"- can_auto_fix: {item['can_auto_fix']}",
                f"- action: {item['action']}",
                f"- verification: {item['verification']}",
            ])
            if item.get("command"):
                lines.append(f"- command: `{item['command']}`")
            lines.append("")
        lines.extend(["", "## 下一步命令"])
        lines.extend([f"- `{cmd}`" for cmd in package.get("required_next_commands") or []])
        lines.extend([
            "",
            "## 证据文件",
            "- evidence/ 下包含候选 DSL、审计、模拟盘、阶段门、QMT 只读和 pretrade 检查报告的副本。",
            "",
            "## 禁止事项",
            "- 不允许把 QMT_READONLY_READY 当成下单许可。",
            "- 不允许跳过 pretrade-check。",
            "- 不允许在没有人工确认的情况下执行真实下单。",
        ])
        (output_dir / "PRETRADE_READINESS_PACKAGE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_runbook(self, output_dir: Path, package: dict) -> None:
        runbook = {
            "status": package["status"],
            "candidate_run_id": package["candidate_run_id"],
            "qmt_run_id": package.get("qmt_run_id"),
            "hard_boundary": package["hard_boundary"],
            "summary": package.get("runbook_summary", {}),
            "sections": self._runbook_sections(package.get("fix_plan") or []),
        }
        (output_dir / "PRETRADE_RUNBOOK.json").write_text(
            json.dumps(runbook, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        lines = [
            "# Pretrade Runbook",
            "",
            f"status: {runbook['status']}",
            f"candidate_run_id: {runbook['candidate_run_id']}",
            f"qmt_run_id: {runbook.get('qmt_run_id') or 'MISSING'}",
            f"verified: {runbook['summary'].get('verified', 0)}",
            f"pending: {runbook['summary'].get('pending', 0)}",
            f"blocked: {runbook['summary'].get('blocked', 0)}",
            "",
            "## 硬边界",
            f"- {runbook['hard_boundary']}",
            "- 任何 stop_trading=true 的事项未解除前，当天停止推进实盘。",
            "- 所有 manual_confirmation 项只能由操作者确认，系统不能代填。",
            "",
        ]
        for section in runbook["sections"]:
            lines.extend([f"## {section['title']}", ""])
            for item in section["items"]:
                lines.extend([
                    f"### {item['title']}",
                    f"- failure: {item['failure']}",
                    f"- severity: {item['severity']}",
                    f"- stop_trading: {item['stop_trading']}",
                    f"- status: {item['status']}",
                    f"- owner: {item['owner']}",
                    f"- action: {item['action']}",
                    f"- verification: {item['verification']}",
                ])
                if item.get("command"):
                    lines.append(f"- command: `{item['command']}`")
                lines.append("")
        (output_dir / "PRETRADE_RUNBOOK.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _runbook_sections(self, fix_plan: list[dict]) -> list[dict]:
        order = [
            ("run_command", "可运行检查"),
            ("manual_review", "人工复核"),
            ("manual_confirmation", "人工确认边界"),
            ("stop_trading", "停止推进事项"),
        ]
        grouped = []
        for key, title in order:
            items = [item for item in fix_plan if item.get("runbook_type") == key]
            if items:
                grouped.append({"type": key, "title": title, "items": items})
        return grouped

    def _runbook_summary(self, fix_plan: list[dict]) -> dict:
        summary = {"verified": 0, "pending": 0, "blocked": 0}
        for item in fix_plan:
            status = item.get("status", "pending")
            summary[status] = summary.get(status, 0) + 1
        summary["total"] = len(fix_plan)
        return summary

    def _build_fix_plan(self, stage_reasons: list[str], pretrade_failures: list[str]) -> list[dict]:
        items: list[dict] = []
        for failure in list(stage_reasons) + list(pretrade_failures):
            items.append(self._fix_item_for(failure))
        seen = set()
        unique = []
        for item in items:
            key = (item["category"], item["failure"])
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique

    def _fix_item_for(self, failure: str) -> dict:
        normalized_failure = failure.replace("阶段阻断：", "")
        rules = [
            ("QMT 只读检查未通过", "QMT 只读", "run_command", "HIGH", False, "operator", "先修 QMT 连接和只读账户读取；只允许读取账户、资金、持仓、委托、成交。", "python3 cli.py qmt-check", "qmt_readonly_report.md status 必须为 VALID。"),
            ("QMT 未连接", "QMT 只读", "run_command", "HIGH", False, "operator", "启动 QMT/xtquant 环境，确认账号可读取；不要开启真实交易。", "python3 cli.py qmt-check", "qmt_account_snapshot.json 中 ok=true。"),
            ("账户不可用", "QMT 只读", "run_command", "HIGH", False, "operator", "检查账号登录、权限和账户选择；只修读取权限。", "python3 cli.py qmt-check", "account_available 必须为 true。"),
            ("dry_run", "人工安全开关", "manual_confirmation", "CRITICAL", False, "human", "保持 dry_run=true，直到所有 pretrade 项通过且人工确认。该项不能由系统自动关闭。", "", "人工确认前 dry_run 不应关闭。"),
            ("enable_real_trade 未开启", "人工安全开关", "manual_confirmation", "CRITICAL", False, "human", "这是最后阶段人工开关；不要为了让测试变绿提前打开。", "", "只有完成 QMT_READONLY_READY、pretrade 其他项、人工确认后才讨论。"),
            ("未输入 CONFIRM_REAL_TRADE", "人工确认", "manual_confirmation", "CRITICAL", False, "human", "二次确认只能由操作者在最后一步手动输入，系统不能代填。", "", "pretrade-check 命令显式包含人工输入。"),
            ("当前不在交易时间", "交易时间", "manual_review", "MEDIUM", False, "operator", "等待 A股连续竞价交易时段再执行 pretrade 检查。", "", "交易时间内重新运行 pretrade-check。"),
            ("数据不是最新", "行情数据", "run_command", "HIGH", False, "operator", "更新行情数据并确认最后一根 K 线时间符合当前周期。", "python3 cli.py update-data --symbol <symbol> --timeframe 1d --adjust point_in_time_qfq", "data-status 显示数据最新。"),
            ("标的不可交易或停牌", "标的状态", "stop_trading", "CRITICAL", True, "operator", "检查停牌、退市风险、交易权限和证券代码映射。", "", "券商/QMT 返回标的可交易。"),
            ("标的处于涨跌停", "价格约束", "stop_trading", "CRITICAL", True, "operator", "等待非涨跌停状态，或取消本次下单计划。", "", "pretrade-check 中 not_limit_price=true。"),
            ("今日亏损超过限制", "风控", "stop_trading", "CRITICAL", True, "operator", "停止当日交易，复核日内亏损和风控阈值。", "", "daily_loss_ok=true 且有人工复核记录。"),
            ("单票仓位超过限制", "仓位风控", "manual_review", "HIGH", False, "operator", "降低单票目标仓位或先减仓，不允许加仓。", "", "single_position_ok=true。"),
            ("总仓位超过限制", "仓位风控", "manual_review", "HIGH", False, "operator", "降低组合总仓位，不允许继续放大风险。", "", "total_position_ok=true。"),
            ("存在重复下单风险", "订单卫生", "manual_review", "HIGH", False, "operator", "清理/确认未完成委托，避免重复发送同方向订单。", "", "no_duplicate_order=true。"),
            ("存在未处理异常订单", "订单卫生", "manual_review", "HIGH", False, "operator", "处理异常委托、废单、撤单状态，再重新检查。", "", "no_abnormal_order=true。"),
            ("阶段未达到 QMT_READONLY_READY", "阶段门", "run_command", "HIGH", False, "operator", "先让 stage-check 达到 QMT_READONLY_READY，再看 pretrade。", "python3 cli.py stage-check --run-id <candidate_run_id> --qmt-run-id <qmt_run_id>", "stage_gate_report.md stage=QMT_READONLY_READY。"),
        ]
        for needle, category, runbook_type, severity, stop_trading, owner, action, command, verification in rules:
            if needle in normalized_failure:
                return {
                    "failure": normalized_failure,
                    "category": category,
                    "title": needle,
                    "runbook_type": runbook_type,
                    "severity": severity,
                    "stop_trading": stop_trading,
                    "owner": owner,
                    "status": "blocked" if stop_trading else "pending",
                    "can_auto_fix": False,
                    "action": action,
                    "command": command,
                    "verification": verification,
                }
        return {
            "failure": normalized_failure,
            "category": "其他",
            "title": "未分类阻断项",
            "runbook_type": "manual_review",
            "severity": "MEDIUM",
            "stop_trading": False,
            "owner": "operator",
            "status": "pending",
            "can_auto_fix": False,
            "action": "人工复核该阻断项，确认是否属于 QMT、数据、风控或订单安全问题。",
            "command": "",
            "verification": "阻断项从 pretrade_report.md 中消失。",
        }
