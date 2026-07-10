# Instructor Guide

## 总讲法

这门课不是“教学生找神奇策略”，而是教学生建立可审计、可复现、可解释的 A股量化研究流程。

## 每一课讲解重点

### 第1课：跑通系统

重点：`course-demo`、报告目录、run_id。

不要讲复杂架构，先让学生看到结果。

### 第2课：A股交易规则

重点：T+1、涨跌停、停牌、100股、费用。

强调：交易规则是代码约束，不是 Prompt。

### 第3课：Intake

重点：模糊想法不能直接回测。

展示：自然语言如何变成 StrategyRequirement 和 DSL。

### 第4课：Research Agent

重点：ResearchPlan、策略范式、样本内/样本外。

强调：Research Agent 是研究员，不是许愿机。

### 第5课：回测和审计

重点：orders.csv、trades.csv、audit_report.md、readiness_report.md。

强调：先看审计，再看收益。

### 第6课：optimize-loop

重点：回测失败后诊断，而不是只调参数。

展示：Deep Diagnosis 和 batch experiments。

### 第7课：Readiness

重点：INVALID、RESEARCH_ONLY、PAPER_READY、LIVE_CANDIDATE。

强调：LIVE_CANDIDATE 也不是直接实盘。

### 第8课：模拟盘

重点：模拟盘是实盘前观察阶段。

不要承诺模拟盘结果能复制到实盘。

### 第9课：QMT实盘前检查

重点：dry_run、pretrade-check、CONFIRM_REAL_TRADE。

强调：课程默认不做真实下单。

### 第10课：扩展策略

重点：组件化 entry/exit/filter/sizing。

强调：扩展策略优先加组件和测试，不改核心风控。

## 哪些地方不能承诺收益

- 所有策略案例；
- Research Agent 输出；
- optimize-loop 候选；
- LIVE_CANDIDATE；
- batch experiments 结果；
- sample data 回测。

## 哪些地方强调风险

- qfq/hfq 未来函数风险；
- sample data 不是真实市场；
- 交易费用和滑点；
- T+1 对日内策略的限制；
- QMT 真实交易配置风险。

## 哪些地方展示系统优势

- 一句话进入 Intake；
- A股规则代码化；
- 审计报告自动生成；
- Readiness 阻断不成熟策略；
- Feedback Loop 不把无改善当停止；
- Batch experiments 检查跨周期/跨标的/regime。

## 学员常见问题

### 这个系统能赚钱吗？

不能承诺。它是研究和审计工具，不是收益保证工具。

### 为什么我的策略是 INVALID？

INVALID 是保护机制。先看 audit_report 和 INVALID 原因。

### 为什么 QMT 检查失败？

课程默认未连接 QMT。QMT 需要真实 MiniQMT / XtQuant 环境和本地配置。

### 为什么 sample data 结果不好？

sample data 用来跑通流程，不代表真实市场。

### 我能直接拿 LIVE_CANDIDATE 实盘吗？

不能。还需要模拟盘、人工复核、真实数据验证和 QMT pretrade-check。
