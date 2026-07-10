from __future__ import annotations

from pathlib import Path


def write_audit_report(path: str | Path, status: str, future_report: dict, trade_report: dict, performance: dict) -> None:
    allow_paper = status == "VALID"
    allow_live = False
    lines = [
        "# Audit Report",
        "",
        f"状态：{status}",
        f"未来函数检查：{future_report.get('status')}",
        f"交易规则检查：{trade_report.get('status')}",
        f"是否允许进入模拟盘：{allow_paper}",
        f"是否允许进入实盘：{allow_live}",
        "",
        "## Performance",
        f"- 初始资金：{performance.get('initial_cash')}",
        f"- 最终资金：{performance.get('final_equity')}",
        f"- 总收益：{performance.get('total_return')}",
        f"- 年化收益：{performance.get('annual_return')}",
        f"- 最大回撤：{performance.get('max_drawdown')}",
        f"- 胜率：{performance.get('win_rate')}",
        f"- 盈亏比：{performance.get('profit_loss_ratio')}",
        f"- 交易次数：{performance.get('trade_count')}",
        f"- 手续费合计：{performance.get('total_fee')}",
        f"- 印花税合计：{performance.get('total_stamp_tax')}",
        "",
        "## Findings",
    ]
    findings = list(future_report.get("findings", [])) + list(trade_report.get("findings", []))
    if findings:
        for item in findings:
            lines.append(f"- [{item.get('severity')}] {item.get('message')}")
    else:
        lines.append("- 未发现严重问题。")
    lines.extend(["", "风险提示：审计 VALID 只代表通过本系统规则检查，不代表策略未来盈利。"])
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
