from __future__ import annotations

import re


class AnswerParser:
    SYMBOLS = {
        "中国神华": "601088.SH",
        "神华": "601088.SH",
        "工商银行": "601398.SH",
        "建设银行": "601939.SH",
        "农业银行": "601288.SH",
        "红利ETF": "510880.SH",
    }

    def parse(self, text: str) -> dict:
        fields: dict = {}
        lowered = text.lower()
        symbols = [symbol for name, symbol in self.SYMBOLS.items() if name in text]
        if symbols:
            fields["symbols"] = list(dict.fromkeys(symbols))
        if "周线" in text or "1w" in lowered or "weekly" in lowered:
            fields.setdefault("timeframes", []).append("1w")
        if "1小时" in text or "1h" in lowered or "60分钟" in text:
            fields.setdefault("timeframes", []).append("1h")
        if "30分钟" in text or "30m" in lowered or "30min" in lowered:
            fields.setdefault("timeframes", []).append("30m")
        if "10分钟" in text or "10m" in lowered or "10min" in lowered:
            fields.setdefault("timeframes", []).append("10m")
        if "5分钟" in text or "5m" in lowered or "5min" in lowered:
            fields.setdefault("timeframes", []).append("5m")
        if "日线" in text or "1d" in lowered:
            fields.setdefault("timeframes", []).append("1d")

        if "网格" in text:
            fields["strategy_pattern"] = "grid"
        elif "轮动" in text or "切换" in text:
            fields["strategy_pattern"] = "rotation"
        elif "选股" in text or "高股息" in text or "低波动" in text or "因子" in text:
            fields["strategy_pattern"] = "stock_selection"
        elif "组合" in text or "再平衡" in text:
            fields["strategy_pattern"] = "portfolio"
        elif "配对" in text or "套利" in text:
            fields["strategy_pattern"] = "pair_trading"
            fields["blocker"] = "A股第一版不支持裸卖空，配对交易只作为 BLOCKER。"
        elif "事件" in text or "公告" in text or "财报" in text:
            fields["strategy_pattern"] = "event_driven"
            fields["blocker"] = "事件驱动需要稳定事件数据源，第一版只作为 BLOCKER。"
        elif any(x in text for x in ["跌多了买", "涨回去卖", "回撤", "低吸", "布林", "波段"]):
            fields["strategy_pattern"] = "swing"
        elif any(x in text for x in ["均线", "趋势", "突破", "择时", "MACD"]):
            fields["strategy_pattern"] = "timing"

        if "布林" in text or "下轨" in text:
            fields["entry_logic"] = "BollLowerEntry"
        elif "回撤" in text or "跌多了买" in text:
            fields["entry_logic"] = "NEEDS_ENTRY_CLARIFICATION"
        elif "均线偏离" in text:
            fields["entry_logic"] = "MADeviationEntry"
        elif "ATR" in text.upper() or "超跌" in text:
            fields["entry_logic"] = "ATROversoldEntry"
        elif "突破" in text:
            fields["entry_logic"] = "BreakoutEntry"

        if "中轨" in text or "涨回去卖" in text or "涨回" in text:
            fields["exit_logic"] = "BollMiddleExit"
        if "止盈" in text:
            fields["take_profit_required"] = True
        if "止损" in text:
            fields["stop_loss_required"] = True
        if "移动止盈" in text:
            fields["trailing_stop_required"] = True
        if "持有" in text and "天" in text:
            fields["holding_days_exit_required"] = True

        if "偏稳健" in text or "稳健" in text or "控制回撤" in text:
            fields["risk_preference"] = "conservative"
            fields.setdefault("risk_control", {})["max_drawdown"] = 0.15
        dd = re.search(r"回撤[^0-9]*(\d+(?:\.\d+)?)%", text)
        if dd:
            fields.setdefault("risk_control", {})["max_drawdown"] = float(dd.group(1)) / 100
        percent = re.search(r"(每次|单次|买入)[^0-9]*(\d+(?:\.\d+)?)%", text)
        if percent:
            fields["sizing_logic"] = "固定比例仓位"
            fields["sizing_percent"] = float(percent.group(2)) / 100
        if "不要太频繁" in text or "交易次数少" in text:
            fields.setdefault("constraints", {})["trade_count_penalty"] = True
            fields.setdefault("constraints", {})["min_holding_period"] = "3 bars"
        if "都可以" in text or "都试" in text or "不确定" in text or "系统都研究" in text:
            fields["multi_route_research"] = True
        if "先研究" in text or "只研究" in text or "不实盘" in text:
            fields["live_intent"] = "research_only"
        if "模拟盘" in text:
            fields["live_intent"] = "paper"
        if "QMT" in text.upper() or "实盘" in text or "真实交易" in text:
            fields["live_intent"] = "future_qmt"
            fields["qmt_safety_note"] = "未来 QMT / 实盘必须通过 dry_run、pretrade-check、审计 VALID 和二次确认。"
        if "前复权" in text:
            fields["adjust"] = "point_in_time_qfq"
        elif "后复权" in text:
            fields["adjust"] = "hfq"
            fields["adjust_warning"] = "hfq 有未来函数风险，不适合作为可信实盘研究依据。"
        elif "qfq" in lowered:
            fields["adjust"] = "qfq"
            fields["adjust_warning"] = "普通 qfq 可能偷看未来分红送转信息。"
        elif "不复权" in text or "raw" in lowered:
            fields["adjust"] = "raw"

        grid = re.search(r"跌(\d+(?:\.\d+)?)%.*涨(\d+(?:\.\d+)?)%", text)
        if grid:
            fields["grid"] = {"buy_step": float(grid.group(1)) / 100, "sell_step": float(grid.group(2)) / 100}
        return fields
