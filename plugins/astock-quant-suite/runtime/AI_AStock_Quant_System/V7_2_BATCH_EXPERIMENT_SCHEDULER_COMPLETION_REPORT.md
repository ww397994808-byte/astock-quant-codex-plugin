# V7.2 Batch Experiment Scheduler Completion Report

## 当前完成内容

V7.2 已新增 Batch Experiment Scheduler，把 V7.1 中仍停留在 expanded experiment plan 的扩展方向推进为真实批量实验。

当前新增能力：

- random_search
- cross_timeframe_validation
- cross_symbol_validation
- regime_split_experiments
- parameter_sweep / component_combination_experiments

## 新增模块

- experiment_scheduler/batch_scheduler.py
- experiment_scheduler/experiment_job.py
- experiment_scheduler/experiment_queue.py
- experiment_scheduler/random_search_runner.py
- experiment_scheduler/cross_timeframe_runner.py
- experiment_scheduler/cross_symbol_runner.py
- experiment_scheduler/regime_split_runner.py
- experiment_scheduler/batch_result_aggregator.py
- experiment_scheduler/batch_budget_manager.py
- experiment_scheduler/batch_report.py

新增配置：

- config/experiment_scheduler.yaml

新增文档：

- docs/architecture/batch_experiment_scheduler.md

## 调度链路

BatchScheduler 现在可以把 Deep Diagnosis / ResearchExpander 生成的扩展动作拆成 ExperimentJob，并执行：

Strategy DSL -> ActionCompiler -> DSLToStrategy -> Backtest Template -> ExecutionEngine -> Audit / Readiness -> BatchResultAggregator

## 输出文件

每次触发批量实验时，iteration 目录会生成：

- batch_jobs.csv
- batch_results.csv
- batch_summary.md
- best_by_timeframe.csv
- best_by_symbol.csv
- best_by_regime.csv
- failed_jobs.csv

正式验收目录：

```text
reports/optimize_loop_20260621_234848
```

该目录中 iteration_3 和 iteration_4 已生成批量实验结果。

## CandidateSelector 接入

CandidateSelector 已接入 batch_summary。候选评分现在会考虑：

- 主周期表现
- 跨周期稳定性
- 跨标的稳定性
- regime 稳定性
- 审计状态
- readiness
- 数据质量
- 交易次数
- 策略复杂度
- qfq/hfq 风险

跨周期、跨标的或 regime 稳定性差会降权。审计 INVALID 不进入 final_candidates。普通 qfq/hfq 仍不能成为 LIVE_CANDIDATE。

## 安全链路

批量实验仍然经过：

- T+1
- 涨跌停
- 停牌
- 费用
- FutureLeakChecker
- TradeRuleChecker
- AdjustmentLeakChecker
- Readiness

没有绕过原有回测和审计系统。

## 当前限制

- CrossTimeframeRunner 当前默认跑 10m、30m、1h、1d。1w 需要后续周线数据聚合层增强后接入。
- 批量实验当前串行执行，parallel_workers 配置已预留，但未开启并行。
- RegimeSplitRunner 第一版以 regime job 标签方式运行，后续可进一步接入真实市场状态切片数据。
- CrossSymbolRunner 第一版使用内置相似标的列表，后续可接行业/主题/ETF 映射库。

## 测试结果

新增 V7.2 测试：35 个。

全量测试：

```text
311 passed in 59.73s
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

下一步建议进入 V7.3：真实 Regime Data Split + Parallel Batch Execution，把 regime job 从标签实验升级成真实区间切片实验，并按预算开启可控并行。
