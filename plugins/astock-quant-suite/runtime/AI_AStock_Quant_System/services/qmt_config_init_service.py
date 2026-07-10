from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from core.result import TaskResult
from core.run_manager import RunManager


class QMTConfigInitService:
    """Create a local QMT config with conservative dry-run defaults."""

    DEFAULT_CONFIG = {
        "dry_run": True,
        "enable_real_trade": False,
        "account_id": "",
        "mini_qmt_path": "",
        "session_id": 123456,
        "emergency_stop": False,
    }

    def run(
        self,
        *,
        config: str = "config/qmt_config.yaml",
        account_id: str | None = None,
        mini_qmt_path: str | None = None,
        session_id: int | None = None,
        force: bool = False,
    ) -> TaskResult:
        config_path = Path(config)
        existing = config_path.exists()
        if existing and not force:
            payload = self._payload(
                status="CONFIG_EXISTS",
                config_path=config_path,
                written=False,
                config_data=self._read_existing(config_path),
                warnings=["配置文件已存在；为避免误覆盖，未做修改。需要覆盖时显式加 --force。"],
            )
            return self._finish(payload, result_status="INVALID")

        data = self._base_config()
        if account_id is not None:
            data["account_id"] = str(account_id)
        if mini_qmt_path is not None:
            data["mini_qmt_path"] = str(mini_qmt_path)
        if session_id is not None:
            data["session_id"] = int(session_id)

        data["dry_run"] = True
        data["enable_real_trade"] = False
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        payload = self._payload(
            status="CONFIG_READY",
            config_path=config_path,
            written=True,
            config_data=data,
            warnings=self._warnings(data),
        )
        return self._finish(payload, result_status="VALID")

    def _base_config(self) -> dict[str, Any]:
        example = Path("config/qmt_config.example.yaml")
        if example.exists():
            try:
                loaded = yaml.safe_load(example.read_text(encoding="utf-8")) or {}
            except Exception:
                loaded = {}
            return {**self.DEFAULT_CONFIG, **loaded}
        return dict(self.DEFAULT_CONFIG)

    def _read_existing(self, path: Path) -> dict[str, Any]:
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            return {"_error": str(exc)}

    def _warnings(self, data: dict[str, Any]) -> list[str]:
        warnings = []
        if not data.get("account_id"):
            warnings.append("account_id 仍为空；研究阶段可以继续，QMT 只读前需要人工填写。")
        if not data.get("mini_qmt_path"):
            warnings.append("mini_qmt_path 仍为空；研究阶段可以继续，QMT 只读前需要人工填写。")
        warnings.append("已强制保持 dry_run=true、enable_real_trade=false；本命令不会开启真实交易。")
        return warnings

    def _payload(
        self,
        *,
        status: str,
        config_path: Path,
        written: bool,
        config_data: dict[str, Any],
        warnings: list[str],
    ) -> dict[str, Any]:
        return {
            "status": status,
            "config_path": str(config_path),
            "written": written,
            "dry_run": config_data.get("dry_run"),
            "enable_real_trade": config_data.get("enable_real_trade"),
            "account_id_present": bool(config_data.get("account_id")),
            "mini_qmt_path_present": bool(config_data.get("mini_qmt_path")),
            "warnings": warnings,
            "hard_boundary": "qmt-config-init 只写入本地安全配置；不会连接 QMT，不会发送委托，不会开启真实交易。",
        }

    def _finish(self, payload: dict[str, Any], result_status: str) -> TaskResult:
        ctx = RunManager().create_run("qmt_config_init")
        self._write_outputs(ctx.output_dir, payload)
        return TaskResult(
            status=result_status,
            message=f"QMT 配置初始化完成：{payload['status']}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=result_status,
            warnings=payload["warnings"],
            artifacts=payload,
        )

    def _write_outputs(self, output_dir: Path, payload: dict[str, Any]) -> None:
        (output_dir / "QMT_CONFIG_INIT.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        lines = [
            "# QMT Config Init",
            "",
            f"status: {payload['status']}",
            f"config_path: {payload['config_path']}",
            f"written: {payload['written']}",
            f"dry_run: {payload['dry_run']}",
            f"enable_real_trade: {payload['enable_real_trade']}",
            f"account_id_present: {payload['account_id_present']}",
            f"mini_qmt_path_present: {payload['mini_qmt_path_present']}",
            "",
            "## Warnings",
        ]
        lines.extend([f"- {item}" for item in payload["warnings"]] or ["- 暂无。"])
        lines.extend([
            "",
            "## Hard Boundary",
            f"- {payload['hard_boundary']}",
        ])
        (output_dir / "QMT_CONFIG_INIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
