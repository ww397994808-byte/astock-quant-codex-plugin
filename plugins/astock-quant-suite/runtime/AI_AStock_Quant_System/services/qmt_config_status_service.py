from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from core.result import TaskResult
from core.run_manager import RunManager


class QMTConfigStatusService:
    """Read-only QMT config readiness report before qmt-check."""

    def run(self, config: str = "config/qmt_config.yaml") -> TaskResult:
        config_path = Path(config)
        checks = self._checks(config_path)
        blockers = [item for item in checks if item["severity"] == "blocker"]
        warnings = [item for item in checks if item["severity"] == "warning"]
        status = "READY_FOR_QMT_READONLY" if not blockers and not warnings else "NEEDS_QMT_CONFIG"
        if blockers:
            status = "BLOCKED_UNSAFE_QMT_CONFIG"
        payload = {
            "status": status,
            "config_path": str(config_path),
            "can_run_qmt_check": status == "READY_FOR_QMT_READONLY",
            "can_touch_live_trade": False,
            "checks": checks,
            "blockers": blockers,
            "warnings": warnings,
            "action_cards": self._action_cards(status, checks),
            "next_command": self._next_command(status, checks, config_path),
            "hard_boundary": "qmt-config-status 只读取本地配置；不会连接 QMT，不会发送委托，不会开启真实交易。",
        }
        ctx = RunManager().create_run("qmt_config_status")
        self._write_outputs(ctx.output_dir, payload)
        result_status = "VALID" if status in {"READY_FOR_QMT_READONLY", "NEEDS_QMT_CONFIG"} else "INVALID"
        return TaskResult(
            status=result_status,
            message=f"QMT 配置状态检查完成：{status}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=result_status,
            warnings=[item["message"] for item in blockers + warnings],
            artifacts=payload,
        )

    def _checks(self, config_path: Path) -> list[dict[str, Any]]:
        if not config_path.exists():
            return [self._check(
                "config_exists",
                "QMT 配置文件",
                False,
                "没有找到 QMT 本地配置。",
                "warning",
                "运行：python3 cli.py qmt-config-init",
            )]
        try:
            config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            return [self._check(
                "config_parse",
                "QMT 配置解析",
                False,
                f"QMT 配置无法解析：{exc}",
                "blocker",
                "修复 YAML 格式，或重新运行 qmt-config-init --force 生成安全配置。",
            )]
        checks = [
            self._check(
                "dry_run",
                "dry_run 安全开关",
                config.get("dry_run") is True,
                "dry_run=true，保持只读/沙盒优先" if config.get("dry_run") is True else "dry_run 不是 true。",
                "blocker",
                "运行：python3 cli.py qmt-config-init --force，或人工把 dry_run 改回 true。",
            ),
            self._check(
                "enable_real_trade",
                "真实交易开关",
                config.get("enable_real_trade") is False,
                "enable_real_trade=false，未开启真实交易" if config.get("enable_real_trade") is False else "enable_real_trade 已开启。",
                "blocker",
                "运行：python3 cli.py qmt-config-init --force，或人工把 enable_real_trade 改回 false。",
            ),
            self._check(
                "account_id",
                "QMT 账号",
                bool(config.get("account_id")),
                "account_id 已填写" if config.get("account_id") else "account_id 还没填写。",
                "warning",
                "运行：python3 cli.py qmt-config-init --account-id \"<你的QMT账号>\" --mini-qmt-path \"<miniQMT路径>\" --force",
            ),
            self._check(
                "mini_qmt_path",
                "miniQMT 路径",
                bool(config.get("mini_qmt_path")),
                "mini_qmt_path 已填写" if config.get("mini_qmt_path") else "mini_qmt_path 还没填写。",
                "warning",
                "运行：python3 cli.py qmt-config-init --account-id \"<你的QMT账号>\" --mini-qmt-path \"<miniQMT路径>\" --force",
            ),
        ]
        path_value = str(config.get("mini_qmt_path") or "")
        if path_value:
            checks.append(self._check(
                "mini_qmt_path_exists",
                "miniQMT 路径存在性",
                Path(path_value).expanduser().exists(),
                "miniQMT 路径存在" if Path(path_value).expanduser().exists() else f"miniQMT 路径不存在：{path_value}",
                "warning",
                "确认 miniQMT 安装路径，重新运行 qmt-config-init 写入正确路径。",
            ))
        return checks

    def _check(self, check_id: str, title: str, ok: bool, message: str, severity: str, fix: str) -> dict[str, Any]:
        return {
            "id": check_id,
            "title": title,
            "ok": ok,
            "severity": "info" if ok else severity,
            "message": message,
            "fix": "" if ok else fix,
        }

    def _action_cards(self, status: str, checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cards = []
        for check in checks:
            if check["ok"]:
                continue
            cards.append({
                "id": check["id"],
                "title": check["title"],
                "status": check["severity"],
                "action": check["fix"],
                "safe_to_copy": check["fix"].startswith("运行：python3 "),
                "why": check["message"],
            })
        if not cards and status == "READY_FOR_QMT_READONLY":
            cards.append({
                "id": "run_qmt_check",
                "title": "运行 QMT 只读检查",
                "status": "ready",
                "action": "python3 cli.py qmt-check",
                "safe_to_copy": True,
                "why": "本地配置已具备 QMT 只读检查前置条件。",
            })
        return cards

    def _next_command(self, status: str, checks: list[dict[str, Any]], config_path: Path) -> str:
        if status == "READY_FOR_QMT_READONLY":
            return "python3 cli.py qmt-check"
        if not config_path.exists():
            return "python3 cli.py qmt-config-init"
        if any(item["id"] in {"dry_run", "enable_real_trade"} and not item["ok"] for item in checks):
            return "python3 cli.py qmt-config-init --force"
        return 'python3 cli.py qmt-config-init --account-id "<你的QMT账号>" --mini-qmt-path "<miniQMT路径>" --force'

    def _write_outputs(self, output_dir: Path, payload: dict[str, Any]) -> None:
        (output_dir / "QMT_CONFIG_STATUS.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        (output_dir / "qmt_config_action_cards.json").write_text(
            json.dumps(payload["action_cards"], ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        lines = [
            "# QMT Config Status",
            "",
            f"status: {payload['status']}",
            f"can_run_qmt_check: {payload['can_run_qmt_check']}",
            f"can_touch_live_trade: {payload['can_touch_live_trade']}",
            f"config_path: {payload['config_path']}",
            "",
            "## 下一步",
            f"- `{payload['next_command']}`",
            "",
            "## 检查项",
        ]
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
        lines.extend([
            "## Hard Boundary",
            f"- {payload['hard_boundary']}",
        ])
        (output_dir / "QMT_CONFIG_STATUS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
