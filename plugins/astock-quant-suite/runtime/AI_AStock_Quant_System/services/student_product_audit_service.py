from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from core.result import TaskResult
from core.run_manager import RunManager
from services.student_doctor_service import StudentDoctorService


class StudentProductAuditService:
    """Read-only delivery audit for the beginner A-share research product."""

    REQUIRED_DOCS = [
        "SYSTEM_CAPABILITY_MAP.md",
        "COURSE_DELIVERY_PLAN.md",
        "QUICK_START_FOR_STUDENTS.md",
        "SYSTEM_RISK_BOUNDARIES.md",
        "CODE_HEALTH_AUDIT.md",
        "FINAL_V8_ACCEPTANCE_REPORT.md",
    ]
    REQUIRED_SKILL_FILES = [
        "codex_skills/astock-quant-research/SKILL.md",
        "codex_skills/astock-quant-research/scripts/run_astock_workflow.py",
        "codex_skills/astock-quant-research/references/future_leak_rules.md",
        "codex_skills/astock-quant-research/references/workflow.md",
        "codex_skills/astock-quant-research/references/strategy_archetypes.md",
        "codex_skills/astock-quant-research/references/paper_observation.md",
        "codex_skills/astock-quant-research/references/qmt_gate.md",
    ]
    REQUIRED_PRODUCT_COMMANDS = [
        "student-doctor",
        "student-backtest-plan-precheck",
        "student-contract-check",
        "student-course-path",
        "student-first-run",
        "student-future-leak-precheck",
        "student-handoff-pack",
        "student-idea-preflight",
        "student-start",
        "student-workflow",
        "student-control-center",
        "student-run-next",
        "student-research-contract",
        "student-safe-loop",
        "student-session-index",
        "student-session-report",
        "student-product-audit",
        "core5-walk-forward",
        "repair-dsl-backtest",
        "qmt-config-init",
        "qmt-config-status",
        "qmt-check",
        "qmt-readiness-dashboard",
        "stage-check",
        "pretrade-package",
        "pretrade-runbook-refresh",
    ]
    REQUIRED_TEST_FILES = [
        "tests/test_future_leak_checker.py",
        "tests/test_no_future_execution.py",
        "tests/test_trade_rule_checker.py",
        "tests/test_paper_observation.py",
        "tests/test_student_workflow.py",
        "tests/test_student_backtest_plan_precheck.py",
        "tests/test_student_contract_check.py",
        "tests/test_student_course_path.py",
        "tests/test_student_future_leak_precheck.py",
        "tests/test_student_research_contract.py",
        "tests/test_student_control_center.py",
        "tests/test_student_start.py",
        "tests/test_student_handoff_pack.py",
        "tests/test_student_next_step_runner.py",
        "tests/test_qmt_config_status.py",
        "tests/test_qmt_readiness_dashboard.py",
        "tests/test_pretrade_package.py",
        "tests/test_asset_boundary.py",
        "tests/test_core5_walk_forward_no_future.py",
    ]

    def run(self, workflow: str | None = None, limit: int = 5) -> TaskResult:
        doctor = StudentDoctorService().run()
        checks: list[dict[str, Any]] = []
        checks.extend(self._checks_from_doctor(doctor))
        checks.extend(self._check_registered_commands())
        checks.extend(self._check_docs())
        checks.extend(self._check_skill_files())
        checks.extend(self._check_tests())
        checks.extend(self._check_qmt_safety_config())
        checks.extend(self._check_latest_workflow(workflow))
        checks.extend(self._check_recent_session_evidence(limit))

        blockers = [item for item in checks if item["status"] == "BLOCK"]
        warnings = [item for item in checks if item["status"] == "WARN"]
        status = "BLOCKED_PRODUCT_DELIVERY" if blockers else "PRODUCT_READY_WITH_WARNINGS" if warnings else "PRODUCT_READY"
        payload = {
            "status": status,
            "summary": self._summary(status, blockers, warnings),
            "can_deliver_to_students": not blockers,
            "can_touch_live_trade": False,
            "hard_boundary": "student-product-audit 只做交付体检；不会回测、不会连接 QMT、不会下单。",
            "doctor_report_path": doctor.report_path,
            "checks": checks,
            "blockers": blockers,
            "warnings": warnings,
            "cards": self._cards(checks),
            "next_commands": self._next_commands(blockers, warnings),
        }

        ctx = RunManager().create_run("student_product_audit")
        self._write_outputs(ctx.output_dir, payload)
        result_status = "VALID" if not blockers else "INVALID"
        return TaskResult(
            status=result_status,
            message=f"学员产品化体检完成：{status}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=result_status,
            warnings=[item["message"] for item in blockers + warnings],
            artifacts=payload,
        )

    def _checks_from_doctor(self, doctor: TaskResult) -> list[dict[str, Any]]:
        artifacts = doctor.artifacts or {}
        status = str(artifacts.get("status") or doctor.status)
        if doctor.status == "VALID":
            return [self._check(
                "environment:student_doctor",
                "environment",
                "学生版环境体检",
                "PASS",
                f"student-doctor={status}",
                "环境可用于新手入口。",
                "",
            )]
        return [self._check(
            "environment:student_doctor",
            "environment",
            "学生版环境体检",
            "BLOCK",
            f"student-doctor={status}",
            "环境体检未通过，不能作为课程交付入口。",
            "先运行 python3 cli.py student-doctor 并处理阻断项。",
        )]

    def _check_registered_commands(self) -> list[dict[str, Any]]:
        registry = Path("tasks/task_registry.py")
        text = registry.read_text(encoding="utf-8") if registry.exists() else ""
        checks = []
        for command in self.REQUIRED_PRODUCT_COMMANDS:
            ok = f'"{command}"' in text
            checks.append(self._check(
                f"command:{command}",
                "commands",
                f"课程命令 {command}",
                "PASS" if ok else "BLOCK",
                "已注册" if ok else "未注册",
                "学员/老师可从 CLI 使用该入口。" if ok else f"缺少 {command} 会打断课程主线。",
                "检查 tasks/task_registry.py 和 cli.py，补齐命令注册。" if not ok else "",
            ))
        return checks

    def _check_docs(self) -> list[dict[str, Any]]:
        return [
            self._file_check(
                f"doc:{path}",
                "docs",
                f"交付文档 {path}",
                Path(path),
                "BLOCK",
                "补齐课程交付文档，避免学员只能靠口头说明。",
            )
            for path in self.REQUIRED_DOCS
        ]

    def _check_skill_files(self) -> list[dict[str, Any]]:
        return [
            self._file_check(
                f"skill:{path}",
                "skill",
                f"Skill 文件 {path}",
                Path(path),
                "BLOCK",
                "补齐 skill 主文件、脚本和引用规则，确保 Codex 能按固定流程带学员。",
            )
            for path in self.REQUIRED_SKILL_FILES
        ]

    def _check_tests(self) -> list[dict[str, Any]]:
        return [
            self._file_check(
                f"test:{path}",
                "tests",
                f"关键测试 {path}",
                Path(path),
                "WARN",
                "补齐测试文件，尤其是未来函数、交易规则、学员入口和 QMT 安全边界。",
            )
            for path in self.REQUIRED_TEST_FILES
        ]

    def _check_qmt_safety_config(self) -> list[dict[str, Any]]:
        path = Path("config/qmt_config.yaml")
        if not path.exists():
            return [self._check(
                "qmt_config:local_file",
                "safety",
                "QMT 本地安全配置",
                "WARN",
                "未找到 config/qmt_config.yaml",
                "研究课程可继续，但 QMT 只读前必须生成本地安全配置。",
                "python3 cli.py qmt-config-init",
            )]
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            return [self._check(
                "qmt_config:parse",
                "safety",
                "QMT 本地安全配置",
                "BLOCK",
                f"无法解析：{exc}",
                "QMT 安全边界不可验证，不能交付。",
                "修复 config/qmt_config.yaml YAML 格式。",
            )]
        checks = [
            self._check(
                "qmt_config:dry_run",
                "safety",
                "QMT dry_run",
                "PASS" if data.get("dry_run") is True else "BLOCK",
                f"dry_run={data.get('dry_run')}",
                "保持只读/沙盒优先。" if data.get("dry_run") is True else "dry_run 未保持 true，存在误触实盘风险。",
                "人工把 config/qmt_config.yaml 的 dry_run 改回 true。" if data.get("dry_run") is not True else "",
            ),
            self._check(
                "qmt_config:enable_real_trade",
                "safety",
                "QMT 真实交易开关",
                "PASS" if data.get("enable_real_trade") is False else "BLOCK",
                f"enable_real_trade={data.get('enable_real_trade')}",
                "真实交易未开启。" if data.get("enable_real_trade") is False else "真实交易开关已开启，不能作为学员默认环境。",
                "人工把 config/qmt_config.yaml 的 enable_real_trade 改回 false。" if data.get("enable_real_trade") is not False else "",
            ),
        ]
        for key in ["account_id", "mini_qmt_path"]:
            checks.append(self._check(
                f"qmt_config:{key}",
                "safety",
                f"QMT {key}",
                "PASS" if data.get(key) else "WARN",
                "已填写" if data.get(key) else "未填写",
                "QMT 只读检查可继续准备。" if data.get(key) else "研究可继续；进入 QMT 只读前需要补齐。",
                "python3 cli.py qmt-config-status" if not data.get(key) else "",
            ))
        return checks

    def _check_latest_workflow(self, explicit: str | None) -> list[dict[str, Any]]:
        source = self._workflow_source(explicit)
        if not source:
            return [self._check(
                "workflow:latest",
                "evidence",
                "最新学员工作流证据",
                "WARN",
                "没有找到 student_workflow 报告",
                "课程环境还没有可展示的完整研究证据。",
                'python3 cli.py student-workflow --idea "<包含标的的策略想法>" --timeframe 1d --adjust point_in_time_qfq --auto-refine',
            )]
        run_dir = source.parent
        required = [
            "workflow_manifest.json",
            "STUDENT_WORKFLOW_SUMMARY.md",
            "NEXT_ACTIONS.md",
            "STUDENT_ACCEPTANCE_CHECKLIST.md",
            "STUDENT_DIAGNOSTICS.md",
            "BACKTEST_ASSUMPTION_CARD.json",
            "BACKTEST_ASSUMPTION_CARD.md",
        ]
        checks = [
            self._check(
                "workflow:latest",
                "evidence",
                "最新学员工作流证据",
                "PASS",
                str(run_dir),
                "已找到可用于教学复盘的 student-workflow 报告。",
                "",
            )
        ]
        for name in required:
            path = run_dir / name
            checks.append(self._file_check(
                f"workflow_file:{name}",
                "evidence",
                f"工作流报告 {name}",
                path,
                "WARN",
                "重新运行 student-workflow，确保学员能看到完整诊断、下一步和回测假设。",
            ))
        return checks

    def _check_recent_session_evidence(self, limit: int) -> list[dict[str, Any]]:
        workflows = list(Path("reports").glob("student_workflow_*/workflow_manifest.json"))
        session_count = 0
        for path in workflows:
            data = self._read_json(path)
            if data.get("session_id"):
                session_count += 1
        ledger = Path("reports/student_session_ledger.jsonl")
        return [
            self._check(
                "session_index:workflow_sessions",
                "teaching_ops",
                "带 session_id 的工作流",
                "PASS" if session_count else "WARN",
                f"session_workflows={session_count}",
                "老师可以按学员/案例追踪。" if session_count else "当前还缺少按学员追踪的示例证据。",
                'python3 cli.py student-workflow --idea "<策略想法>" --session-id student001 --timeframe 1d --adjust point_in_time_qfq --auto-refine' if not session_count else "",
            ),
            self._check(
                "session_index:ledger",
                "teaching_ops",
                "安全执行账本",
                "PASS" if ledger.exists() else "WARN",
                str(ledger) if ledger.exists() else "未找到 reports/student_session_ledger.jsonl",
                "可以复盘学员 safe-run 记录。" if ledger.exists() else "还没有 student-run-next 或 safe-loop 的审计记录。",
                "python3 cli.py student-run-next --dry-run" if not ledger.exists() else "",
            ),
        ][: max(1, int(limit))]

    def _workflow_source(self, explicit: str | None) -> Path | None:
        if explicit:
            path = Path(explicit)
            if path.is_dir():
                path = path / "workflow_manifest.json"
            return path if path.exists() else None
        candidates = sorted(Path("reports").glob("student_workflow_*/workflow_manifest.json"))
        return candidates[-1] if candidates else None

    def _file_check(self, check_id: str, category: str, title: str, path: Path, missing_status: str, fix: str) -> dict[str, Any]:
        ok = path.exists()
        return self._check(
            check_id,
            category,
            title,
            "PASS" if ok else missing_status,
            str(path) if ok else f"缺少 {path}",
            "已找到。" if ok else "交付材料不完整。",
            "" if ok else fix,
        )

    def _check(
        self,
        check_id: str,
        category: str,
        title: str,
        status: str,
        evidence: str,
        message: str,
        fix: str,
    ) -> dict[str, Any]:
        return {
            "id": check_id,
            "category": category,
            "title": title,
            "status": status,
            "evidence": evidence,
            "message": message,
            "fix": fix,
        }

    def _cards(self, checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        categories = []
        for category in sorted({item["category"] for item in checks}):
            items = [item for item in checks if item["category"] == category]
            blockers = [item for item in items if item["status"] == "BLOCK"]
            warnings = [item for item in items if item["status"] == "WARN"]
            status = "BLOCK" if blockers else "WARN" if warnings else "PASS"
            categories.append({
                "id": category,
                "title": self._category_title(category),
                "status": status,
                "pass_count": len([item for item in items if item["status"] == "PASS"]),
                "warning_count": len(warnings),
                "blocker_count": len(blockers),
                "action": blockers[0]["fix"] if blockers else warnings[0]["fix"] if warnings else "保持当前证据链。",
                "safe_to_copy": False,
            })
        return categories

    def _category_title(self, category: str) -> str:
        return {
            "commands": "命令入口",
            "docs": "课程文档",
            "environment": "本地环境",
            "evidence": "研究证据",
            "safety": "安全边界",
            "skill": "Codex Skill",
            "teaching_ops": "教学运营",
            "tests": "测试覆盖",
        }.get(category, category)

    def _summary(self, status: str, blockers: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> str:
        if status == "BLOCKED_PRODUCT_DELIVERY":
            return f"暂不适合交给学员使用：还有 {len(blockers)} 个阻断项。"
        if status == "PRODUCT_READY_WITH_WARNINGS":
            return f"可以作为课程/内测入口使用，但还有 {len(warnings)} 个提醒项要补。"
        return "当前项目达到课程交付体检标准；仍需遵守研究、模拟盘、QMT 只读和盘前门禁。"

    def _next_commands(self, blockers: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> list[str]:
        fixes = [item["fix"] for item in blockers + warnings if str(item.get("fix") or "").startswith("python3 ")]
        if fixes:
            return list(dict.fromkeys(fixes))[:5]
        return [
            "python3 cli.py student-start",
            "python3 cli.py student-session-index",
            "python3 cli.py student-control-center",
        ]

    def _read_json(self, path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _write_outputs(self, output_dir: Path, payload: dict[str, Any]) -> None:
        (output_dir / "STUDENT_PRODUCT_AUDIT.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        (output_dir / "student_product_cards.json").write_text(
            json.dumps(payload["cards"], ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        lines = [
            "# Student Product Audit",
            "",
            f"status: {payload['status']}",
            f"can_deliver_to_students: {payload['can_deliver_to_students']}",
            f"can_touch_live_trade: {payload['can_touch_live_trade']}",
            f"doctor_report_path: {payload.get('doctor_report_path') or 'MISSING'}",
            "",
            "## 当前结论",
            f"- {payload['summary']}",
            f"- {payload['hard_boundary']}",
            "",
            "## 下一步",
        ]
        lines.extend([f"- `{command}`" for command in payload["next_commands"]] or ["- 暂无。"])
        lines.extend(["", "## 交付卡片"])
        for card in payload["cards"]:
            lines.extend([
                f"### {card['title']}",
                f"- status: {card['status']}",
                f"- pass_count: {card['pass_count']}",
                f"- warning_count: {card['warning_count']}",
                f"- blocker_count: {card['blocker_count']}",
                f"- action: {card['action'] or 'MISSING'}",
                "",
            ])
        lines.extend(["## 阻断项"])
        lines.extend([f"- {item['title']}: {item['message']} fix={item['fix']}" for item in payload["blockers"]] or ["- NONE"])
        lines.extend(["", "## 提醒项"])
        lines.extend([f"- {item['title']}: {item['message']} fix={item['fix']}" for item in payload["warnings"]] or ["- NONE"])
        lines.extend(["", "## 全部检查"])
        for item in payload["checks"]:
            lines.extend([
                f"### {item['title']}",
                f"- category: {item['category']}",
                f"- status: {item['status']}",
                f"- evidence: {item['evidence']}",
                f"- message: {item['message']}",
            ])
            if item["fix"]:
                lines.append(f"- fix: {item['fix']}")
            lines.append("")
        (output_dir / "STUDENT_PRODUCT_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
