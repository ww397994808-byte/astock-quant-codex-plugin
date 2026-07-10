from __future__ import annotations

import json
from pathlib import Path

from core.result import TaskResult
from core.run_manager import RunManager


class ExplainReportService:
    def run(self, run_id: str) -> TaskResult:
        run_dir = RunManager().resolve_run_dir(run_id)
        lines = ["# Explain Report", ""]
        audit = run_dir / "audit_report.md"
        metrics = run_dir / "metrics_report.md"
        final = run_dir / "final_research_report.md"
        if audit.exists():
            text = audit.read_text(encoding="utf-8")
            lines.append("## 审计解释")
            lines.append("这部分告诉你策略有没有违反未来函数、A股交易规则或实盘安全边界。看到 INVALID 就不要进入模拟盘或实盘。")
            lines.append("当前报告状态：" + ("INVALID" if "INVALID" in text[:200] else "VALID"))
        if metrics.exists():
            lines.append("")
            lines.append("## 指标解释")
            text = metrics.read_text(encoding="utf-8")
            if "Calmar" in text:
                lines.append("Calmar 表示每承担 1 单位最大回撤，大约换来多少单位收益；数值越高，风险收益越划算。")
            if "Max Drawdown" in text:
                lines.append("Max Drawdown 是历史最大回撤，可以理解为从高点跌到低点时账户最难受的一段。")
            if "Monthly Win Rate" in text:
                lines.append("Monthly Win Rate 表示盈利月份占比，用来观察策略是否只靠少数月份赚钱。")
        orders = run_dir / "orders.csv"
        if orders.exists():
            lines.append("")
            lines.append("## 日内与复权解释")
            text = orders.read_text(encoding="utf-8")
            if "execute_datetime" in text:
                lines.append("本次订单记录包含 signal_datetime 和 execute_datetime，用来确认信号与成交没有发生在同一根 K 线。")
        dq = run_dir / "data_quality_report.md"
        if dq.exists():
            lines.append("数据质量报告会检查非交易时间、午休 bar、缺失 bar、重复 datetime 和异常跳变。")
        lines.append("普通 qfq/前复权可能把未来分红送转信息提前反映到历史价格里，因此可信研究应优先使用 raw 或 point_in_time_qfq。")
        if final.exists():
            lines.append("")
            lines.append("## 研究报告解释")
            lines.append("Research Agent 已把自然语言方向拆成研究计划、策略变体、样本内/样本外实验和下一轮建议。")
        out = run_dir / "explain_report.md"
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return TaskResult("VALID", "解释报告已生成", run_id=run_dir.name, report_path=str(out))
