# Strategy Action Compiler

## 为什么 V7 优化动作必须编译成可执行组件

V7 的 OptimizationDirector 和 Deep Diagnosis 能提出很多合理动作，例如替换入场、增加移动止盈、加入冷却过滤、降低仓位。但如果这些动作只停留在报告或 DSL，expanded experiments 就没有真正被验证。V7.1 的目标是把动作落到策略组件层，让每一轮修改都能进入真实回测。

## ActionCompiler 如何把优化动作转成 DSL

ActionCompiler 接收当前 Strategy DSL 和 action，输出新的 Strategy DSL。例如：

- `test_atr_oversold_entry` -> `entry.type = ATROversoldEntry`
- `test_ma_deviation_entry` -> `entry.type = MADeviationEntry`
- `add_trailing_stop` -> 增加 `TrailingStopExit`
- `add_cooldown` -> 增加 `CooldownFilter`
- `reduce_position_size` -> 使用 `ReducedPositionSizing`

如果 action 或组件不存在，系统会生成 compile_error，不能静默失败。

## DSLToStrategy 如何把 DSL 转成可回测策略

DSLToStrategy 会读取 DSL 中的：

- entry_rules
- exit_rules
- filters
- sizing_rules
- risk_controls
- strategy pattern

然后通过 ComponentFactory 实例化组件，生成一个 `ComponentStrategy` 对象。该对象仍只输出 Signal，不直接下单。回测模板仍负责把 Signal 转成 OrderIntent，ExecutionEngine 仍负责 A股规则、费用、T+1、涨跌停和审计链路。

## expanded experiments 是否真的被回测

V7.1 已改造 optimize-loop：

OptimizationDirector / Deep Diagnosis -> ActionCompiler -> Strategy DSL -> DSLToStrategy -> Backtest Template -> ExecutionEngine -> Audit / Readiness

每轮 iteration 都会输出：

- compiled_strategy.json
- compile_report.md
- component_list.md

如果编译失败，该轮进入 rejected_candidates，不进入 final_candidates。

## 当前还有哪些 action 只是计划

当前 V7.1 已支持主要 V7/V7.1 动作。仍属于后续增强的方向包括：

- 大规模 random_search 的真实采样执行；
- cross_symbol_validate 的多标的批量回测；
- test_timeframe_1w 等跨周期自动取数和批量调度；
- regime_split_analysis 的分市场状态独立回测。

这些动作会在 Deep Diagnosis 报告中出现，但需要后续批量实验调度层继续增强。
