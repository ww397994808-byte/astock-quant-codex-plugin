# Template Blockers

## 已可用于第一版研究的模板

### timing_template

状态：可用。

适用：MA、布林择时、MACD、趋势突破等单标的择时研究。  
边界：只生成 `OrderIntent`，最终必须进入 `ExecutionEngine`。不直接修改现金、持仓或调用 broker。

### swing_template

状态：可用。

适用：波段低吸、回撤买入、反弹卖出、止损止盈、持有 N 天退出。  
边界：当前支持持仓状态和最大持仓周期扩展，复杂移动止盈仍需在策略组件或模板参数中继续增强。

### grid_template

状态：可用于单标的网格研究。

已实现：

- `grid_levels`
- 每层 `filled` 状态
- 每层目标仓位
- 下穿买入
- 上穿卖出
- `grid_trades` 网格成交记录

边界：

- 第一版仍用统一 `ExecutionEngine` 在下一根 K 线开盘撮合，不做盘中逐 tick 网格。
- 多标的网格需要后续扩展 Portfolio 多标的市值统计。

### stock_selection_template

状态：可用于选股调仓计划研究。

已实现：

- `universe`
- `factor_table`
- ranking
- `top_n`
- `rebalance_frequency`
- `target_weights`
- `RebalancePlan`

边界：第一版 RebalancePlan 已能生成订单意图，但多标的组合回测的净值和持仓统计仍需进一步增强。

### rotation_template

状态：可用于轮动调仓计划研究。

已实现：

- `asset_pool`
- `score_rules`
- `top_k`
- `switch_threshold`
- `rebalance_frequency`
- `RebalancePlan`

边界：第一版适合 ETF/行业/主题强弱评分研究，真实多资产执行统计仍需后续扩展。

### portfolio_rebalance_template

状态：可用于组合目标权重调仓计划研究。

已实现：

- `target_weights`
- `drift_threshold`
- `rebalance_frequency`
- `cash_buffer`
- `RebalancePlan`

边界：第一版单标的执行链路已接通；完整多标的 Portfolio 市值、权重漂移和调仓成本拆解需要 V3。

## 明确 BLOCKER 的模板

### pair_trading_template

状态：骨架，不可作为真实市场中性配对交易。

BLOCKER：

- A股第一版不支持裸卖空。
- 第一版不支持融资融券。
- 因此不能实现真正市场中性 pair trading。
- 当前只能用于做多强弱轮动、A/H 择强、价差观察或未来扩展研究。

### event_driven_template

状态：骨架，需要事件数据源。

BLOCKER：

- 需要稳定事件数据源。
- 需要事件日期、事件类型、公告/财报/分红字段。
- 需要可复核来源和事件修订处理。
- 没有事件数据源时，只能验证事件窗口逻辑，不能形成可商业交付的事件策略。

## 统一强制约束

所有模板必须：

- 输出 `OrderIntent` 或 `RebalancePlan`。
- 最终进入 `ExecutionEngine`。
- 不能直接修改 `Portfolio`。
- 不能直接调用 broker 或 `place_order`。
- 不能绕过 T+1、涨跌停、停牌、100 股、费用、现金/持仓检查。
- 必须生成标准 artifacts。
- 必须生成 `audit_report.md`。

