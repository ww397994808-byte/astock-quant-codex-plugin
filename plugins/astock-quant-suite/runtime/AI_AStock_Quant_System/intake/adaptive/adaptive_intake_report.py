from __future__ import annotations

from pathlib import Path

from intake.adaptive.interview_state import InterviewState
from intake.strategy_requirement import StrategyRequirement


class AdaptiveIntakeReportWriter:
    def write(self, output_dir: str | Path, state: InterviewState, req: StrategyRequirement, questions: list[tuple[str, str]]) -> None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "unanswered_questions.md").write_text(
            "# Unanswered Questions\n\n" + "\n".join(f"- {q}" for _, q in questions if _ != "confirm") + "\n",
            encoding="utf-8",
        )
        (output_dir / "assumptions.md").write_text(
            "# Assumptions\n\n" + "\n".join(f"- {item}" for item in state.assumptions) + "\n",
            encoding="utf-8",
        )
        (output_dir / "confirmation_summary.md").write_text(self.confirmation_summary(req, state), encoding="utf-8")
        lines = [
            "# Adaptive Intake Report",
            "",
            f"- completeness_score: {state.completeness_score}",
            f"- research_ready: {state.research_ready}",
            f"- user_confirmed: {state.user_confirmed}",
            f"- current_question_id: {state.current_question_id}",
            "",
            "## Next Questions",
        ]
        lines.extend(f"- {question}" for _, question in questions[:5])
        (output_dir / "adaptive_intake_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def confirmation_summary(self, req: StrategyRequirement, state: InterviewState) -> str:
        return "\n".join(
            [
                "# Confirmation Summary",
                "",
                "请确认：",
                f"1. 标的：{self._symbols(req.symbols)}",
                f"2. 策略类型：{self._pattern(req.strategy_pattern)}",
                f"3. 买入条件：{self._entry(req.entry_logic)}",
                f"4. 卖出条件：{self._exit(req.exit_logic)}",
                f"5. 使用周期：{self._timeframe(req.timeframe)}",
                f"6. 每次买多少：{self._sizing(req.sizing_logic, state)}",
                f"7. 风控要求：{self._risk(req.risk_control)}",
                f"8. 研究目标：{self._objective(req.objective)}",
                f"9. 价格处理方式：{self._adjust(req.data_adjustment)}",
                f"10. 实盘意图：{self._live_intent(state.inferred_fields.get('live_intent'))}",
                "",
                f"是否已经可以进入研究：{'可以，但仍建议你先人工确认' if state.research_ready else '还不可以，需要先补充上面缺失的信息'}",
                "说明：在你确认前，系统不会自动进入 Research Agent。",
            ]
        ) + "\n"

    def _symbols(self, symbols: list[str]) -> str:
        if not symbols:
            return "还需要你补充"
        name_map = {"601088.SH": "中国神华（601088.SH）", "510880.SH": "红利ETF（510880.SH）"}
        return "、".join(name_map.get(symbol, symbol) for symbol in symbols)

    def _pattern(self, value: str | None) -> str:
        return {
            "swing": "波段低吸/反弹卖出",
            "timing": "择时/趋势信号",
            "grid": "网格分批买卖",
            "rotation": "多资产轮动",
            "stock_selection": "因子选股",
            "portfolio": "组合再平衡",
            "pair_trading": "配对交易（当前 A股版本暂不支持裸卖空）",
            "event_driven": "事件驱动（需要额外事件数据源）",
        }.get(value or "", "还需要你补充")

    def _entry(self, value: str | None) -> str:
        return {
            "NEEDS_ENTRY_CLARIFICATION": "还需要你补充：跌多了具体指布林下轨、N日回撤、均线偏离、RSI超卖，还是让系统都研究",
            "BollLowerEntry": "价格跌到布林下轨附近时考虑买入",
            "DrawdownEntry": "距离近期高点回撤达到一定幅度时考虑买入",
            "MADeviationEntry": "价格低于均线一定比例时考虑买入",
            "ATROversoldEntry": "出现 ATR 超跌时考虑买入",
            "BreakoutEntry": "价格突破关键位置时考虑买入",
            "多路线研究：布林下轨 / N日回撤 / 均线偏离 / ATR超跌": "不确定具体买点，让系统同时研究多种低吸方式",
        }.get(value or "", "还需要你补充")

    def _exit(self, value: str | None) -> str:
        return {
            "BollMiddleExit": "涨回布林中轨附近时考虑卖出",
            "FixedTakeProfitExit": "达到固定止盈时卖出",
            "FixedStopLossExit": "触发固定止损时卖出",
            "TrailingStopExit": "盈利后回撤达到阈值时移动止盈",
            "HoldingDaysExit": "持有满指定时间后退出",
        }.get(value or "", "还需要你补充")

    def _timeframe(self, value: str | None) -> str:
        return {
            "1w": "周线",
            "1d": "日线",
            "1h": "1小时",
            "30m": "30分钟",
            "10m": "10分钟",
            "5m": "5分钟",
        }.get(value or "", "还需要你补充")

    def _sizing(self, value: str | None, state: InterviewState) -> str:
        percent = state.inferred_fields.get("sizing_percent")
        if percent:
            return f"每次买入约 {percent:.0%} 仓位"
        return value or "还需要你补充"

    def _risk(self, value: dict) -> str:
        if not value:
            return "还需要你补充"
        parts = []
        if "max_drawdown" in value:
            parts.append(f"最大可接受回撤：{float(value['max_drawdown']):.0%}")
        if value.get("stop_loss_required"):
            parts.append("需要止损")
        return "；".join(parts) if parts else "已填写，但需要进一步确认"

    def _objective(self, value: dict) -> str:
        if not value:
            return "还需要你补充"
        parts = []
        if value.get("primary") == "calmar":
            parts.append("优先看风险收益比（Calmar）")
        if value.get("trade_frequency") == "low":
            parts.append("希望交易次数少一些")
        return "；".join(parts) if parts else "已填写，但需要进一步确认"

    def _adjust(self, value: str) -> str:
        return {
            "raw": "不复权",
            "point_in_time_qfq": "按当时已知信息做前复权，尽量避免偷看未来",
            "qfq": "普通前复权（有未来函数风险）",
            "hfq": "后复权（有未来函数风险）",
        }.get(value, value or "默认使用 point_in_time_qfq")

    def _live_intent(self, value: str | None) -> str:
        return {
            "research_only": "只是研究，不实盘",
            "paper": "未来可能先做模拟盘",
            "future_qmt": "未来可能接 QMT；真实交易默认关闭，必须单独检查",
        }.get(value or "", "还需要你补充")
