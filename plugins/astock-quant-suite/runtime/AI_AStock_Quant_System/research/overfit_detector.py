from __future__ import annotations

import ast
from pathlib import Path


class OverfitDetector:
    def detect(self, result: dict, search_space: dict) -> list[str]:
        flags: list[str] = []
        in_ret = float(result.get("in_sample_return", 0) or 0)
        out_ret = float(result.get("out_sample_return", 0) or 0)
        trade_count = int(float(result.get("trade_count", 0) or 0))
        if in_ret > 0 and out_ret < in_ret * 0.3:
            flags.append("样本内好、样本外明显退化")
        params = self._parse_params(result.get("params", "{}"))
        for key, value in params.items():
            values = search_space.get(key, [])
            if values and value in {min(values), max(values)}:
                flags.append(f"参数 {key} 位于搜索边界")
        if trade_count < 3:
            flags.append("交易次数过少，结果不稳定")
        if result.get("audit_status") == "INVALID":
            flags.append("审计 INVALID")
        if str(result.get("future_leak_risk", "")).upper() == "HIGH":
            flags.append("未来函数 HIGH 风险")
        if abs(float(result.get("total_return", 0) or 0)) > 0 and trade_count <= 1:
            flags.append("收益可能由少数交易贡献")
        if abs(in_ret - out_ret) > 0.2:
            flags.append("Walk Forward 不稳定")
        return flags

    def write_report(self, path: str | Path, results: list[dict], search_space: dict) -> dict[str, list[str]]:
        report = {row["variant_id"]: self.detect(row, search_space) for row in results}
        lines = ["# Overfit Report", ""]
        for variant_id, flags in report.items():
            lines.append(f"## {variant_id}")
            if flags:
                lines.extend([f"- {flag}" for flag in flags])
            else:
                lines.append("- 未发现明显过拟合信号。")
            lines.append("")
        Path(path).write_text("\n".join(lines), encoding="utf-8")
        return report

    def _parse_params(self, text) -> dict:
        if isinstance(text, dict):
            return text
        try:
            return ast.literal_eval(str(text))
        except Exception:
            return {}

