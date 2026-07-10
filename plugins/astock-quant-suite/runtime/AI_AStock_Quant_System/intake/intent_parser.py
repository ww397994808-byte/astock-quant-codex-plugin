from __future__ import annotations

import re

from intake.strategy_requirement import StrategyRequirement
from strategy_patterns.classifier import StrategyArchetypeClassifier


class IntentParser:
    SYMBOLS = {
        "中国神华": "601088.SH",
        "神华": "601088.SH",
        "建设银行": "601939.SH",
        "农业银行": "601288.SH",
        "工商银行": "601398.SH",
        "红利ETF": "510880.SH",
    }

    def parse(self, idea: str) -> StrategyRequirement:
        req = StrategyRequirement(original_idea=idea)
        req.symbols = self._symbols(idea)
        req.asset_type = "ETF" if "ETF" in idea.upper() else "stock"
        req.timeframe = self._timeframe(idea)
        req.strategy_pattern = self._pattern(idea)
        req.archetype = StrategyArchetypeClassifier().classify(req.strategy_pattern, idea).archetype.value
        req.entry_logic = self._entry(idea)
        req.exit_logic = self._exit(idea)
        req.sizing_logic = self._sizing(idea)
        req.risk_control = self._risk(idea)
        req.objective = self._objective(idea)
        req.constraints = self._constraints(idea)
        req.data_adjustment = self._adjustment(idea)
        if "实盘" in idea or "QMT" in idea.upper():
            req.live_intent = "qmt"
            req.qmt_safety_note = "用户有实盘意图：必须通过 QMT dry_run、pre-trade check、审计 VALID 和二次确认。"
        return req

    def _symbols(self, idea: str) -> list[str]:
        found = []
        for name, symbol in self.SYMBOLS.items():
            if name in idea and symbol not in found:
                found.append(symbol)
        if "煤炭" in idea and "银行" in idea and "电力" in idea:
            found.extend(["煤炭", "银行", "电力"])
        return found

    def _timeframe(self, idea: str) -> str | None:
        if any(x in idea for x in ["1小时", "1h", "60分钟"]):
            return "1h"
        if any(x in idea for x in ["10分钟", "10min"]):
            return "10m"
        if any(x.lower() in idea.lower() for x in ["周线", "1w", "weekly"]):
            return "1w"
        if "日线" in idea:
            return "1d"
        return None

    def _pattern(self, idea: str) -> str | None:
        if any(x in idea for x in ["网格", "分层"]):
            return "grid"
        if any(x in idea for x in ["轮动", "切换", "强弱"]):
            return "rotation"
        if any(x in idea for x in ["选股", "高股息", "低波动", "因子", "TopN"]):
            return "stock_selection"
        if any(x in idea for x in ["组合", "再平衡", "等权", "权重"]):
            return "portfolio"
        if any(x in idea for x in ["跌多了买", "涨回去卖", "回撤", "波段", "低吸", "布林"]):
            return "swing"
        if any(x in idea for x in ["均线", "趋势", "突破", "MACD", "择时"]):
            return "timing"
        return None

    def _entry(self, idea: str) -> str | None:
        if "布林" in idea or "下轨" in idea:
            return "布林下轨或低吸入场"
        if "跌多了买" in idea or "回撤" in idea:
            return "回撤/跌多了买入"
        if "突破" in idea:
            return "突破买入"
        if "均线" in idea:
            return "均线信号买入"
        return None

    def _exit(self, idea: str) -> str | None:
        if "涨回去卖" in idea or "中轨" in idea:
            return "涨回均值/中轨卖出"
        if "止盈" in idea:
            return "止盈卖出"
        if "止损" in idea:
            return "止损卖出"
        return None

    def _sizing(self, idea: str) -> str | None:
        if "分批" in idea or "加仓" in idea:
            return "分批仓位"
        if "%" in idea or "比例" in idea:
            return "固定比例仓位"
        return None

    def _risk(self, idea: str) -> dict:
        risk = {}
        if "稳健" in idea or "控制回撤" in idea:
            risk["max_drawdown"] = 0.15
        drawdown_match = re.search(r"回撤[^0-9]{0,8}(\d+(?:\.\d+)?)\s*%", idea)
        if drawdown_match:
            risk["max_drawdown"] = float(drawdown_match.group(1)) / 100
        if "止损" in idea:
            risk["stop_loss_required"] = True
        if "单日亏损" in idea:
            risk["daily_loss_limit_required"] = True
        return risk

    def _objective(self, idea: str) -> dict:
        obj = {"primary": "calmar"}
        if "年化" in idea:
            obj["target_annual_return"] = [0.15, 0.25]
        annual_match = re.search(r"年化[^0-9]{0,8}(\d+(?:\.\d+)?)\s*%", idea)
        if annual_match:
            obj["min_annual_return"] = float(annual_match.group(1)) / 100
        if "胜率" in idea:
            obj["secondary"] = "win_rate"
        if "交易次数少" in idea or "不要太频繁" in idea:
            obj["trade_frequency"] = "low"
        return obj

    def _constraints(self, idea: str) -> dict:
        constraints = {"min_trades": 10, "max_experiments": 300}
        if "不要太频繁" in idea or "交易次数少" in idea:
            constraints["min_holding_period"] = "3 bars"
            constraints["trade_count_penalty"] = True
        return constraints

    def _adjustment(self, idea: str) -> str:
        if "不复权" in idea or "raw" in idea.lower():
            return "raw"
        if "前复权" in idea:
            return "point_in_time_qfq"
        if "后复权" in idea:
            return "hfq"
        return "point_in_time_qfq"
