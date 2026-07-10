from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import yaml

from core.result import TaskResult
from core.run_manager import RunManager


class StudentDoctorService:
    """Lightweight beginner-facing environment and safety check."""

    REQUIRED_DIRS = [
        "config",
        "data",
        "reports",
        "codex_skills/astock-quant-research",
    ]
    REQUIRED_FILES = [
        "cli.py",
        "QUICK_START_FOR_STUDENTS.md",
        "codex_skills/astock-quant-research/SKILL.md",
        "codex_skills/astock-quant-research/scripts/run_astock_workflow.py",
        "config/qmt_config.example.yaml",
    ]
    REQUIRED_COMMANDS = [
        "student-workflow",
        "student-backtest-plan-precheck",
        "student-contract-check",
        "student-course-path",
        "student-first-run",
        "student-future-leak-precheck",
        "student-handoff-pack",
        "student-idea-preflight",
        "student-control-center",
        "student-run-next",
        "student-research-contract",
        "student-safe-loop",
        "student-session-index",
        "student-session-report",
        "student-start",
        "student-product-audit",
        "core5-walk-forward",
        "qmt-config-init",
        "qmt-config-status",
        "repair-dsl-backtest",
        "qmt-check",
        "qmt-readiness-dashboard",
        "stage-check",
    ]
    REQUIRED_IMPORTS = ["yaml"]

    def run(self) -> TaskResult:
        checks = []
        checks.extend(self._check_paths())
        checks.extend(self._check_imports())
        checks.extend(self._check_commands())
        checks.extend(self._check_qmt_config())
        checks.extend(self._check_sample_data())

        blockers = [check for check in checks if check["severity"] == "blocker"]
        warnings = [check for check in checks if check["severity"] == "warning"]
        status = self._status(blockers, warnings)
        next_commands = self._next_commands(status, checks)
        payload = {
            "status": status,
            "summary": self._summary(status, blockers, warnings),
            "can_start_research": status in {"READY_FOR_STUDENT_WORKFLOW", "READY_WITH_WARNINGS"},
            "can_touch_live_trade": False,
            "learner_boundary": "本体检不会连接 QMT、不会回测、不会下单；只检查新手能否安全开始。",
            "checks": checks,
            "blockers": blockers,
            "warnings": warnings,
            "next_commands": next_commands,
        }

        ctx = RunManager().create_run("student_doctor")
        self._write_outputs(ctx.output_dir, payload)
        result_status = "VALID" if payload["can_start_research"] else "INVALID"
        return TaskResult(
            status=result_status,
            message=f"学生版体检完成：{status}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=result_status,
            warnings=[item["message"] for item in blockers + warnings],
            artifacts=payload,
        )

    def _check_paths(self) -> list[dict[str, Any]]:
        checks = []
        for path in self.REQUIRED_DIRS:
            p = Path(path)
            checks.append(self._check(
                check_id=f"dir:{path}",
                title=f"目录 {path}",
                ok=p.is_dir(),
                message="已找到" if p.is_dir() else f"缺少目录：{path}",
                severity="blocker",
                fix="确认当前目录是项目根目录，或重新下载完整项目。",
            ))
        for path in self.REQUIRED_FILES:
            p = Path(path)
            checks.append(self._check(
                check_id=f"file:{path}",
                title=f"文件 {path}",
                ok=p.is_file(),
                message="已找到" if p.is_file() else f"缺少文件：{path}",
                severity="blocker",
                fix="确认当前目录是项目根目录，或重新下载完整项目。",
            ))
        qmt_config = Path("config/qmt_config.yaml")
        checks.append(self._check(
            check_id="file:config/qmt_config.yaml",
            title="QMT 本地配置",
            ok=qmt_config.is_file(),
            message="已找到 config/qmt_config.yaml" if qmt_config.is_file() else "未找到 config/qmt_config.yaml，会使用示例配置作为参考。",
            severity="warning",
            fix="从 config/qmt_config.example.yaml 复制一份为 config/qmt_config.yaml，并保持 dry_run=true、enable_real_trade=false。",
        ))
        return checks

    def _check_imports(self) -> list[dict[str, Any]]:
        checks = []
        for module in self.REQUIRED_IMPORTS:
            ok = importlib.util.find_spec(module) is not None
            checks.append(self._check(
                check_id=f"import:{module}",
                title=f"Python 依赖 {module}",
                ok=ok,
                message="可导入" if ok else f"缺少 Python 依赖：{module}",
                severity="blocker",
                fix="先安装项目依赖，再重新运行 student-doctor。",
            ))
        return checks

    def _check_commands(self) -> list[dict[str, Any]]:
        checks = []
        registry = Path("tasks/task_registry.py")
        registry_text = registry.read_text(encoding="utf-8") if registry.exists() else ""
        for command in self.REQUIRED_COMMANDS:
            ok = f'"{command}"' in registry_text
            checks.append(self._check(
                check_id=f"command:{command}",
                title=f"命令 {command}",
                ok=ok,
                message="已注册" if ok else f"命令未注册：{command}",
                severity="blocker",
                fix="检查 tasks/task_registry.py，确认新手工作流命令已经挂载。",
            ))
        return checks

    def _check_qmt_config(self) -> list[dict[str, Any]]:
        path = Path("config/qmt_config.yaml")
        if not path.exists():
            path = Path("config/qmt_config.example.yaml")
        if not path.exists():
            return [self._check(
                check_id="qmt_config:readable",
                title="QMT 安全配置",
                ok=False,
                message="没有可读取的 QMT 配置。",
                severity="blocker",
                fix="补齐 config/qmt_config.example.yaml，并创建安全的 config/qmt_config.yaml。",
            )]

        try:
            config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            return [self._check(
                check_id="qmt_config:parse",
                title="QMT 安全配置",
                ok=False,
                message=f"QMT 配置无法解析：{exc}",
                severity="blocker",
                fix="修复 YAML 格式，并保持 dry_run=true、enable_real_trade=false。",
            )]

        checks = [
            self._check(
                check_id="qmt_config:dry_run",
                title="QMT dry_run",
                ok=config.get("dry_run") is True,
                message="dry_run=true，保持沙盒优先" if config.get("dry_run") is True else "dry_run 没有保持 true。",
                severity="blocker",
                fix="人工确认后把 config/qmt_config.yaml 的 dry_run 设为 true。",
            ),
            self._check(
                check_id="qmt_config:enable_real_trade",
                title="QMT 真实交易开关",
                ok=config.get("enable_real_trade") is False,
                message="enable_real_trade=false，未开启真实交易" if config.get("enable_real_trade") is False else "enable_real_trade 已开启。",
                severity="blocker",
                fix="人工确认后把 config/qmt_config.yaml 的 enable_real_trade 设为 false。",
            ),
        ]
        for key in ["account_id", "mini_qmt_path"]:
            if not config.get(key):
                checks.append(self._check(
                    check_id=f"qmt_config:{key}",
                    title=f"QMT {key}",
                    ok=False,
                    message=f"{key} 还没填写；研究阶段可以继续，QMT 只读前需要补。",
                    severity="warning",
                    fix="运行：python3 cli.py qmt-config-status，按行动单补齐 QMT 只读配置。",
                ))
        return checks

    def _check_sample_data(self) -> list[dict[str, Any]]:
        candidates = [
            Path("data/sample/601088.csv"),
            Path("data/sample/601088.SH.csv"),
            Path("data/adjustment_factors/601088.SH.parquet"),
        ]
        ok = any(path.exists() for path in candidates)
        return [self._check(
            check_id="data:sample",
            title="入门样例数据",
            ok=ok,
            message="已找到入门样例数据" if ok else "没有找到 601088 入门样例数据。",
            severity="warning",
            fix="运行：python3 cli.py generate-sample-data --timeframe 1d --symbol 601088.SH",
        )]

    def _check(
        self,
        check_id: str,
        title: str,
        ok: bool,
        message: str,
        severity: str,
        fix: str,
    ) -> dict[str, Any]:
        return {
            "id": check_id,
            "title": title,
            "ok": ok,
            "severity": "info" if ok else severity,
            "message": message,
            "fix": "" if ok else fix,
        }

    def _status(self, blockers: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> str:
        if blockers:
            return "BLOCKED_ENVIRONMENT"
        if warnings:
            return "READY_WITH_WARNINGS"
        return "READY_FOR_STUDENT_WORKFLOW"

    def _summary(self, status: str, blockers: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> str:
        if status == "BLOCKED_ENVIRONMENT":
            return f"暂时不能给新手开始研究，先处理 {len(blockers)} 个阻断项。"
        if status == "READY_WITH_WARNINGS":
            return f"可以开始研究，但有 {len(warnings)} 个提醒需要在 QMT 或数据阶段补齐。"
        return "可以开始新手研究流程。"

    def _next_commands(self, status: str, checks: list[dict[str, Any]]) -> list[str]:
        if status == "BLOCKED_ENVIRONMENT":
            fixes = [check["fix"] for check in checks if check["severity"] == "blocker" and check["fix"]]
            return list(dict.fromkeys(fixes))[:5]
        commands = ["python3 cli.py student-control-center"]
        if any(check["id"] == "data:sample" and not check["ok"] for check in checks):
            commands.insert(0, "python3 cli.py generate-sample-data --timeframe 1d --symbol 601088.SH")
        commands.append('python3 cli.py student-workflow --idea "<包含标的的策略想法>" --timeframe 1d --adjust point_in_time_qfq --auto-refine')
        return commands

    def _write_outputs(self, output_dir: Path, payload: dict[str, Any]) -> None:
        (output_dir / "STUDENT_DOCTOR.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        (output_dir / "student_fix_actions.json").write_text(
            json.dumps(payload["next_commands"], ensure_ascii=False, indent=2), encoding="utf-8"
        )
        lines = [
            "# Student Doctor",
            "",
            f"status: {payload['status']}",
            f"can_start_research: {payload['can_start_research']}",
            f"can_touch_live_trade: {payload['can_touch_live_trade']}",
            "",
            "## 当前结论",
            f"- {payload['summary']}",
            f"- {payload['learner_boundary']}",
            "",
            "## 下一步",
        ]
        for command in payload["next_commands"]:
            lines.append(f"- `{command}`" if command.startswith("python3 ") else f"- {command}")
        lines.extend(["", "## 检查项"])
        for check in payload["checks"]:
            mark = "PASS" if check["ok"] else check["severity"].upper()
            lines.extend([
                f"### {check['title']}",
                f"- result: {mark}",
                f"- message: {check['message']}",
            ])
            if check["fix"]:
                lines.append(f"- fix: {check['fix']}")
            lines.append("")
        (output_dir / "STUDENT_DOCTOR.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
