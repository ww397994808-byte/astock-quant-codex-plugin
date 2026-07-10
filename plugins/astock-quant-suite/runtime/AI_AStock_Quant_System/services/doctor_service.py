from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path

from core.result import TaskResult
from qmt.qmt_broker import QMTBroker
from validators.config_validator import ConfigValidator


class DoctorService:
    def run(self) -> TaskResult:
        findings = []
        for path in ["data", "config", "reports"]:
            findings.append(("OK" if Path(path).exists() else "WARN", f"目录检查：{path}"))
        findings.extend(("WARN", issue) for issue in ConfigValidator().validate())
        for module in ["yaml", "pytest"]:
            try:
                importlib.import_module(module)
                findings.append(("OK", f"依赖可用：{module}"))
            except Exception:
                findings.append(("WARN", f"依赖缺失：{module}"))
        qmt_connected = QMTBroker().connect()
        findings.append(("OK" if qmt_connected else "WARN", "QMT连接检查"))
        if os.environ.get("AI_AQ_SKIP_DOCTOR_PYTEST") == "1":
            findings.append(("OK", "测试状态：跳过嵌套 pytest 检查"))
        else:
            try:
                env = dict(os.environ)
                env["AI_AQ_SKIP_DOCTOR_PYTEST"] = "1"
                proc = subprocess.run([sys.executable, "-m", "pytest", "tests/"], text=True, capture_output=True, timeout=180, env=env)
                findings.append(("OK" if proc.returncode == 0 else "WARN", "测试状态：pytest tests/"))
            except Exception as exc:
                findings.append(("WARN", f"测试状态无法检查：{exc}"))
        lines = ["# Doctor Report", ""]
        lines.extend([f"- [{level}] {msg}" for level, msg in findings])
        Path("doctor_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        status = "VALID" if all(level == "OK" for level, _ in findings if "QMT" not in _) else "INVALID"
        return TaskResult(status, "doctor 检查完成", report_path="doctor_report.md", warnings=[msg for level, msg in findings if level != "OK"])
