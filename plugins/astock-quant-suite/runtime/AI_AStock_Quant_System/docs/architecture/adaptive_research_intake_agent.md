# Adaptive Research Intake Agent

## 为什么需要 Adaptive Intake

0基础用户的策略想法通常是模糊的，例如“跌多了买，涨回去卖”。这种想法不能直接进入 Research Agent，更不能直接回测。Adaptive Research Intake Agent 的职责是先追问，把自然语言想法变成可计算、可回测、可审计的 Strategy Requirement 和 Strategy DSL。

## 标准入口

新手优先使用：

```bash
python3 cli.py intake-chat --idea "我想做中国神华，跌多了买，涨回去卖，控制回撤"
```

高级用户可使用 quick intake：

```bash
python3 cli.py intake --idea "中国神华周线布林低吸，控制回撤"
```

## 工作流

```text
Adaptive Intake
-> 多轮问答澄清
-> InterviewState
-> StrategyRequirement
-> Confirmation Summary
-> 用户确认
-> Strategy DSL
-> Research Agent
```

未确认前，`research_ready=false`。

## Question Tree

Question Tree 根据策略范式动态选择问题：

- 网格：追问网格间距、涨跌加减仓、最大仓位、连续加仓；
- 轮动：追问资产池、评分方式、调仓周期、top_k、切换阈值；
- 选股：追问股票池、因子、top_n、调仓周期；
- 波段：追问布林下轨、N日回撤、均线偏离、RSI超卖、ATR超跌；
- 配对 / 事件驱动：输出 BLOCKER。

## Readiness 规则

- 0-40：必须继续问，禁止进入 Research；
- 40-70：可生成初步需求，但假设很多，禁止自动 Research；
- 70-90：可生成 DSL，但必须用户确认；
- 90-100：可进入 Research，但默认仍建议确认。

## 输出文件

每次 intake-chat 会生成：

- conversation_log.md
- interview_state.json
- strategy_requirement.json
- strategy_dsl.yaml
- confirmation_summary.md
- unanswered_questions.md
- assumptions.md
- adaptive_intake_report.md

## 安全边界

Adaptive Intake 不负责研究、回测或下单。它只负责把想法问清楚。QMT / 实盘意图只会触发风险提醒，不会真实下单。
