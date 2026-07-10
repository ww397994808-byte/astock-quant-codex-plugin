# Backtest Template Design

## 为什么不能只有一个万能回测模板

不同策略范式的研究对象和状态机不同。择时策略关注入场/出场信号，波段策略关注买点、卖点、止损、止盈和持仓周期，网格策略关注价格层级和分批仓位，选股策略关注股票池、因子、排序和调仓日。如果用一个万能模板承载所有逻辑，最终会把策略状态、组合调仓、网格层级、事件窗口和配对腿全部塞进一个回测循环，导致规则难审计、策略难扩展、实盘前检查难复用。

本项目采用“统一执行层 + 分离策略模板”的结构。

## 各策略范式的回测流程差异

| 模板 | 关键状态 | 输出 |
|---|---|---|
| timing_template | 指标、入场/出场信号 | OrderIntent |
| swing_template | 入场区间、持仓状态、止损止盈、时间退出 | OrderIntent |
| grid_template | 网格基准价、层级、每层仓位 | OrderIntent |
| stock_selection_template | 股票池、因子、排名、top_n | RebalancePlan |
| rotation_template | 资产池评分、top_k、切换判断 | RebalancePlan |
| portfolio_rebalance_template | 目标权重、偏离、调仓频率 | RebalancePlan |
| pair_trading_template | 价差、z-score、对冲比例 | OrderIntent pair |
| event_driven_template | 事件日期、买入窗口、退出窗口 | OrderIntent |

## 哪些统一，哪些分离

统一部分：

- `ExecutionEngine`
- `MarketRules`
- `FeeCalculator`
- `Portfolio`
- `RiskManager`
- `AuditSystem`
- `orders.csv` / `trades.csv` / `positions.csv` / `equity_curve.csv`
- `signal_time` / `execute_time` 审计

分离部分：

- 策略范式状态机
- 指标和信号生成方式
- 网格层级管理
- 股票池排序与 RebalancePlan
- 轮动切换规则
- 配对交易 z-score 与对冲比例
- 事件窗口逻辑

## 各模板如何统一到 ExecutionEngine

模板只允许输出：

- `OrderIntent`
- `RebalancePlan`

`OrderIntent` 会转换为 `Signal`，再由 `ExecutionEngine.signal_to_order()` 转换为订单，最后由 `ExecutionEngine.execute()` 做撮合。模板不能直接修改 `Portfolio`，不能直接下单，不能绕过 T+1、涨跌停、停牌、100 股、费用和现金持仓检查。

`RebalancePlan` 会转换为一组 `OrderIntent`，再进入同一执行层。

## 如何新增一种回测模板

1. 在 `backtest_templates/` 新增模板类，继承 `BaseBacktestTemplate`。
2. 实现 `create_intents(index, history_data, portfolio)`。
3. 只返回 `OrderIntent` 或 `RebalancePlan` 转换后的意图。
4. 不直接调用 `portfolio.cash -= ...`、`portfolio.positions.buy()` 或 broker。
5. 在 `template_registry.py` 绑定策略到模板。
6. 补测试，确认生成 artifacts 和 audit_report。

## 如何从开源项目模块化吸收

吸收开源项目时按模板维度做局部吸收，不把外部框架整体塞进本项目：

- RQAlpha：账户、撮合、多标的、调仓机制，优先映射到选股、轮动、组合调仓。
- vn.py：事件驱动、Gateway/Broker、订单成交持仓对象，优先映射到 execution、qmt、paper/live。
- vnpy_qmt：QMT Gateway 和 miniQMT 连接结构，只参考 qmt_adapter/qmt_broker。
- QMT-MCP：Agent/MCP 调用结构，只参考 agent、skills、task layer。
- QuantDinger：AI 研究闭环、paper/live workflow、monitoring，只参考 research_agent、reporting。
- VectorBT：批量参数矩阵、向量化实验，只参考 optimizer。
- Backtesting.py / Backtrader：简单指标/信号表达，只参考 timing 和 swing 模板。

