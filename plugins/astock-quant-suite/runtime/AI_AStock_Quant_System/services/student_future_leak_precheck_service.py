from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from audit.future_leak_checker import FutureLeakChecker
from core.result import TaskResult
from core.run_manager import RunManager


class StudentFutureLeakPrecheckService:
    """Beginner-facing static precheck for obvious future-looking strategy code."""

    def run(
        self,
        code: str | None = None,
        file: str | None = None,
        strategy_name: str | None = None,
        session_id: str | None = None,
    ) -> TaskResult:
        strategy_name = self._clean_label(strategy_name) or "student_strategy"
        session_id = self._clean_label(session_id)
        source = self._load_source(code, file)
        if source["status"] != "OK":
            payload = self._missing_payload(source, strategy_name, session_id)
        else:
            payload = self._payload(source, strategy_name, session_id)

        ctx = RunManager().create_run("student_future_leak_precheck")
        self._write_outputs(ctx.output_dir, payload, source)
        result_status = "VALID" if payload["status"] == "LEAK_CHECK_VALID" else "INVALID"
        warnings = [item["message"] for item in payload.get("blockers", []) + payload.get("warnings", [])]
        return TaskResult(
            status=result_status,
            message=f"未来函数代码预检完成：{payload['status']}",
            run_id=ctx.run_id,
            report_path=str(ctx.output_dir),
            audit_status=result_status,
            warnings=warnings,
            artifacts=payload,
        )

    def _load_source(self, code: str | None, file: str | None) -> dict[str, Any]:
        file_text = str(file or "").strip()
        code_text = str(code or "")
        if file_text:
            path = Path(file_text).expanduser()
            if not path.exists():
                return {"status": "MISSING_FILE", "path": str(path), "code": "", "error": f"找不到文件：{path}"}
            if not path.is_file():
                return {"status": "NOT_A_FILE", "path": str(path), "code": "", "error": f"不是普通文件：{path}"}
            try:
                return {"status": "OK", "path": str(path), "code": path.read_text(encoding="utf-8"), "source_type": "file"}
            except UnicodeDecodeError:
                return {"status": "READ_ERROR", "path": str(path), "code": "", "error": "文件不是 UTF-8 文本。"}
        if code_text.strip():
            return {"status": "OK", "path": "<inline>", "code": code_text, "source_type": "inline"}
        return {"status": "MISSING_CODE", "path": "", "code": "", "error": "没有提供 --file 或 --code。"}

    def _payload(self, source: dict[str, Any], strategy_name: str, session_id: str) -> dict[str, Any]:
        report = FutureLeakChecker().check_code_text(str(source.get("code") or ""))
        findings = self._normalize_findings(report.get("findings") or [], str(source.get("path") or "<inline>"))
        high = [item for item in findings if item["severity"] == "HIGH"]
        medium = [item for item in findings if item["severity"] == "MEDIUM"]
        status = "LEAK_RISK_FOUND" if high else "LEAK_CHECK_VALID"
        blockers = [
            self._issue(
                item.get("code") or "future_leak",
                "发现未来函数高风险",
                item["message"],
                "修改策略代码，确保交易信号只能使用当前 K 线及以前的 OHLCV；再重新运行 student-future-leak-precheck。",
            )
            for item in high
        ]
        warnings = [
            self._issue(
                item.get("code") or "future_leak_warning",
                "未来函数提醒",
                item["message"],
                "确认是否使用了全样本统计、最优参数或后验标签；必要时改为滚动/扩展历史窗口。",
            )
            for item in medium
        ]
        next_command = (
            'python3 cli.py student-idea-preflight --idea "<策略想法>"'
            if status == "LEAK_CHECK_VALID"
            else self._rerun_command(source)
        )
        payload = {
            "status": status,
            "summary": self._summary(status, high, medium),
            "strategy_name": strategy_name,
            "session_id": session_id,
            "source_type": source.get("source_type", ""),
            "source_path": source.get("path", ""),
            "safe_to_copy": status == "LEAK_CHECK_VALID",
            "next_command": next_command,
            "hard_boundary": "student-future-leak-precheck 只做静态代码预检；不会回测、不会连接 QMT、不会下单，也不能替代完整 audit/stage-check。",
            "student_rule": "所有产生交易信号的数据只能使用当前 K 线及以前的 OHLCV/成交量；未来数据、负向 shift、居中窗口、forward merge、未来标签和当前 K 线收盘价成交都属于未来函数风险。",
            "checker_report": {
                "status": report.get("status", "VALID"),
                "finding_count": len(findings),
                "high_count": len(high),
                "medium_count": len(medium),
                "findings": findings,
            },
            "blockers": blockers,
            "warnings": warnings,
            "cards": self._cards(status, findings, next_command),
        }
        return payload

    def _missing_payload(self, source: dict[str, Any], strategy_name: str, session_id: str) -> dict[str, Any]:
        blocker = self._issue(
            "missing_code",
            "缺少策略代码",
            str(source.get("error") or "没有可检查的代码。"),
            '传入 --file <策略文件.py>，或传入 --code "signal = close.rolling(20).mean()"。',
        )
        return {
            "status": "MISSING_CODE",
            "summary": "还没有策略代码，不能做未来函数预检。",
            "strategy_name": strategy_name,
            "session_id": session_id,
            "source_type": "",
            "source_path": source.get("path", ""),
            "safe_to_copy": False,
            "next_command": 'python3 cli.py student-future-leak-precheck --file "<策略文件.py>"',
            "hard_boundary": "student-future-leak-precheck 只做静态代码预检；不会回测、不会连接 QMT、不会下单，也不能替代完整 audit/stage-check。",
            "student_rule": "所有产生交易信号的数据只能使用当前 K 线及以前的 OHLCV/成交量。",
            "checker_report": {"status": "INVALID", "finding_count": 0, "high_count": 0, "medium_count": 0, "findings": []},
            "blockers": [blocker],
            "warnings": [],
            "cards": self._cards("MISSING_CODE", [], 'python3 cli.py student-future-leak-precheck --file "<策略文件.py>"'),
        }

    def _normalize_findings(self, findings: list[dict[str, Any]], path: str) -> list[dict[str, Any]]:
        normalized = []
        seen = set()
        for item in findings:
            message = str(item.get("message") or "").strip()
            severity = str(item.get("severity") or "MEDIUM").upper()
            code = str(item.get("code") or "")
            line = item.get("line")
            key = (severity, message, code, line)
            if not message or key in seen:
                continue
            seen.add(key)
            out = {"severity": severity, "message": message, "path": str(item.get("path") or path)}
            if code:
                out["code"] = code
            if line:
                out["line"] = line
            normalized.append(out)
        return normalized

    def _cards(self, status: str, findings: list[dict[str, Any]], next_command: str) -> list[dict[str, Any]]:
        high = sum(1 for item in findings if item["severity"] == "HIGH")
        medium = sum(1 for item in findings if item["severity"] == "MEDIUM")
        return [
            {
                "id": "future_leak_static_precheck",
                "title": "未来函数静态预检",
                "status": "PASS" if status == "LEAK_CHECK_VALID" else "BLOCK",
                "action": "可以进入想法预检或完整 student-workflow；仍需完整 audit/stage-check。" if status == "LEAK_CHECK_VALID" else "先修复 HIGH 风险未来函数，再继续研究。",
                "why": f"high={high}; medium={medium}",
                "command": next_command,
                "safe_to_copy": status == "LEAK_CHECK_VALID",
            },
            {
                "id": "signal_causality_rule",
                "title": "信号因果边界",
                "status": "PASS" if high == 0 else "BLOCK",
                "action": "信号只允许看当前及以前 K 线。" if high == 0 else "删除未来 K 线、未来标签、负向位移或后验对齐。",
                "why": "rule=current_or_past_ohlcv_only",
                "command": next_command,
                "safe_to_copy": False,
            },
        ]

    def _summary(self, status: str, high: list[dict[str, Any]], medium: list[dict[str, Any]]) -> str:
        if status == "LEAK_RISK_FOUND":
            return f"发现 {len(high)} 个 HIGH 未来函数风险，不能进入回测或 QMT 链路。"
        return f"未发现 HIGH 风险未来函数；有 {len(medium)} 个提醒项，后续仍需完整 audit/stage-check。"

    def _rerun_command(self, source: dict[str, Any]) -> str:
        if source.get("source_type") == "file" and source.get("path"):
            return f"python3 cli.py student-future-leak-precheck --file {json.dumps(source['path'], ensure_ascii=False)}"
        return 'python3 cli.py student-future-leak-precheck --code "<修复后的策略代码>"'

    def _issue(self, issue_id: str, title: str, message: str, fix: str) -> dict[str, str]:
        return {"id": issue_id, "title": title, "message": message, "fix": fix}

    def _clean_label(self, value: str | None) -> str:
        text = str(value or "").strip()
        return "".join(ch for ch in text if ch.isalnum() or ch in {"-", "_", "."})[:80]

    def _write_outputs(self, output_dir: Path, payload: dict[str, Any], source: dict[str, Any]) -> None:
        (output_dir / "STUDENT_FUTURE_LEAK_PRECHECK.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        (output_dir / "student_future_leak_cards.json").write_text(
            json.dumps(payload["cards"], ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        if source.get("status") == "OK":
            (output_dir / "submitted_strategy.py").write_text(str(source.get("code") or ""), encoding="utf-8")
        lines = [
            "# Student Future Leak Precheck",
            "",
            f"status: {payload['status']}",
            f"strategy_name: {payload['strategy_name']}",
            f"session_id: {payload.get('session_id') or 'MISSING'}",
            f"source: {payload.get('source_path') or 'MISSING'}",
            f"safe_to_copy: {payload['safe_to_copy']}",
            "",
            "## 当前结论",
            f"- {payload['summary']}",
            f"- {payload['hard_boundary']}",
            f"- {payload['student_rule']}",
            "",
            "## 下一步",
            f"- command: `{payload['next_command']}`",
            "",
            "## 检查结果",
            f"- checker_status: {payload['checker_report']['status']}",
            f"- high_count: {payload['checker_report']['high_count']}",
            f"- medium_count: {payload['checker_report']['medium_count']}",
            "",
            "## 发现项",
        ]
        if payload["checker_report"]["findings"]:
            for item in payload["checker_report"]["findings"]:
                line = f"- [{item['severity']}] {item['message']} ({item.get('path') or 'MISSING'}"
                if item.get("line"):
                    line += f":{item['line']}"
                line += ")"
                lines.append(line)
        else:
            lines.append("- NONE")
        lines.extend(["", "## 修复清单"])
        lines.extend([f"- {item['title']}: {item['message']} fix={item['fix']}" for item in payload.get("blockers") or []] or ["- NONE"])
        lines.extend(["", "## 提醒项"])
        lines.extend([f"- {item['title']}: {item['message']} fix={item['fix']}" for item in payload.get("warnings") or []] or ["- NONE"])
        lines.extend(["", "## 卡片"])
        for card in payload["cards"]:
            lines.extend([
                f"### {card['title']}",
                f"- status: {card['status']}",
                f"- action: {card['action']}",
                f"- why: {card['why']}",
                f"- command: `{card['command']}`",
                f"- safe_to_copy: {card['safe_to_copy']}",
                "",
            ])
        (output_dir / "STUDENT_FUTURE_LEAK_PRECHECK.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
