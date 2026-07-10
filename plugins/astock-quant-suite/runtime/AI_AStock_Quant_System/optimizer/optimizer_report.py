from __future__ import annotations

from pathlib import Path


def write_optimizer_report(path: str | Path, opt: dict, wf: dict, stability: dict) -> None:
    lines = [
        "# Optimizer Report",
        "",
        "## 样本内 / 样本外",
        f"- 样本内组合数：{wf.get('in_sample_count')}",
        f"- 样本外组合数：{wf.get('out_sample_count')}",
        f"- 是否存在样本外：{wf.get('has_out_sample')}",
        "",
        "## 推荐参数",
        f"- best: {opt.get('best')}",
        "",
        "## 参数稳定性排名",
    ]
    for item in stability.get("stable_rank", []):
        lines.append(f"- {item}")
    lines.extend([
        "",
        f"过拟合风险：{stability.get('overfit_risk')}",
        "不推荐参数：样本外缺失、回撤过大或审计 INVALID 的参数组合。",
    ])
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
