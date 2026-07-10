from __future__ import annotations

import csv
import re
from pathlib import Path
from strategy_safety.causality_checker import SignalCausalityChecker


class FutureLeakChecker:
    PATTERNS = [
        (re.compile(r"shift\s*\(\s*-\d+"), "检测到 shift(-n)，疑似使用未来数据", "HIGH"),
        (re.compile(r"shift\s*\([^)]*periods\s*=\s*-\d+"), "检测到 shift(periods=-n)，疑似使用未来数据", "HIGH"),
        (re.compile(r"(pct_change|diff)\s*\(\s*-\d+"), "检测到 pct_change/diff(-n)，疑似使用未来数据", "HIGH"),
        (re.compile(r"(pct_change|diff)\s*\([^)]*(periods|period|n)\s*=\s*-\d+"), "检测到 pct_change/diff 负周期，疑似使用未来数据", "HIGH"),
        (re.compile(r"iloc\s*\[[^\]]*\+\s*1\]"), "检测到 iloc[i+1]，疑似读取未来 K 线", "HIGH"),
        (re.compile(r"future_return|未来收益"), "检测到未来收益字段或变量", "HIGH"),
        (re.compile(r"rolling\s*\([^)]*center\s*=\s*True"), "检测到 rolling(center=True)，居中窗口疑似读取未来 K 线", "HIGH"),
        (re.compile(r"merge_asof\s*\([^)]*direction\s*=\s*['\"]forward['\"]"), "检测到 merge_asof(direction='forward')，疑似并入未来数据", "HIGH"),
        (re.compile(r"\.rolling\([^)]*\).*shift\s*\(\s*-\d+"), "rolling 后负向 shift，疑似错误对齐", "HIGH"),
        (re.compile(r"全样本|max\(\s*closes\s*\)|min\(\s*closes\s*\)|mean\(\s*all|std\(\s*all"), "疑似全样本统计生成信号", "MEDIUM"),
        (re.compile(r"best_params|最优参数"), "只报告最优参数时需样本外验证", "MEDIUM"),
    ]

    def check(self, output_dir: str | Path, source_paths: list[Path] | None = None) -> dict:
        output_dir = Path(output_dir)
        findings: list[dict] = []
        for path in source_paths or []:
            if path.exists():
                text = path.read_text(encoding="utf-8")
                for regex, message, severity in self.PATTERNS:
                    if regex.search(text):
                        findings.append({"severity": severity, "message": message, "path": str(path)})
                causality = SignalCausalityChecker().check_text(text).to_dict()
                for item in causality.get("findings", []):
                    findings.append({**item, "path": str(path)})
        orders_path = output_dir / "orders.csv"
        if orders_path.exists():
            with orders_path.open("r", encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    signal_time = row.get("signal_datetime") or row.get("signal_time")
                    execute_time = row.get("execute_datetime") or row.get("execute_time")
                    if signal_time and execute_time and signal_time >= execute_time:
                        findings.append({"severity": "HIGH", "message": "订单 signal_time >= execute_time，存在当前 K 线成交或时间倒挂", "path": str(orders_path)})
        status = "INVALID" if any(f["severity"] == "HIGH" for f in findings) else "VALID"
        report = {"status": status, "findings": findings}
        self._write_report(output_dir / "future_leak_report.md", report)
        SignalCausalityChecker().write_report(
            output_dir / "causality_report.md",
            {"status": status, "findings": [f for f in findings if f.get("code") or "未来" in f.get("message", "")]},
        )
        return report

    def check_code_text(self, text: str) -> dict:
        findings = []
        for regex, message, severity in self.PATTERNS:
            if regex.search(text):
                findings.append({"severity": severity, "message": message, "path": "<memory>"})
        causality = SignalCausalityChecker().check_text(text).to_dict()
        findings.extend([{**item, "path": "<memory>"} for item in causality.get("findings", [])])
        return {"status": "INVALID" if any(f["severity"] == "HIGH" for f in findings) else "VALID", "findings": findings}

    def _write_report(self, path: Path, report: dict) -> None:
        lines = ["# Future Leak Report", "", f"status: {report['status']}", ""]
        for item in report["findings"]:
            lines.append(f"- [{item['severity']}] {item['message']} ({item['path']})")
        if not report["findings"]:
            lines.append("- 未发现 HIGH 风险未来函数问题。")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
