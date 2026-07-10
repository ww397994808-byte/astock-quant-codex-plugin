from __future__ import annotations

from pathlib import Path


class BatchReport:
    def conclusion(self, summary: dict) -> str:
        weak = []
        if summary.get("cross_timeframe_stability", 1) < 0.5:
            weak.append("跨周期不稳定")
        if summary.get("cross_symbol_stability", 1) < 0.5:
            weak.append("跨标的不稳定")
        if summary.get("regime_stability", 1) < 0.5:
            weak.append("regime 不稳定")
        if summary.get("regime_slice_stability", 1) < 0.5:
            weak.append("真实 regime 区间切片不稳定")
        return "；".join(weak) if weak else "批量实验稳定性暂未发现明显短板"

    def append_to_final_report(self, path: str | Path, summary: dict) -> None:
        path = Path(path)
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        addition = "\n## 批量实验结论\n\n" + self.conclusion(summary) + "\n"
        path.write_text(text + addition, encoding="utf-8")
