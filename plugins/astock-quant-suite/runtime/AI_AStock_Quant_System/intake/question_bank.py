from __future__ import annotations


QUESTION_BANK = {
    "symbols": "你想研究哪只股票/ETF/一组股票？例如：中国神华、红利ETF、煤炭银行电力。",
    "strategy_pattern": "你更像是想做：A 跌多了买涨回去卖；B 突破追涨；C 网格；D 轮动；E 选股；F 组合再平衡？",
    "timeframe": "你希望看日线、1小时、10分钟，还是周线？交易频率想高一点还是低一点？",
    "entry_logic": "什么情况下买？跌破指标、回撤比例、布林下轨、均线突破，还是别的？",
    "exit_logic": "什么情况下卖？涨回均线/中轨、目标收益、止损、移动止盈，还是持有固定时间？",
    "sizing_logic": "每次买多少？固定金额、固定比例，还是分批加仓？单只股票最大仓位是多少？",
    "risk_control": "你能接受最大回撤多少？是否需要止损、单日亏损限制，是否允许连续加仓？",
    "objective": "你更重视年化收益、最大回撤、胜率，还是交易次数少？",
    "data_adjustment": "数据使用 raw、point_in_time_qfq，还是普通 qfq？默认建议 raw 或 point_in_time_qfq。",
    "live_intent": "你只是研究、想模拟盘，还是最终想接 QMT 实盘？",
}

