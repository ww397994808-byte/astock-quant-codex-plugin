from __future__ import annotations

import json
from pathlib import Path


def write_csv(path: str | Path, rows: list[dict], fieldnames: list[str]) -> None:
    import csv

    path = Path(path)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_json(path: str | Path, data: dict) -> None:
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_research_readme(path: str | Path, summary: dict) -> None:
    lines = [
        "# 本次研究",
        "",
        f"- 策略名称：{summary.get('strategy')}",
        f"- 标的：{summary.get('symbol')}",
        f"- 数据区间：{summary.get('start_date')} 至 {summary.get('end_date')}",
        f"- 初始资金：{summary.get('initial_cash')}",
        f"- 最终资金：{summary.get('final_equity')}",
        f"- 总收益：{summary.get('total_return')}",
        f"- 最大回撤：{summary.get('max_drawdown')}",
        f"- 交易次数：{summary.get('trade_count')}",
        f"- 状态：{summary.get('status')}",
        "",
        "风险提示：历史回测不代表未来收益。审计失败结果不得进入模拟盘或实盘。",
    ]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
