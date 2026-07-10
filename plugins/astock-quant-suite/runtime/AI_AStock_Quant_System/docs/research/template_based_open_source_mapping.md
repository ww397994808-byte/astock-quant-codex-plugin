# Template Based Open Source Mapping

| 策略模板 | 可参考开源项目 | 可吸收模块 | 不可直接复用部分 | 是否建议接入 |
|---|---|---|---|---|
| timing_template | Backtesting.py、Backtrader、RQAlpha | 指标/信号表达、简单策略生命周期、订单意图表达 | GPL/框架内撮合、非 A股规则、直接下单接口 | 建议参考，不直接依赖 |
| swing_template | Backtesting.py、Backtrader、RQAlpha | 持仓状态、止损止盈、时间退出、波段状态机 | 绕过本系统 T+1/涨跌停/费用的撮合逻辑 | 建议参考 |
| grid_template | Backtrader 社区策略、vn.py CTA 思路 | 网格层级、分批成交、层级记录 | 第三方真实下单、非 A股手数规则 | 建议自研为主 |
| stock_selection_template | RQAlpha、Qlib | 股票池、因子、排序、调仓日、目标权重 | 外部数据协议、非本系统审计输出 | 建议二次封装 |
| rotation_template | RQAlpha、Qlib、VectorBT | 资产池评分、top_k、定期切换、参数矩阵 | 直接使用外部回测绩效作为实盘依据 | 建议二次封装 |
| portfolio_rebalance_template | RQAlpha、QuantConnect Lean | 组合权重、再平衡、仓位约束 | 重型框架账户模型、非 A股费用/税费 | 建议参考 |
| pair_trading_template | Qlib、VectorBT、Backtrader | 价差、z-score、参数扫描、对冲比例 | A股第一版不做空、不支持融资融券、外部撮合 | 只参考研究端 |
| event_driven_template | vn.py、RQAlpha、QuantDinger | 事件驱动流程、事件日志、研究到执行闭环 | Agent 直接下单、缺少本系统 pre-trade check 的 live workflow | 建议参考 |
| execution / broker | vn.py、vnpy_qmt、XtQuant 官方接口 | Gateway/Broker、订单成交持仓对象、QMT 连接方式 | 第三方 skill/proxy 作为实盘核心 | 仅官方 XtQuant 可进入核心 |
| optimizer | VectorBT、Qlib、PyBroker | 参数矩阵、Walk Forward、稳定性分析 | Commons Clause 项目作为商业核心依赖、只报告最优参数 | 建议吸收思想 |
| agent / skills | QuantDinger、QMT-MCP | AI 研究闭环、Agent 调用结构、MCP 工具边界 | Prompt 承担交易规则、AI 绕过审计下单 | 只参考入口设计 |

结论：开源项目按策略模板和系统层次做模块化吸收。执行、风控、A股规则、审计、QMT 安全门必须保留为本项目自研核心。

