# Codex Research Prompt

请基于以下结构化策略需求启动 Research Agent，而不是直接手写一次性回测脚本。

- 原始想法：中国神华 周线 跌多了买 涨回去卖 控制回撤 不要太频繁交易
- 市场：A股
- 标的：601088.SH
- 周期：1w
- 策略范式：swing
- 入场：回撤/跌多了买入
- 出场：涨回均值/中轨卖出
- 仓位：待补充
- 风险：{'max_drawdown': 0.15}
- 目标：{'primary': 'calmar', 'trade_frequency': 'low'}
- 复权：point_in_time_qfq
- 约束：{'min_trades': 10, 'max_experiments': 300, 'min_holding_period': '3 bars', 'trade_count_penalty': True}

要求：
1. 使用 Task Layer / Research Agent。
2. 使用对应 backtest_template。
3. 审计 INVALID 不进入推荐。
4. 不按总收益排序，优先看 Calmar、样本外、回撤、稳定性、交易次数。
5. 如果有 QMT 实盘意图，只能输出安全提醒，不能真实下单。
