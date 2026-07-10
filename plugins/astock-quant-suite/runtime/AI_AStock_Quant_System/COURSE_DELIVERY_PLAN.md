# Course Delivery Plan

## 第1课：跑通系统

目标：让学生完成 `python3 cli.py course-demo`，看到完整报告目录。

学生学会：CLI、报告目录、run_id、latest。

## 第2课：理解A股交易规则

目标：解释 T+1、涨跌停、停牌、100股、费用。

学生学会：为什么策略不能信号当天成交，为什么审计比收益更重要。

## 第3课：用 Adaptive Intake 规范化策略

目标：把“跌多了买，涨回去卖”变成结构化 StrategyRequirement 和 DSL。

学生学会：小白不能直接回测模糊想法，必须先经过 `intake-chat` 的多轮澄清。旧 `intake --idea` 只作为高级 quick intake。

## 第4课：运行Research Agent

目标：让系统自动识别策略范式，生成 ResearchPlan 和策略变体。

学生学会：研究计划不是回测结果，研究先要定义假设。

## 第5课：理解回测和审计

目标：运行 backtest，并读懂 orders/trades/performance/audit_report。

学生学会：VALID / INVALID、FutureLeak、TradeRule、AdjustmentLeak。

## 第6课：运行optimize-loop

目标：理解回测后反馈优化，不把“无改善”当停止，而是触发 Deep Diagnosis。

学生学会：优化不是找最高收益，而是诊断失败原因。

## 第7课：看懂Readiness

目标：解释 INVALID、RESEARCH_ONLY、PAPER_READY、LIVE_CANDIDATE。

学生学会：LIVE_CANDIDATE 也不等于直接实盘。

## 第8课：进入模拟盘

目标：介绍 PaperBroker、paper 命令、模拟盘日志和限制。

学生学会：所有策略必须先模拟盘观察。

## 第9课：QMT实盘前检查

目标：演示 qmt-check / pretrade-check，解释 dry_run 和 CONFIRM_REAL_TRADE。

学生学会：真实交易默认关闭，AI 不允许绕过风控下单。

## 第10课：扩展自己的策略

目标：讲 Strategy DSL、ActionCompiler、组件化 entry/exit/filter/sizing。

学生学会：扩展策略应优先新增组件和测试，而不是改核心回测引擎。
