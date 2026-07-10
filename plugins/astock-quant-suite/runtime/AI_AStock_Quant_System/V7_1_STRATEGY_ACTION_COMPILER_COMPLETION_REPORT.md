# V7.1 Strategy Action Compiler Completion Report

## 当前完成内容

V7.1 已新增 Strategy Action Compiler，把 V7 中的优化动作从“报告建议 / DSL 修改”推进到“可编译、可回测的策略组件”。

当前链路已经升级为：

OptimizationDirector / Deep Diagnosis -> ActionCompiler -> Strategy DSL -> DSLToStrategy -> ComponentStrategy -> Backtest Template -> ExecutionEngine -> Audit / Readiness

## 为什么优化动作必须编译成可执行组件

如果 `replace_entry_rule`、`add_trailing_stop`、`add_cooldown` 等动作只写进报告，Research Loop 实际上没有验证这些动作。V7.1 让每个支持的 action 都生成新的 Strategy DSL，并由 DSLToStrategy 编译成真正的 Strategy 对象进入回测。

## 新增目录和模块

- strategy_compiler/action_compiler.py
- strategy_compiler/dsl_to_strategy.py
- strategy_compiler/component_registry.py
- strategy_compiler/component_factory.py
- strategy_compiler/compile_report.py
- strategy_compiler/compiler_errors.py

新增策略组件：

- strategies/components/entry_rules/
- strategies/components/exit_rules/
- strategies/components/filters/
- strategies/components/sizing_rules/

## 已支持的 action

已支持 V7.1 要求的主要动作：

- add_stop_loss
- tighten_stop_loss
- add_trailing_stop
- add_holding_days
- add_cooldown
- add_trend_filter
- add_volatility_filter
- reduce_position_size
- replace_entry_rule
- add_alternative_entry
- test_drawdown_entry
- test_boll_entry
- test_ma_deviation_entry
- test_atr_oversold_entry
- replace_exit_rule
- test_fixed_take_profit
- test_trailing_stop
- test_boll_middle_exit
- test_holding_days_exit

同时兼容 V7 遗留动作：

- widen_entry_condition
- reduce_threshold
- adjust_take_profit
- test_alternative_exit

## DSLToStrategy 如何工作

DSLToStrategy 会读取 DSL 中的 entry、exit、filters、sizing 和 pattern，通过 ComponentFactory 实例化组件，并生成 `ComponentStrategy`。

`ComponentStrategy` 只生成 Signal，不直接下单。因此所有交易仍然经过：

- Backtest Template
- ExecutionEngine
- T+1
- 涨跌停
- 停牌
- 手数
- 费用
- Audit
- Readiness

## expanded experiments 是否真的回测

是。

正式验收目录：

```text
reports/optimize_loop_20260621_232753
```

该目录中每轮 iteration 都包含：

- compiled_strategy.json
- compile_report.md
- component_list.md
- orders.csv
- trade_rule_report.md
- readiness_report.md

正式验收中也生成了：

- deep_diagnosis_round_1.md
- deep_diagnosis_round_2.md
- expanded_experiment_plan_round_1.md
- expanded_experiment_plan_round_2.md

说明 expanded experiments 已进入编译和回测链路，而不是只停留在报告。

## 编译失败处理

如果 DSL 中出现不存在的组件，系统会抛出 StrategyCompileError，生成 compile_error，并把该实验记录为 INVALID。compile_error 不进入 final_candidates。

## 当前仍属于计划层的动作

以下方向仍需要后续批量实验调度增强：

- random_search
- coarse_grid_restart
- cross_symbol_validate
- test_similar_assets
- test_etf_proxy
- regime_split_analysis
- bull_bear_sideways_split
- volatility_regime_split
- test_timeframe_1w 等跨周期批量研究

这些动作目前可进入 expanded experiment plan，但还没有完整批量调度执行器。

## 测试结果

新增 V7.1 测试：36 个。

全量测试结果：

```text
276 passed in 45.07s
```

## 验收命令

已通过：

```bash
python3 cli.py optimize-loop --idea "中国神华1小时布林低吸波段，控制回撤，不要太频繁交易" --symbol 601088.SH --timeframe 1h --adjust point_in_time_qfq --max-iterations 8
```

已通过：

```bash
python3 -m pytest tests/
```

## 下一阶段建议

下一阶段应做 V7.2：Expanded Experiment Scheduler，把 Deep Diagnosis 中的 random search、跨标的、跨周期、regime split 从计划层推进到批量实验执行层。
