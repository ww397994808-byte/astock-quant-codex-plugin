from __future__ import annotations


class QuestionTree:
    QUESTIONS = {
        "symbol": "你想研究哪只股票、ETF，还是一组股票？例如：中国神华、红利ETF。",
        "pattern": "你更像想做哪类策略：A 波段低吸，B 择时趋势，C 网格，D 轮动，E 选股，F 组合再平衡？",
        "entry_swing": "你说的“跌多了”更接近：A 布林下轨，B N日高点回撤，C 均线偏离，D RSI超卖，E ATR超跌，F 不确定让系统都研究？",
        "grid_step": "网格策略要继续明确：网格间距是固定价格还是百分比？跌多少加仓、涨多少减仓？最大仓位多少？是否允许连续加仓？",
        "rotation_pool": "轮动策略要继续明确：资产池是什么？根据什么评分？多久调仓？买前几名？切换阈值是多少？",
        "selection_factor": "选股策略要继续明确：股票池是什么？使用哪些因子？选 top_n 多少只？多久调仓？",
        "portfolio_weight": "组合再平衡要继续明确：目标权重是什么？多久再平衡？偏离多少才调仓？",
        "timeframe": "你想用什么周期：A 周线，B 日线，C 1小时，D 30分钟，E 10分钟，F 多周期都研究？",
        "exit": "什么情况下卖出：A 回到中轨，B 固定止盈，C 固定止损，D 移动止盈，E 持有N天，F 不确定让系统都研究？",
        "sizing": "每次买多少：固定金额、固定比例、分批加仓、等权，还是波动率调整？",
        "risk": "你能接受最大回撤多少？是否需要止损、冷却期、最少持有期或单票最大仓位？",
        "objective": "你更重视：A 年化收益，B 最大回撤，C Calmar，D 胜率，E 交易次数少，F 样本外表现？",
        "adjust": "复权方式建议 raw 或 point_in_time_qfq。你想用哪一种？普通 qfq/hfq 有未来函数风险。",
        "live_intent": "这次只是研究、想模拟盘，还是未来想接 QMT？真实交易默认关闭。",
        "confirm": "请确认摘要是否正确。确认后才允许进入 Research Agent。",
    }

    def next_questions(self, fields: dict) -> list[tuple[str, str]]:
        questions: list[tuple[str, str]] = []
        pattern = fields.get("strategy_pattern")
        if not fields.get("symbols"):
            questions.append(("symbol", self.QUESTIONS["symbol"]))
        if not pattern:
            questions.append(("pattern", self.QUESTIONS["pattern"]))
        elif pattern == "grid":
            if not fields.get("grid"):
                questions.append(("grid_step", self.QUESTIONS["grid_step"]))
        elif pattern == "rotation":
            questions.append(("rotation_pool", self.QUESTIONS["rotation_pool"]))
        elif pattern == "stock_selection":
            questions.append(("selection_factor", self.QUESTIONS["selection_factor"]))
        elif pattern == "portfolio":
            questions.append(("portfolio_weight", self.QUESTIONS["portfolio_weight"]))
        elif pattern == "swing" and fields.get("entry_logic") == "NEEDS_ENTRY_CLARIFICATION":
            questions.append(("entry_swing", self.QUESTIONS["entry_swing"]))

        if not fields.get("timeframes"):
            questions.append(("timeframe", self.QUESTIONS["timeframe"]))
        if pattern not in {"grid", "rotation", "stock_selection", "portfolio"} and not fields.get("exit_logic"):
            questions.append(("exit", self.QUESTIONS["exit"]))
        if not fields.get("sizing_logic") and pattern not in {"rotation", "stock_selection"}:
            questions.append(("sizing", self.QUESTIONS["sizing"]))
        if not fields.get("risk_control"):
            questions.append(("risk", self.QUESTIONS["risk"]))
        if not fields.get("objective"):
            questions.append(("objective", self.QUESTIONS["objective"]))
        if not fields.get("adjust"):
            questions.append(("adjust", self.QUESTIONS["adjust"]))
        if not fields.get("live_intent"):
            questions.append(("live_intent", self.QUESTIONS["live_intent"]))
        questions.append(("confirm", self.QUESTIONS["confirm"]))
        return questions
