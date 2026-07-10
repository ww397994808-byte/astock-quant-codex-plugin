# Strategy Intake Report

- 原始想法：中国神华 周线 跌多了买 涨回去卖 控制回撤 不要太频繁交易
- 完整度评分：90
- 是否可进入研究：True
- 识别范式：swing
- 策略原型：swing
- 标的：601088.SH
- 周期：1w
- 复权：point_in_time_qfq

## 风险与目标
- risk_control: {'max_drawdown': 0.15}
- objective: {'primary': 'calmar', 'trade_frequency': 'low'}
