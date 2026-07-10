# Batch Experiment Scheduler

## 目标

V7.2 把 V7.1 中仍停留在 expanded experiment plan 的研究方向推进为真实批量实验：

- random_search
- cross_timeframe_validation
- cross_symbol_validation
- regime_split_experiments
- parameter_sweep
- component_combination_experiments

## 调度流程

BatchScheduler 接收 Deep Diagnosis / ResearchExpander 生成的扩展动作，拆成 ExperimentJob，然后逐个执行：

1. 生成 Strategy DSL；
2. 调用 ActionCompiler；
3. 调用 DSLToStrategy；
4. 调用 Backtest Template；
5. 经过 ExecutionEngine；
6. 输出 Audit / Readiness；
7. 聚合 batch_results；
8. 回传 Feedback Loop。

## ExperimentJob

ExperimentJob 记录：

- job_id
- parent_iteration
- experiment_type
- symbol
- timeframe
- adjust
- strategy_dsl
- data_path
- regime
- parameters
- status
- result_path
- audit_status
- readiness
- score
- failure_reason

## 批量实验类型

RandomSearchRunner 从 ComponentRegistry 的 parameter_ranges 中采样，支持固定 random_seed，避免生成非正数等非法参数。

CrossTimeframeRunner 当前默认验证 10m、30m、1h、1d。1w 需要后续周线聚合数据层增强后接入。

CrossSymbolRunner 支持主标的和相似标的，例如中国神华可扩展到工商银行、建设银行、红利ETF等。

RegimeSplitRunner 生成 bull、bear、sideways、high_volatility、low_volatility 的独立实验 job。

## 结果聚合

BatchResultAggregator 输出：

- batch_jobs.csv
- batch_results.csv
- batch_summary.md
- best_by_timeframe.csv
- best_by_symbol.csv
- best_by_regime.csv
- failed_jobs.csv

## 如何影响候选评分

CandidateSelector 已接入 batch_summary。跨周期、跨标的、regime 稳定性差会降低候选分数，并写入 final_feedback_loop_report。

## 安全边界

批量实验仍然不绕过：

- T+1
- 涨跌停
- 停牌
- 费用
- FutureLeakChecker
- TradeRuleChecker
- AdjustmentLeakChecker
- Readiness

INVALID job 不进入候选。普通 qfq / hfq 仍不能成为 LIVE_CANDIDATE。
